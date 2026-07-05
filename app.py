import os
import json
import time
import ctypes
import threading
import asyncio
import webbrowser
import requests
import urllib3
import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Suppress insecure SSL warnings for LOL Live API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

CONFIG_PATH = "config.json"
system_logs = []
active_connections = set()
async_loop = None

# Global game states
game_status = "not_running"  # not_running, loading, in_game
player_status = "unknown"     # unknown, alive, dead
summoner_name = ""
prev_is_dead = False
is_first_check = True

class Settings(BaseModel):
    room_id: str
    polling_interval: float
    is_monitoring: bool
    is_simulation: bool
    test_window_title: str

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "room_id": "22603245",
        "polling_interval": 1.0,
        "is_monitoring": True,
        "is_simulation": True,
        "test_window_title": "无标题 - 记事本"
    }

def save_config(config_data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        add_log(f"保存配置文件失败: {e}")

# Global cached config to avoid disk I/O in the polling loop
cached_config = load_config()

def add_log(message):
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    system_logs.append(log_entry)
    if len(system_logs) > 50:
        system_logs.pop(0)
    print(log_entry)
    # Broadcast to WebSocket
    broadcast_event("log", {"log": log_entry})

def get_current_state_payload():
    cfg = load_config()
    return {
        "game_status": game_status,
        "player_status": player_status,
        "summoner_name": summoner_name,
        "room_id": cfg.get("room_id", "22603245"),
        "polling_interval": cfg.get("polling_interval", 1.0),
        "is_monitoring": cfg.get("is_monitoring", True),
        "is_simulation": cfg.get("is_simulation", True),
        "test_window_title": cfg.get("test_window_title", "无标题 - 记事本"),
        "connections_count": len(active_connections),
        "logs": system_logs
    }

def broadcast_event(event_type, data):
    if not async_loop:
        return
    coro = send_broadcast(event_type, data)
    asyncio.run_coroutine_threadsafe(coro, async_loop)

async def send_broadcast(event_type, data):
    payload = {
        "type": "event",
        "event": event_type,
        "data": data,
        "state": get_current_state_payload()
    }
    for conn in list(active_connections):
        try:
            await conn.send_json(payload)
        except Exception:
            if conn in active_connections:
                active_connections.remove(conn)

# Extension Connections (Bilibili official live room plugin)
extension_connections = set()

def broadcast_to_extension(action):
    if not async_loop:
        return
    coro = send_extension_broadcast(action)
    asyncio.run_coroutine_threadsafe(coro, async_loop)

async def send_extension_broadcast(action):
    payload = {
        "action": action
    }
    for conn in list(extension_connections):
        try:
            await conn.send_json(payload)
        except Exception:
            if conn in extension_connections:
                extension_connections.remove(conn)

def broadcast_state_change():
    broadcast_event("state_change", get_current_state_payload())

# Window Focus Workaround using Win32 API and ctypes (Pure ctypes, no win32gui dependencies)
def focus_target_window(test_title, is_simulation=False):
    import ctypes
    from ctypes import wintypes
    
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    
    # Win32 API function definitions
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetActiveWindow.argtypes = [wintypes.HWND]
    user32.SetActiveWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    user32.FindWindowW.argtypes = [wintypes.LPWSTR, wintypes.LPWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_size_t]
    user32.keybd_event.restype = None

    target_hwnd = None

    def enum_callback(hwnd, lParam):
        nonlocal target_hwnd
        if user32.IsWindowVisible(hwnd):
            length = 512
            buffer = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buffer, length)
            title = buffer.value
            
            if not is_simulation:
                # Direct match by title first
                if "league of legends" in title.lower():
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    try:
                        proc = psutil.Process(pid.value)
                        if proc.name().lower() == "league of legends.exe":
                            target_hwnd = hwnd
                            return False  # Stop enumeration
                    except Exception:
                        pass
            else:
                # 1. Match by specified window title substring
                if test_title and test_title.lower() in title.lower():
                    target_hwnd = hwnd
                    return False
                # 2. Fallback: if we are looking for Notepad, match by process name
                if test_title and test_title.lower() in ["notepad", "记事本", "无标题 - 记事本", "无标题-notepad"]:
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    try:
                        proc = psutil.Process(pid.value)
                        if proc.name().lower() in ["notepad.exe", "notepad"]:
                            target_hwnd = hwnd
                            return False
                    except Exception:
                        pass
        return True

    cb_proc = WNDENUMPROC(enum_callback)
    user32.EnumWindows(cb_proc, 0)

    if not target_hwnd and is_simulation and test_title:
        # Exact match fallback
        target_hwnd = user32.FindWindowW(None, test_title)
            
    if not target_hwnd:
        desc = f"标题含有 '{test_title}' 的窗口" if is_simulation else "英雄联盟游戏窗口 (League of Legends.exe)"
        add_log(f"未找到目标窗口: {desc}，无法执行置顶。")
        return False

    length = 512
    buffer = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(target_hwnd, buffer, length)
    title_found = buffer.value
    
    add_log(f"找到目标窗口: '{title_found}' (HWND: {target_hwnd})，正在强行置顶聚焦...")
    
    try:
        # 1. If iconic (minimized), restore it
        if user32.IsIconic(target_hwnd):
            user32.ShowWindow(target_hwnd, 9) # SW_RESTORE
        else:
            user32.ShowWindow(target_hwnd, 5) # SW_SHOW

        # 2. Attach thread input to bypass SetForegroundWindow lock
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd != target_hwnd:
            fg_thread_id = user32.GetWindowThreadProcessId(fg_hwnd, None)
            current_thread_id = kernel32.GetCurrentThreadId()
            target_thread_id = user32.GetWindowThreadProcessId(target_hwnd, None)
            
            # Attach current thread to foreground thread & target thread
            if fg_thread_id != current_thread_id and fg_thread_id != 0:
                user32.AttachThreadInput(current_thread_id, fg_thread_id, True)
            if target_thread_id != current_thread_id and target_thread_id != 0:
                user32.AttachThreadInput(current_thread_id, target_thread_id, True)
            
            # Alt key trick: Press Alt
            user32.keybd_event(0x12, 0, 0, 0)
            
            user32.BringWindowToTop(target_hwnd)
            user32.SetForegroundWindow(target_hwnd)
            
            # Release Alt
            user32.keybd_event(0x12, 0, 2, 0)
            
            # Detach
            if fg_thread_id != current_thread_id and fg_thread_id != 0:
                user32.AttachThreadInput(current_thread_id, fg_thread_id, False)
            if target_thread_id != current_thread_id and target_thread_id != 0:
                user32.AttachThreadInput(current_thread_id, target_thread_id, False)
        else:
            # Alt key trick: Press Alt
            user32.keybd_event(0x12, 0, 0, 0)
            user32.SetForegroundWindow(target_hwnd)
            # Release Alt
            user32.keybd_event(0x12, 0, 2, 0)
            
        user32.SetActiveWindow(target_hwnd)
        add_log(f"已成功激活窗口: '{title_found}'")
        return True
    except Exception as e:
        add_log(f"置顶窗口时出错: {e}")
        try:
            user32.SetForegroundWindow(target_hwnd)
            return True
        except Exception:
            return False

