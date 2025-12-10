import time
import os
import json
import requests
import configparser

CONFIG_FILE = "config.ini"
ONLINE_FILE = "data/online.json"


# ---------------------------
# Cargar o crear configuraciones
# ---------------------------
def load_config():
    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_FILE):
        # Crear archivo de configuración por primera vez
        config["webhook"] = {"url": ""}
        config["messages"] = {
            "server_on": "🟢 Servidor iniciado",
            "server_off": "🔴 Servidor detenido",
            "player_on": "🟢 {player} se ha conectado",
            "player_off": "🔴 {player} se ha desconectado",
        }
        config["server"] = {
            "log_path": "enshrouded_server.log",
            "auto_start": "1"
        }

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)

    config.read(CONFIG_FILE, encoding="utf-8")
    return config


# ---------------------------
# Manejo de archivo online.json
# ---------------------------
def load_online():
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(ONLINE_FILE):
        with open(ONLINE_FILE, "w") as f:
            json.dump({}, f)

    with open(ONLINE_FILE, "r") as f:
        return json.load(f)


def save_online(data):
    with open(ONLINE_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---------------------------
# Enviar mensaje al Webhook
# ---------------------------
def send_webhook(url, message):
    if not url:
        print("Webhook no configurado.")
        return

    try:
        requests.post(url, json={"content": message})
        print("[Webhook]:", message)
    except Exception as e:
        print("Error webhook:", e)


# ---------------------------
# Procesar líneas del log
# ---------------------------
def extract_player(line):
    try:
        return line.split("'")[1]
    except:
        return None


def monitor_log(config, online):
    log_path = config["server"]["log_path"]
    webhook = config["webhook"]["url"]

    msg_player_on = config["messages"]["player_on"]
    msg_player_off = config["messages"]["player_off"]
    msg_server_on = config["messages"]["server_on"]
    msg_server_off = config["messages"]["server_off"]

    last_size = 0
    server_running = False

    print("Monitoreo iniciado...")
    send_webhook(webhook, msg_server_on)

    while True:
        # Servidor apagado o log inexistente
        if not os.path.exists(log_path):
            if server_running:
                send_webhook(webhook, msg_server_off)
            server_running = False
            time.sleep(2)
            continue

        # Si aparece el log → servidor iniciado
        if not server_running:
            send_webhook(webhook, msg_server_on)
            server_running = True

        size = os.path.getsize(log_path)

        # Leer solo lo nuevo
        if size > last_size:
            with open(log_path, "r", errors="ignore") as f:
                f.seek(last_size)
                new_lines = f.read().splitlines()

            for line in new_lines:

                # Jugador entra
                if "Send Character Savegame" in line:
                    player = extract_player(line)
                    if player and not online.get(player, False):
                        online[player] = True
                        send_webhook(webhook, msg_player_on.replace("{player}", player))

                # Jugador sale
                elif "Remove Entity for Player" in line:
                    player = extract_player(line)
                    if player and online.get(player, False):
                        online[player] = False
                        send_webhook(webhook, msg_player_off.replace("{player}", player))

            save_online(online)

        last_size = size
        time.sleep(1)


# ---------------------------
# Ejecución principal
# ---------------------------
if __name__ == "__main__":
    config = load_config()
    online = load_online()

    auto_start = config["server"].get("auto_start", "1")

    if auto_start == "1":
        monitor_log(config, online)
    else:
        print("Auto-start desactivado. Cambia auto_start = 1 en config.ini para iniciar automáticamente.")
