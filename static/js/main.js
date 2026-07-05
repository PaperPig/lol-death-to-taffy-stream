// State variables
let socket = null;
let currentRoomId = "";
let currentMuteState = 1; // 1 = muted, 0 = unmuted
let isFirstLoad = true;

// DOM Elements
const wsBadge = document.getElementById("ws-badge");
const taffyAvatar = document.getElementById("taffy-avatar");
const gameStatusVal = document.getElementById("game-status-val");
const playerStatusVal = document.getElementById("player-status-val");
const summonerNameVal = document.getElementById("summoner-name-val");
const consoleOutput = document.getElementById("console-output");
const streamSoundStatus = document.getElementById("stream-sound-status");

// Buttons & Controls
const btnSimDeath = document.getElementById("btn-sim-death");
const btnSimRespawn = document.getElementById("btn-sim-respawn");
const btnTestOpen = document.getElementById("btn-test-open");
const btnTestFocus = document.getElementById("btn-test-focus");
const btnClearLogs = document.getElementById("btn-clear-logs");
const simControls = document.getElementById("sim-controls");

// Settings Form
const settingsForm = document.getElementById("settings-form");
const roomIdInput = document.getElementById("room_id");
const pollingInput = document.getElementById("polling_interval");
const windowTitleInput = document.getElementById("test_window_title");
const isMonitoringInput = document.getElementById("is_monitoring");
const isSimulationInput = document.getElementById("is_simulation");

// Check if page was opened via death trigger (autoplay url param)
const urlParams = new URLSearchParams(window.location.search);
let shouldAutoplay = urlParams.get("autoplay") === "1";

// Clean up URL history so refreshing doesn't trigger autoplay again
if (shouldAutoplay) {
    const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
    window.history.replaceState({ path: cleanUrl }, '', cleanUrl);
}

// Initialize WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    wsBadge.innerHTML = `<span class="dot"></span><span class="text">正在连接...</span>`;
    wsBadge.className = "status-badge";
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        wsBadge.innerHTML = `<span class="dot"></span><span class="text">已连接</span>`;
        wsBadge.className = "status-badge connected";
        addLocalLog("成功连接到后台 WebSocket 服务。");
    };
    
    socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        handleServerPayload(payload);
    };
    
    socket.onclose = () => {
        wsBadge.innerHTML = `<span class="dot"></span><span class="text">断开连接</span>`;
        wsBadge.className = "status-badge";
        addLocalLog("与后台的 WebSocket 连接已断开，正在尝试重连...");
        setTimeout(connectWebSocket, 3000);
    };
}

// Handle WebSocket payloads
function handleServerPayload(payload) {
    const state = payload.state;
    
    if (payload.type === "init") {
        // Load initial logs
        consoleOutput.innerHTML = "";
        if (state.logs) {
            state.logs.forEach(log => {
                appendLogElement(log);
            });
        }
        
        // Populate settings
        roomIdInput.value = state.room_id;
        pollingInput.value = state.polling_interval;
        windowTitleInput.value = state.test_window_title;
        isMonitoringInput.checked = state.is_monitoring;
        isSimulationInput.checked = state.is_simulation;
        
        currentRoomId = state.room_id;
        
        // Handle stream initial load mute state
        if (isFirstLoad) {
            let initialMute = 1; // Default to muted
            if (shouldAutoplay || state.player_status === "dead") {
                initialMute = 0; // Unmuted
            }
            updatePlayerIframe(state.room_id, initialMute);
            isFirstLoad = false;
        }
    }
    
    // Process server logs
    if (payload.type === "event" && payload.event === "log") {
        appendLogElement(payload.data.log);
    }
    
    // Update State UI
    if (state) {
        updateStateUI(state);
    }
    
    // Handle Event Triggers (death / respawn)
    if (payload.type === "event") {
        if (payload.event === "death") {
            addLocalLog("⚡ 收到阵亡通知，正在开启声音播放！");
            updatePlayerIframe(state.room_id, 0); // Unmute
        } else if (payload.event === "respawn") {
            addLocalLog("🛡️ 收到复活通知，静音网页直播。");
            updatePlayerIframe(state.room_id, 1); // Mute
        }
    }
}

