import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import configparser
import os

CONFIG_FILE = "config.ini"

def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        return None
    config.read(CONFIG_FILE, encoding="utf-8")
    return config

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)

def create_gui():
    config = load_config()
    if config is None:
        messagebox.showerror("Error", "config.ini no existe. Ejecuta monitor.py primero.")
        return

    root = tk.Tk()
    root.title("Configuración Enshrouded Monitor")

    tk.Label(root, text="Webhook URL:").grid(row=0, column=0, sticky="w")
    url = tk.Entry(root, width=60)
    url.insert(0, config["webhook"]["url"])
    url.grid(row=0, column=1)

    tk.Label(root, text="Mensaje Servidor ON:").grid(row=1, column=0, sticky="w")
    msg_on = tk.Entry(root, width=60)
    msg_on.insert(0, config["messages"]["server_on"])
    msg_on.grid(row=1, column=1)

    tk.Label(root, text="Mensaje Servidor OFF:").grid(row=2, column=0, sticky="w")
    msg_off = tk.Entry(root, width=60)
    msg_off.insert(0, config["messages"]["server_off"])
    msg_off.grid(row=2, column=1)

    tk.Label(root, text="Mensaje Player ON:").grid(row=3, column=0, sticky="w")
    on_player = tk.Entry(root, width=60)
    on_player.insert(0, config["messages"]["player_on"])
    on_player.grid(row=3, column=1)

    tk.Label(root, text="Mensaje Player OFF:").grid(row=4, column=0, sticky="w")
    off_player = tk.Entry(root, width=60)
    off_player.insert(0, config["messages"]["player_off"])
    off_player.grid(row=4, column=1)

    tk.Label(root, text="Ruta del archivo de log:").grid(row=5, column=0, sticky="w")
    log_path = tk.Entry(root, width=60)
    log_path.insert(0, config["server"]["log_path"])
    log_path.grid(row=5, column=1)

    def save():
        config["webhook"]["url"] = url.get()
        config["messages"]["server_on"] = msg_on.get()
        config["messages"]["server_off"] = msg_off.get()
        config["messages"]["player_on"] = on_player.get()
        config["messages"]["player_off"] = off_player.get()
        config["server"]["log_path"] = log_path.get()

        save_config(config)
        messagebox.showinfo("Guardado", "Configuración actualizada")
        root.destroy()

    tk.Button(root, text="Guardar", command=save).grid(row=6, column=1)
    root.mainloop()

if __name__ == "__main__":
    create_gui()