# Helper to launch browser in app mode (no blank new tab page, cleaner UI)
def open_browser_app(url):
    import os
    import subprocess
    
    # Check Chrome
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            add_log(f"检测到 Chrome 浏览器，以 App 模式启动: {url}")
            subprocess.Popen(f'"{path}" --app={url}')
            return True
            
    # Check Edge
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for path in edge_paths:
        if os.path.exists(path):
            add_log(f"检测到 Edge 浏览器，以 App 模式启动: {url}")
            subprocess.Popen(f'"{path}" --app={url}')
            return True
            
    # Fallback to standard start command
    add_log(f"未检测到 Chrome/Edge 路径，使用系统默认浏览器打开: {url}")
    subprocess.Popen(f'start "" "{url}"', shell=True)
    return False

# Event Handlers
def handle_death_event(cfg):
    room_id = cfg.get("room_id", "22603245")
    add_log(f"触发阵亡事件！玩家阵亡。")
    
    # Broadcast to Bilibili official extension if connected
    if len(extension_connections) > 0:
        add_log("检测到 B站 官方直播插件已连接，发送 WebSocket 指令取消静音。")
        broadcast_to_extension("unmute")
        
    # If dashboard is open, send WebSocket event to unmute
    if len(active_connections) > 0:
        add_log("检测到控制面板网页已开启，发送 WebSocket 指令取消静音。")
        broadcast_event("death", {"room_id": room_id})
    elif len(extension_connections) == 0:
        # Neither dashboard nor extension is active, open Bilibili official live room directly
        url = f"https://live.bilibili.com/{room_id}"
        open_browser_app(url)
        
    # Bring the browser page to the front
    add_log("正在尝试置顶浏览器/直播窗口...")
    # First try Bilibili official live room, then the local dashboard
    if not focus_target_window("哔哩哔哩", is_simulation=True):
        if not focus_target_window(room_id, is_simulation=True):
            focus_target_window("永雏客栈 - 英雄联盟阵亡助手", is_simulation=True)