// Update State UI elements
function updateStateUI(state) {
    // Game Status
    if (state.game_status === "not_running") {
        gameStatusVal.textContent = "未检测到游戏";
        gameStatusVal.className = "value badge";
    } else if (state.game_status === "loading") {
        gameStatusVal.textContent = "对局加载中...";
        gameStatusVal.className = "value badge warning";
    } else if (state.game_status === "in_game") {
        gameStatusVal.textContent = "游戏对局中";
        gameStatusVal.className = "value badge success";
    }
    
    // Player Status & Avatar
    const avatarParent = taffyAvatar.parentElement;
    if (state.player_status === "dead") {
        playerStatusVal.textContent = "阵亡";
        playerStatusVal.className = "value badge danger";
        taffyAvatar.src = "/static/img/taffy_sad.png";
        avatarParent.className = "avatar-container dead";
    } else if (state.player_status === "alive") {
        playerStatusVal.textContent = "存活";
        playerStatusVal.className = "value badge success";
        taffyAvatar.src = "/static/img/taffy_happy.png";
        avatarParent.className = "avatar-container alive";
    } else {
        playerStatusVal.textContent = "未知";
        playerStatusVal.className = "value badge";
        taffyAvatar.src = "/static/img/taffy_happy.png";
        avatarParent.className = "avatar-container";
    }
    
    // Summoner Name
    summonerNameVal.textContent = state.summoner_name || "-";
    
    // Update Standby Status Text
    const standbyStatusText = document.getElementById("standby-status-text");
    if (standbyStatusText) {
        if (state.is_simulation) {
            standbyStatusText.textContent = "模拟调试模式已就绪，等待手动触发阵亡...";
        } else if (state.game_status === "not_running") {
            standbyStatusText.textContent = "等待英雄联盟游戏客户端启动...";
        } else if (state.game_status === "loading") {
            standbyStatusText.textContent = "英雄联盟对局加载中，等待对局开始...";
        } else if (state.game_status === "in_game") {
            standbyStatusText.textContent = `${state.summoner_name || "召唤师"} 对局中 | 正在监控存活状态...`;
        }
    }
    
    // Hide/show simulation panel
    if (state.is_simulation) {
        simControls.style.display = "block";
    } else {
        simControls.style.display = "none";
    }
}

// Update iframe safely
function updatePlayerIframe(roomId, muteState) {
    const player = document.getElementById("bilibili-player");
    let targetSrc;
    
    if (muteState === 1) {
        // Mute / Respawn: Unload iframe completely to silence audio and save system resources
        targetSrc = "about:blank";
        const standby = document.getElementById("standby-screen");
        if (standby) standby.classList.remove("hidden");
    } else {
        // Unmute / Death: Load Bilibili live player unmuted, autoplayed and with live chat (danmaku=1)
        targetSrc = `https://www.bilibili.com/blackboard/live/live-activity-player.html?cid=${roomId}&autoplay=1&mute=0&logo=0&danmaku=1`;
        const standby = document.getElementById("standby-screen");
        if (standby) standby.classList.add("hidden");
    }
    
    if (player.src !== targetSrc) {
        player.src = targetSrc;
        currentMuteState = muteState;
        currentRoomId = roomId;
        
        if (muteState === 0) {
            streamSoundStatus.textContent = "🔊 直播正在播放 (有声)";
            streamSoundStatus.className = "stream-status unmuted";
        } else {
            streamSoundStatus.textContent = "🔇 已静音 (复活卸载)";
            streamSoundStatus.className = "stream-status";
        }
    }
}

// Log formatting helpers
function appendLogElement(logText) {
    const div = document.createElement("div");
    div.textContent = logText;
    
    // Simple coloring based on text
    if (logText.includes("阵亡")) {
        div.style.color = "var(--color-danger)";
    } else if (logText.includes("复活")) {
        div.style.color = "var(--color-success)";
    } else if (logText.includes("成功连接")) {
        div.style.color = "var(--color-blue)";
    } else if (logText.includes("激活窗口")) {
        div.style.color = "var(--color-warning)";
    }
    
    consoleOutput.appendChild(div);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function addLocalLog(message) {
    const timestamp = new Date().toTimeString().split(' ')[0];
    appendLogElement(`[${timestamp}] ${message}`);
}

// Button Events / Fetch APIs
btnSimDeath.addEventListener("click", () => {
    fetch("/api/simulate/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "death" })
    });
});

btnSimRespawn.addEventListener("click", () => {
    fetch("/api/simulate/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "respawn" })
    });
});

btnTestOpen.addEventListener("click", () => {
    fetch("/api/test/open", { method: "POST" });
});

btnTestFocus.addEventListener("click", () => {
    fetch("/api/test/focus", { method: "POST" });
});

btnClearLogs.addEventListener("click", () => {
    consoleOutput.innerHTML = "";
    addLocalLog("日志控制台已清空。");
});

// Settings Form Submission
settingsForm.addEventListener("submit", (e) => {
    e.preventDefault();
    
    const settings = {
        room_id: roomIdInput.value,
        polling_interval: parseFloat(pollingInput.value),
        test_window_title: windowTitleInput.value,
        is_monitoring: isMonitoringInput.checked,
        is_simulation: isSimulationInput.checked
    };
    
    // Save settings
    fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings)
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "success") {
            addLocalLog("配置保存成功！正在应用新配置...");
            // Update player room if changed
            updatePlayerIframe(settings.room_id, currentMuteState);
        }
    })
    .catch(err => {
        addLocalLog(`保存配置出错: ${err}`);
    });
});

// Sidebar Panel toggle
const settingsTrigger = document.getElementById("settings-trigger");
const btnClosePanel = document.getElementById("btn-close-panel");
const slidePanel = document.getElementById("slide-panel");

settingsTrigger.addEventListener("click", () => {
    slidePanel.classList.toggle("open");
});

btnClosePanel.addEventListener("click", () => {
    slidePanel.classList.remove("open");
});

// Start WS connection
connectWebSocket();
