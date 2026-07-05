console.log("%c[永雏客栈] B站官方直播控制插件已加载", "color: #ff69b4; font-weight: bold;");

let ws = null;

function connect() {
    // 连接本地 Python 后台的插件专用 WebSocket 端口
    ws = new WebSocket("ws://127.0.0.1:8000/ws/extension");

    ws.onopen = () => {
        console.log("%c[永雏客栈] 成功连接到助手后台！监听指令中...", "color: #00ff00; font-weight: bold;");
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log("[永雏客栈] 收到控制指令:", data.action);
            
            // 找到页面上所有的 <video> 标签进行控制，防止 B站 嵌套播放器
            const videos = document.querySelectorAll("video");
            if (videos.length > 0) {
                videos.forEach((video) => {
                    if (data.action === "mute") {
                        video.muted = true;
                    } else if (data.action === "unmute") {
                        video.muted = false;
                    }
                });
                console.log(`[永雏客栈] 已成功执行 ${data.action === "mute" ? "静音" : "开启声音"}。`);
            } else {
                console.warn("[永雏客栈] 未在当前页面找到视频播放器元素！");
            }
        } catch (e) {
            console.error("[永雏客栈] 执行控制指令出错:", e);
        }
    };

    ws.onclose = () => {
        console.warn("[永雏客栈] 与助手后台的连接已断开，3秒后尝试自动重连...");
        setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
        ws.close();
    };
}

// 启动连接
connect();