def handle_respawn_event(cfg):
    add_log(f"触发复活事件！玩家已复活。")
    
    # Broadcast to Bilibili official extension if connected
    if len(extension_connections) > 0:
        add_log("发送 WebSocket 指令使 B站 官方网页静音。")
        broadcast_to_extension("mute")
        
    # Broadcast to dashboard websocket to mute Bilibili stream
    broadcast_event("respawn", {})
    
    # Focus League of Legends game window (or test window if in simulation)
    is_sim = cfg.get("is_simulation", True)
    test_title = cfg.get("test_window_title", "无标题 - 记事本")
    focus_target_window(test_title, is_simulation=is_sim)

# Polling loop for League of Legends game client
def lol_monitoring_loop():
    global game_status, player_status, summoner_name, prev_is_dead, is_first_check
    
    add_log("LOL 状态监控后台线程已启动。")
    
    while True:
        try:
            cfg = cached_config
            if not cfg.get("is_monitoring", True):
                time.sleep(cfg.get("polling_interval", 1.0))
                continue
                
            if cfg.get("is_simulation", True):
                # Simulated mode: Handled by manual API triggers. Just sleep.
                time.sleep(cfg.get("polling_interval", 1.0))
                continue
                
            # Real Mode: Scan for LOL client process
            lol_running = False
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == "league of legends.exe":
                        lol_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if not lol_running:
                if game_status != "not_running":
                    game_status = "not_running"
                    player_status = "unknown"
                    summoner_name = ""
                    prev_is_dead = False
                    is_first_check = True
                    add_log("英雄联盟游戏未运行。")
                    broadcast_state_change()
                time.sleep(cfg.get("polling_interval", 1.0))
                continue
                
            # LOL is running, pull active player data
            try:
                # Poll URL (using localhost API)
                response = requests.get(
                    "https://127.0.0.1:2999/liveclientdata/allgamedata",
                    verify=False,
                    timeout=1.0
                )
                if response.status_code == 200:
                    if game_status != "in_game":
                        game_status = "in_game"
                        add_log("已连接到英雄联盟对局 API！")
                        broadcast_state_change()
                        
                    data = response.json()
                    active_player = data.get("activePlayer", {})
                    all_players = data.get("allPlayers", [])
                    
                    # Extract active player name (summonerName or riotIdGameName)
                    act_name = active_player.get("summonerName", "")
                    if not act_name:
                        act_name = active_player.get("riotIdGameName", "")
                    
                    if act_name != summoner_name:
                        summoner_name = act_name
                        add_log(f"检测到召唤师姓名: {summoner_name}")
                        broadcast_state_change()
                        
                    # Find active player in players list
                    player_obj = None
                    for p in all_players:
                        p_name = p.get("summonerName", "")
                        if not p_name:
                            p_name = p.get("riotIdGameName", "")
                        if p_name == act_name:
                            player_obj = p
                            break
                            
                    if player_obj:
                        is_dead = player_obj.get("isDead", False)
                        p_status = "dead" if is_dead else "alive"
                        
                        if p_status != player_status:
                            player_status = p_status
                            add_log(f"玩家状态更新: {'[阵亡]' if is_dead else '[存活]'}")
                            
                            # Handle transitions
                            if not is_first_check:
                                if is_dead and not prev_is_dead:
                                    handle_death_event(cfg)
                                elif not is_dead and prev_is_dead:
                                    handle_respawn_event(cfg)
                            else:
                                is_first_check = False
                                
                            prev_is_dead = is_dead
                            broadcast_state_change()
                else:
                    if game_status != "loading":
                        game_status = "loading"
                        player_status = "unknown"
                        add_log("英雄联盟对局正在加载中...")
                        broadcast_state_change()
            except requests.exceptions.RequestException:
                if game_status != "loading":
                    game_status = "loading"
                    player_status = "unknown"
                    add_log("检测到游戏进程，但本地 API 暂未启动（可能处于加载界面）...")
                    broadcast_state_change()
            
            time.sleep(cfg.get("polling_interval", 1.0))
            
        except Exception as e:
            add_log(f"监控线程异常: {e}")
            time.sleep(1.0)

