#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Monitor Enshrouded - Discord + SQLite + Tail-F real
Detecta:
 - [server] Player 'X' logged in with Permissions:   (JOIN)
 - Remove Entity for Player 'X'                      (LEAVE)

Modo de ejecución (config.ini):
[mode]
run_mode = TERMINAL   ; TERMINAL | GUI | SERVICE
"""

import os
import sys
import time
import re
import json
import sqlite3
import logging
import configparser
from datetime import datetime, timezone
from urllib import request, error as urlerror

# ---------------------------------------------------------
# CONFIGURACIÓN DE RUTAS
# ---------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "monitor.log")

# ---------------------------------------------------------
# LOGGING INTERNO (se ajusta luego según modo)
# ---------------------------------------------------------

logger = logging.getLogger("enshrouded_monitor")
logger.setLevel(logging.INFO)

fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
fh.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

# ---------------------------------------------------------
# LEER CONFIG.INI
# ---------------------------------------------------------

CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.ini")
config = configparser.ConfigParser()

if not os.path.isfile(CONFIG_PATH):
    logger.error("config.ini NO encontrado. Crea uno antes de continuar.")
    sys.exit(1)

config.read(CONFIG_PATH, encoding="utf-8")

def cfg(section, key, default=None):
    try:
        return config.get(section, key)
    except:
        return default

def cfg_int(section, key, default=0):
    try:
        return config.getint(section, key)
    except:
        return default

# Modo
run_mode = cfg("mode", "run_mode", "TERMINAL")
run_mode = (run_mode or "TERMINAL").strip().upper()

# General
log_path_cfg = cfg("general", "log_path", "enshrouded_server.log")
auto_start = cfg_int("general", "auto_start", 1)

# Discord
discord_enable = cfg_int("discord", "enable", 1) == 1
discord_webhook = cfg("discord", "webhook_url", "").strip()

msg_join = cfg("discord", "msg_player_join", "🟢 El jugador {player} se ha conectado.")
msg_leave = cfg("discord", "msg_player_leave", "🔴 El jugador {player} se ha desconectado.")
msg_server_start = cfg("discord", "msg_server_start", "⚡ Servidor de Enshrouded monitoreado iniciado.")
msg_server_stop = cfg("discord", "msg_server_stop", "🔻 Monitor detenido.")

# Database
db_path_cfg = cfg("database", "sqlite_file", "enshrouded.db")

# Resolver rutas
LOG_PATH = log_path_cfg if os.path.isabs(log_path_cfg) else os.path.join(SCRIPT_DIR, log_path_cfg)
DB_PATH = db_path_cfg if os.path.isabs(db_path_cfg) else os.path.join(SCRIPT_DIR, db_path_cfg)

# Ajustar logging según modo
if run_mode == "SERVICE":
    # En modo servicio no queremos spam en la consola
    logger.removeHandler(ch)

logger.info("Modo de ejecución: %s", run_mode)
logger.info("Usando log_path: %s", LOG_PATH)
logger.info("Usando sqlite_file: %s", DB_PATH)

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def parse_log_time(line):
    """
    Extrae la hora de la línea del log de Enshrouded, si existe.
    Ejemplo: [I 02:48:39,079] ...
    Devuelve '02:48:39,079' o None.
    """
    m = re.match(r"\[[IWE]\s+(?P<t>\d{2}:\d{2}:\d{2},\d{3})\]", line)
    return m.group("t") if m else None

# ---------------------------------------------------------
# DISCORD WEBHOOK (FIX CLOUDFLARE)
# ---------------------------------------------------------

def send_discord(msg):
    if not discord_enable:
        return
    if not discord_webhook:
        logger.warning("Webhook de Discord vacío.")
        return

    payload = {"content": msg}
    data = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "curl/8.5.0",
        "Accept": "*/*"
    }

    req = request.Request(discord_webhook, data=data, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=10) as resp:
            if resp.getcode() >= 300:
                logger.error("Discord devolvió status: %s", resp.getcode())
    except urlerror.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        logger.error("Discord HTTPError %s: %s", e.code, body)
    except Exception as e:
        logger.exception("Error enviando a Discord: %s", e)

# ---------------------------------------------------------
# BASE DE DATOS SQLITE
# ---------------------------------------------------------

def init_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at_utc TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            session_start_utc TEXT,
            session_end_utc TEXT,
            duration_seconds INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            event_type TEXT,
            event_time_utc TEXT,
            log_time TEXT,
            raw_line TEXT,
            session_id INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS server_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            event_time_utc TEXT,
            raw_line TEXT
        )
    """)

    conn.commit()
    return conn

