import os
import json

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "user_settings.json")

DEFAULT_SETTINGS = {
    "context_window": 2048,
    "active_analytical_model": "",
    "active_math_model": "",
    "analytical_server_url": "http://localhost:8000",
    "math_server_url": "http://localhost:8001",
    "active_server": "Локальный сервер",
    "share_library": False,
    "library_port": 8000
}

AVAILABLE_SERVERS = {
    "Локальный сервер": "http://localhost:8000",
    "Глобальный сервер": "http://YOUR_GLOBAL_SERVER_IP:8000"   # ← замени на нужный IP/порт!
}

def get_share_library():
    settings = load_settings()
    return settings.get("share_library", False)

def set_share_library(val):
    settings = load_settings()
    settings["share_library"] = bool(val)
    save_settings(settings)

def get_library_port():
    settings = load_settings()
    return int(settings.get("library_port", 8000))

def set_library_port(port):
    settings = load_settings()
    settings["library_port"] = int(port)
    save_settings(settings)

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def get_active_server():
    settings = load_settings()
    return settings.get("active_server", "Локальный сервер")

def set_active_server(server_key):
    settings = load_settings()
    if server_key not in AVAILABLE_SERVERS:
        server_key = "Локальный сервер"
    settings["active_server"] = server_key
    save_settings(settings)

def get_available_server_choices():
    return [(v, k) for k, v in AVAILABLE_SERVERS.items()]

def get_server_url():
    settings = load_settings()
    key = settings.get("active_server", "Локальный сервер")
    return AVAILABLE_SERVERS.get(key, "http://localhost:8000")

def get_analytical_server_url():
    settings = load_settings()
    return settings.get("analytical_server_url", "http://localhost:8000")

def set_analytical_server_url(url):
    settings = load_settings()
    settings["analytical_server_url"] = url
    save_settings(settings)

def get_math_server_url():
    settings = load_settings()
    return settings.get("math_server_url", "http://localhost:8001")

def set_math_server_url(url):
    settings = load_settings()
    settings["math_server_url"] = url
    save_settings(settings)

def get_active_analytical_model():
    settings = load_settings()
    return settings.get("active_analytical_model", "")

def set_active_analytical_model(model):
    settings = load_settings()
    settings["active_analytical_model"] = model
    save_settings(settings)

def get_active_math_model():
    settings = load_settings()
    return settings.get("active_math_model", "")

def set_active_math_model(model):
    settings = load_settings()
    settings["active_math_model"] = model
    save_settings(settings)