# FastAPI HTTP Endpoints
@app.on_event("startup")
async def startup_event():
    global async_loop
    async_loop = asyncio.get_running_loop()
    
    # Initialize logs
    add_log("应用启动完成。控制台地址: http://127.0.0.1:8000")
    
    # Start LOL monitoring thread
    monitor_thread = threading.Thread(target=lol_monitoring_loop, daemon=True)
    monitor_thread.start()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Read templates/index.html
    html_path = os.path.join("templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h3>Index.html not found. Check project setup.</h3>")

@app.get("/api/status")
async def get_status():
    return get_current_state_payload()

@app.post("/api/settings")
async def update_settings(settings: Settings):
    global cached_config
    cfg = {
        "room_id": settings.room_id,
        "polling_interval": settings.polling_interval,
        "is_monitoring": settings.is_monitoring,
        "is_simulation": settings.is_simulation,
        "test_window_title": settings.test_window_title
    }
    save_config(cfg)
    cached_config = cfg
    
    # If simulation mode is toggled, reset the state
    global game_status, player_status, summoner_name, prev_is_dead, is_first_check
    if settings.is_simulation:
        game_status = "in_game"
        summoner_name = "【模拟召唤师】"
        player_status = "alive"
        prev_is_dead = False
        is_first_check = False
    else:
        game_status = "not_running"
        summoner_name = ""
        player_status = "unknown"
        prev_is_dead = False
        is_first_check = True
        
    add_log(f"已更新配置. 模拟模式: {settings.is_simulation}, 监控开启: {settings.is_monitoring}")
    broadcast_state_change()
    return {"status": "success", "config": get_current_state_payload()}

@app.post("/api/simulate/action")
async def simulate_action(payload: dict):
    cfg = load_config()
    if not cfg.get("is_simulation", True):
        raise HTTPException(status_code=400, detail="当前处于真实运行模式，无法接收手动模拟事件。请先开启模拟模式。")
        
    action = payload.get("action")
    global player_status, prev_is_dead
    
    if action == "death":
        player_status = "dead"
        prev_is_dead = True
        add_log("【手动模拟】执行阵亡测试")
        handle_death_event(cfg)
        broadcast_state_change()
    elif action == "respawn":
        player_status = "alive"
        prev_is_dead = False
        add_log("【手动模拟】执行复活测试")
        handle_respawn_event(cfg)
        broadcast_state_change()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    return {"status": "success"}

@app.get("/api/debug/windows")
async def debug_windows():
    import win32gui
    wins = []
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                wins.append(title)
        return True
    try:
        win32gui.EnumWindows(cb, None)
    except Exception as e:
        wins.append(f"Error: {e}")
    return {"windows": wins}

@app.post("/api/test/open")
async def test_open():
    cfg = load_config()
    add_log("手动测试：调用系统打开直播间")
    handle_death_event(cfg)
    return {"status": "success"}

@app.post("/api/test/focus")
async def test_focus():
    cfg = load_config()
    is_sim = cfg.get("is_simulation", True)
    test_title = cfg.get("test_window_title", "无标题 - 记事本")
    add_log(f"手动测试：置顶目标窗口 (模拟={is_sim}, 窗口={test_title})")
    success = focus_target_window(test_title, is_simulation=is_sim)
    return {"status": "success", "success": success}

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    # Send current state upon connection
    await websocket.send_json({
        "type": "init",
        "state": get_current_state_payload()
    })
    add_log(f"网页控制台已连接 (当前连接数: {len(active_connections)})")
    
    try:
        while True:
            # Just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        # We don't call add_log inside disconnect to avoid recursion issue if logging fails
        print(f"网页控制台已断开连接 (当前连接数: {len(active_connections)})")
        broadcast_state_change()

# WebSocket Endpoint for Bilibili Official Page Extension
@app.websocket("/ws/extension")
async def websocket_extension_endpoint(websocket: WebSocket):
    await websocket.accept()
    extension_connections.add(websocket)
    add_log(f"B站官方直播间浏览器插件已连接")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in extension_connections:
            extension_connections.remove(websocket)
        print(f"B站官方直播间浏览器插件已断开连接")