def get_or_create_player(conn, name):
    c = conn.cursor()
    c.execute("SELECT id FROM players WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        return row[0]
    c.execute("INSERT INTO players (name, created_at_utc) VALUES (?, ?)",
              (name, utc_now()))
    conn.commit()
    return c.lastrowid

def start_session(conn, pid):
    c = conn.cursor()
    c.execute("""
        INSERT INTO sessions (player_id, session_start_utc)
        VALUES (?, ?)
    """, (pid, utc_now()))
    conn.commit()
    return c.lastrowid

def end_session(conn, sid):
    c = conn.cursor()
    c.execute("SELECT session_start_utc FROM sessions WHERE id=?", (sid,))
    row = c.fetchone()
    if not row:
        return
    start = datetime.fromisoformat(row[0])
    end = datetime.now(timezone.utc)
    duration = int((end - start).total_seconds())

    c.execute("""
        UPDATE sessions
        SET session_end_utc=?, duration_seconds=?
        WHERE id=?
    """, (utc_now(), duration, sid))
    conn.commit()

def insert_event(conn, pid, event_type, log_time, raw, sid=None):
    c = conn.cursor()
    c.execute("""
        INSERT INTO events (player_id, event_type, event_time_utc, log_time, raw_line, session_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (pid, event_type, utc_now(), log_time, raw, sid))
    conn.commit()

def insert_server_event(conn, event_type, raw=None):
    c = conn.cursor()
    c.execute("""
        INSERT INTO server_events (event_type, event_time_utc, raw_line)
        VALUES (?, ?, ?)
    """, (event_type, utc_now(), raw))
    conn.commit()

# ---------------------------------------------------------
# DETECCIÓN JOIN / LEAVE
# ---------------------------------------------------------

# JOIN solo cuando es exactamente la línea de Player con Permissions:
# [I ...] [server] Player 'NOMBRE' logged in with Permissions:
JOIN_MARKER = "logged in with Permissions"
JOIN_RE = re.compile(
    r"\[.*?\]\s+\[server\]\s+Player '([^']+)' logged in with Permissions:"
)

# LEAVE patrón anterior:
LEAVE_MARKER = "Remove Entity for Player"
LEAVE_RE = re.compile(r"'([^']+)'")

class SessionManager:
    def __init__(self, conn):
        self.conn = conn
        self.active = {}  # player -> session_id

    def join(self, player, line):
        logger.info("JOIN detectado: %s", player)
        pid = get_or_create_player(self.conn, player)

        # Si ya tenía sesión abierta (edge case), cerrarla primero
        if player in self.active:
            end_session(self.conn, self.active[player])

        sid = start_session(self.conn, pid)
        self.active[player] = sid

        insert_event(self.conn, pid, "join", parse_log_time(line), line, sid)
        send_discord(msg_join.format(player=player))

    def leave(self, player, line):
        logger.info("LEAVE detectado: %s", player)
        pid = get_or_create_player(self.conn, player)

        sid = self.active.get(player)
        if sid:
            end_session(self.conn, sid)
            insert_event(self.conn, pid, "leave", parse_log_time(line), line, sid)
            self.active.pop(player, None)
        else:
            # Leave sin sesión en memoria (por ejemplo, script iniciado a mitad de sesión)
            logger.warning(
                "Jugador %s no tenía sesión activa en memoria. Registrando leave sin sesión asociada.",
                player,
            )
            insert_event(self.conn, pid, "leave", parse_log_time(line), line, None)

        send_discord(msg_leave.format(player=player))

# ---------------------------------------------------------
# TAIL -F
# ---------------------------------------------------------

def follow(path):
    while True:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                # Ir al final del archivo: sólo nuevas líneas
                f.seek(0, os.SEEK_END)
                logger.info("Comenzando tail -f en: %s", path)

                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.3)
                        continue
                    yield line.rstrip("\n")
        except FileNotFoundError:
            logger.error("Archivo de log NO encontrado: %s", path)
            time.sleep(3)
        except Exception as e:
            logger.exception("Error tailing: %s", e)
            time.sleep(3)

# ---------------------------------------------------------
# PROCESADOR DE LÍNEAS
# ---------------------------------------------------------

def process_line(line, sm: SessionManager):
    # JOIN: sólo aceptamos la línea completa con Permissions
    if JOIN_MARKER in line and "[server]" in line and "Player '" in line:
        m = JOIN_RE.search(line)
        if m:
            player = m.group(1)
            sm.join(player, line)
        return

    # LEAVE
    if LEAVE_MARKER in line:
        m = LEAVE_RE.search(line)
        if m:
            player = m.group(1)
            sm.leave(player, line)
        return

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    logger.info("Monitor Enshrouded iniciado.")
    conn = init_db(DB_PATH)

    sm = SessionManager(conn)
    insert_server_event(conn, "start", "monitor_start")
    send_discord(msg_server_start)

    # En modo TERMINAL/GUI respetamos auto_start; en SERVICE nunca pedimos input.
    if run_mode in ("TERMINAL", "GUI") and not auto_start:
        try:
            input("Presiona ENTER para iniciar el seguimiento del log (tail -f)...")
        except EOFError:
            # Si no hay stdin, continuamos igual
            pass

    logger.info("Comenzando seguimiento en tiempo real del log.")
    logger.info("NOTA: Sólo se procesarán líneas NUEVAS agregadas al archivo.")

    try:
        for line in follow(LOG_PATH):
            try:
                process_line(line, sm)
            except Exception as e:
                logger.exception("Error procesando línea: %s", e)

    except KeyboardInterrupt:
        logger.info("Monitor interrumpido por el usuario (CTRL+C).")
        send_discord(msg_server_stop)
    finally:
        insert_server_event(conn, "stop", "monitor_stop")
        conn.close()
        logger.info("Monitor Enshrouded detenido.")

if __name__ == "__main__":
    main()
