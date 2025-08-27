# client/client_agent.py
import json
import time
import threading
import requests
import websocket
import sys
import os

# Testing mouse button 4 and 5 clicks using ctypes 
import ctypes

# Constants
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

def click_xbutton(button=1):
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_XDOWN, 0, 0, button, 0)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_XUP, 0, 0, button, 0)


# Colorful logs
from colorama import init, Fore, Style
init(autoreset=True)

# Try to import keyboard; if not available or fails, you can switch to pynput
try:
    import keyboard   # pip install keyboard
except Exception:
    keyboard = None

CONFIG_PATH = "config.json"

def log_info(msg):    print(Fore.CYAN + "[INFO] " + Style.RESET_ALL + msg)
def log_warn(msg):    print(Fore.YELLOW + "[WARN] " + Style.RESET_ALL + msg)
def log_error(msg):   print(Fore.RED + "[ERROR] " + Style.RESET_ALL + msg)
def log_ws(msg):      print(Fore.CYAN + "[WS] " + Style.RESET_ALL + msg)
def log_action(msg):  print(Fore.GREEN + "[ACTION] " + Style.RESET_ALL + msg)

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def ws_on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception as e:
        log_ws(f"invalid message: {e} {message}")
        return

    action = data.get("action")
    if not action:
        log_ws("no action in payload")
        return

    # expected action shape: { "action_name": "jump", "keybind": "space", "duration": 0 }
    keybind = action.get("keybind")
    duration = float(action.get("duration", 0) or 0)

    if not keybind:
        log_action("invalid action payload (no keybind)")
        return

    t = threading.Thread(target=perform_action, args=(keybind, duration, action.get("action_name")), daemon=True)
    t.start()

def perform_action(keybind: str, duration: float, action_name: str = None):
    label = f"{action_name or keybind}"
    try:
        # trying mouse button clicks
        if keybind == "mb4":
            click_xbutton(XBUTTON1)
            log_action(f"{label} => clicked mouse button 4")
            return
        elif keybind == "mb5":
            click_xbutton(XBUTTON2)
            log_action(f"{label} => clicked mouse button 5")
            return

        if duration == 0:
            if keyboard:
                keyboard.press_and_release(keybind)
                log_action(f"{label} => pressed once")
            else:
                log_warn(f"{label} => (keyboard lib not available)")
            return

        # duration > 0: repeat press+release until duration elapses
        end = time.time() + duration
        if keyboard:
            while time.time() < end:
                keyboard.press(keybind)
                time.sleep(0.035)
            keyboard.release(keybind)
        else:
            log_warn(f"{label} => keyboard lib not available; simulating only")
            while time.time() < end:
                time.sleep(0.035)

        log_action(f"{label} => held {duration}s (simulated via repeated presses)")
    except Exception as e:
        log_error(f"{label} error: {e}")

def ws_on_open(ws, cfg):
    def run_send_init():
        payload = {"access_token": cfg["access_token"], "keys": cfg.get("keys", [])}
        ws.send(json.dumps(payload))
        log_ws("sent init payload (access token + keys). Waiting for actions...")
        base_url = cfg.get("base_url")
        access_token = cfg.get("access_token")
        try:
            r = requests.get(f"{base_url.rstrip('/')}/whoami/{access_token}", timeout=6)
            if r.status_code == 200:
                uuid = r.json().get("uuid")
                log_ws(f"Connected as {Fore.YELLOW}{uuid}{Style.RESET_ALL}")
        except Exception as e:
            log_error(f"failed to fetch uuid: {e}")

    threading.Thread(target=run_send_init, daemon=True).start()

def ws_on_close(ws, code, reason):
    log_ws(f"closed {code} {reason}")

def ws_on_error(ws, err):
    log_error(f"ws error: {err}")

def login_and_get_uuid(base_url, access_token):
    try:
        r = requests.get(f"{base_url.rstrip('/')}/whoami/{access_token}", timeout=6)
        if r.status_code == 200:
            return r.json().get("uuid")
    except Exception:
        pass
    return None

def main():
    if not os.path.exists(CONFIG_PATH):
        log_error("Missing config.json. Copy config.example.json -> config.json and edit.")
        sys.exit(1)

    cfg = load_config()

    # if base_url and access_token are not present
    if not cfg.get("base_url") or not cfg.get("access_token"):
        log_error("Missing base_url or access_token in config.json.")
        sys.exit(1)
        
    base_url = cfg.get("base_url").rstrip("/")
    ws_url = base_url.replace("http", "ws") + "/ws"

    log_info(f"Base: {base_url}")
    uuid = login_and_get_uuid(base_url, cfg["access_token"])
    if uuid:
        log_info(f"Known UUID for token: {Fore.YELLOW}{uuid}{Style.RESET_ALL}")
    else:
        log_warn("Token not yet registered; will be created on WS connect.")

    while True:
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=ws_on_message,
                on_open=lambda _ws: ws_on_open(_ws, cfg),
                on_close=ws_on_close,
                on_error=ws_on_error
            )
            log_ws(f"connecting to {ws_url}")
            ws.run_forever()
        except KeyboardInterrupt:
            log_info("Exiting client.")
            break
        except Exception as e:
            log_error(f"exception: {e}")
        log_ws("disconnected. reconnecting in 3s...")
        time.sleep(3)

if __name__ == "__main__":
    main()
