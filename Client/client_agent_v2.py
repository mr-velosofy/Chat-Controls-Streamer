# client/client_agent.py
import json
import time
import threading
import requests
import websocket
import sys
import os
import ctypes

# ==============================
# Rich UI (instead of colorama)
# ==============================
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

def log_info(msg):    
    console.print(f"[bold cyan][INFO][/bold cyan] {msg}")

def log_warn(msg):    
    console.print(f"[bold yellow][WARN][/bold yellow] {msg}")

def log_error(msg):   
    console.print(f"[bold red][ERROR][/bold red] {msg}")

def log_ws(msg):      
    console.print(f"[bold cornflower_blue][WS][/bold cornflower_blue] {msg}")

def log_action(msg):  
    console.print(
                Panel.fit(
                    f"[bold cornflower_blue][ACTION][/bold cornflower_blue] {msg}",
                    box=box.ROUNDED,
                    style="cornflower_blue"
                )
    )

CONFIG_PATH = "config.json"

# ==============================
# Keyboard support
# ==============================
try:
    import keyboard   
except Exception:
    keyboard = None
    log_warn("Keyboard library not available! Some actions may not work.")

# ==============================
# Core Functions
# ==============================
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def ws_on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception as e:
        log_ws(f"Invalid message: {e} {message}")
        return

    action = data.get("action")
    user_name = data.get("user_name")
    if not action:
        log_ws("No action in payload")
        return

    keybind = action.get("keybind")
    duration = float(action.get("duration", 0) or 0)

    if not keybind:
        log_action("Invalid action payload (no keybind)")
        return

    t = threading.Thread(
        target=perform_action,
        args=(keybind, duration, action.get("action_name"), user_name),
        daemon=True
    )
    t.start()

def perform_action(keybind: str, duration: float, action_name: str = None, user_name: str = None):

    label = f"{action_name + " (" + keybind.upper() + ")"}"
    keybind = keybind.lower()
    #  if user_name then add <user_name>
    if user_name:
        label = f"{user_name} - {label}"
    try:
        # Normal keyboard presses
        if duration == 0:
            if keyboard:
                keyboard.press_and_release(keybind)
                log_action(f"{label} → Pressed once ")
            else:
                log_warn(f"{label} → (keyboard lib not available)")
            return

        # Holding down key for duration
        end = time.time() + duration
        if keyboard:
            while time.time() < end:
                keyboard.press(keybind)
                time.sleep(0.03)
            keyboard.release(keybind)
        else:
            log_warn(f"{label} → Keyboard lib not available; simulating only")
            while time.time() < end:
                time.sleep(0.03)

        log_action(f"{label} → Held for {duration}s ")
    except Exception as e:
        log_error(f"{label} error: {e}")

def ws_on_open(ws, cfg):
    def run_send_init():
        payload = {"access_token": cfg["access_token"], "keys": cfg.get("keys", [])}
        ws.send(json.dumps(payload))
        log_ws(" Sent init payload (access token + keys). Waiting for actions...")

        base_url = cfg.get("base_url")
        access_token = cfg.get("access_token")
        try:
            r = requests.get(f"{base_url.rstrip('/')}/whoami/{access_token}", timeout=6)
            if r.status_code == 200:
                uuid = r.json().get("uuid")
                console.print(
                    Panel.fit(
                        f"[bold cyan]Connected as[/bold cyan] [yellow]{uuid}[/yellow] ",
                        box=box.ROUNDED,
                        style="green"
                    )
                )
        except Exception as e:
            log_error(f"Failed to fetch uuid: {e}")

    threading.Thread(target=run_send_init, daemon=True).start()

def ws_on_close(ws, code, reason):
    log_ws(f" Connection closed ({code}) {reason}")

def ws_on_error(ws, err):
    log_error(f" WebSocket error: {err}")

def login_and_get_uuid(base_url, access_token):
    try:
        r = requests.get(f"{base_url.rstrip('/')}/whoami/{access_token}", timeout=6)
        if r.status_code == 200:
            return r.json().get("uuid")
    except Exception:
        pass
    return None

# ==============================
# Main Client
# ==============================
def main():
    if not os.path.exists(CONFIG_PATH):
        console.print(
            Panel(
                "[red]Missing config.json![/red]\n\nCopy [bold]config.example.json[/bold] → config.json and edit.",
                title=" Config Error",
                style="bold red",
                box=box.DOUBLE
            )
        )
        sys.exit(1)

    cfg = load_config()

    if not cfg.get("base_url") or not cfg.get("access_token"):
        console.print(
            Panel(
                "[red]Missing base_url or access_token in config.json[/red]",
                title=" Config Incomplete",
                style="bold red",
                box=box.DOUBLE
            )
        )
        sys.exit(1)

    base_url = cfg.get("base_url").rstrip("/")
    ws_url = base_url.replace("http", "ws") + "/ws"

    console.print(Panel.fit(f"[cyan]Base URL:[/cyan] {base_url}", box=box.ROUNDED, style="cornflower_blue"))

    uuid = login_and_get_uuid(base_url, cfg["access_token"])
    if uuid:
        console.print(f"[bold green] Known UUID for token:[/bold green] [yellow]{uuid}[/yellow]")
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
            log_ws(f" Connecting to {ws_url}")
            ws.run_forever()
        except KeyboardInterrupt:
            console.print("[bold magenta] Exiting client...[/bold magenta]")
            break
        except Exception as e:
            log_error(f"Unexpected exception: {e}")

        console.print("[yellow]Reconnecting in 3s...[/yellow]")
        time.sleep(3)


if __name__ == "__main__":
    main()
