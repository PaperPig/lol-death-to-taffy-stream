# lol-death-to-taffy-stream (英雄联盟阵亡自动跳转永雏塔菲直播间助手)

An automatic window-focus and volume controller for League of Legends that auto-opens/unmutes VTuber Taffy's Bilibili livestream when you die in-game, and auto-mutes & restores focus to the game window when you respawn.

这是一个专为英雄联盟玩家与永雏塔菲粉丝设计的智能对局助手：对局中角色死亡自动唤起/解静音 VTuber 永雏塔菲的 B站 官方直播间，复活时自动静音直播并秒切回游戏窗口。包含配套轻量级浏览器静音控制插件。

---

## ✨ 核心特性 (Key Features)

*   **🎮 官方直播网页直接控制**：配套轻量级浏览器扩展程序（Extension），可直接控制官方直播页面 `https://live.bilibili.com/22603245` 里的 HTML5 播放器，完美支持弹幕、送礼、粉丝牌等官方网页的所有功能。
*   **⚡ 毫秒级原生 `ctypes` 窗口置顶**：移除所有导致明显卡顿的全局进程扫描，改用底层纯 Windows `ctypes` 接口，窗口聚焦速度提升至 **2ms 级**。
*   **🔑 Alt 键模拟欺骗机制**：置顶切换时自动模拟按下/释放 Alt 键，突破 Windows 操作系统对后台进程“抢占焦点”的限制，实现无视状态的 100% 强行置顶。
*   **📦 极速内存轮询缓存**：将 Live Client API 扫描速度提速至 **$10\text{ Hz}$** (每秒 10 次检查)，数据完全使用全局内存缓存进行高频交互，实现**磁盘零 I/O 读写**。
*   **📺 影院级独立 App 模式**：冷启动直播时自动识别 Chrome/Edge 并以独立的 `--app` 模式（应用窗口）拉起，不仅精美无边框，还能**彻底规避**浏览器产生多余“新建标签页”空白页的 Bug。
*   **🧪 完善的模拟测试面板**：提供隐藏式推拉控制面板，支持“一键模拟死亡/复活”进行无游戏联调测试，支持自定义测试窗口（如记事本）。

---

## 🛠️ 安装与部署指南 (Installation & Setup)

### 1. 准备环境
运行本助手需要安装以下 Python 第三方库：
```bash
pip install fastapi uvicorn requests psutil pydantic
```

### 2. 安装浏览器插件（仅需一次）
由于浏览器的同源策略限制，直接访问 B站 需要借助配套的轻量级插件：
1. 打开 Chrome 浏览器（或 Edge 浏览器），地址栏输入 `chrome://extensions/`（Edge 为 `edge://extensions/`）。
2. 在右上角**开启“开发者模式” (Developer Mode)**。
3. 点击左上角的 **“加载已解压的扩展程序” (Load unpacked)**。
4. 选择本项目根目录下的 **`taffy-extension`** 文件夹，载入成功即可。

### 3. 运行服务
在项目根目录启动命令行窗口，执行以下指令即可启动服务：
```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🚀 使用方法 (How to Use)

1. **进入官方直播间**：启动服务后，使用装有该插件的浏览器直接打开 B站 官方直播间：
   [https://live.bilibili.com/22603245](https://live.bilibili.com/22603245)
   *(命令行会提示：`B站官方直播间浏览器插件已连接`，代表联调成功)*
2. **测试连接**：
   - 访问本地控制中心：`http://127.0.0.1:8000`。
   - 鼠标滑向右上角，点击 **⚙️（齿轮）** 弹出控制台。
   - 保持“模拟测试模式”开启。打开一个记事本，在控制面板中输入记事本标题（如 `无标题 - 记事本`），点击保存。
   - 点击 **💀 模拟阵亡**：官方直播间窗口瞬间置顶并响起声音。
   - 点击 **💖 模拟复活**：记事本窗口瞬间被拉回屏幕最前端并获取焦点，官方直播间静音。
3. **真实对局**：
   - 调试无误后，在控制面板中**取消勾选“模拟测试模式”**并保存。
   - 开启一局 LOL 游戏（人机/大乱斗/匹配均可），助手会自动监控对局状态，带您体验角色死亡时全自动跳转大屏看塔菲直播、复活自动静音切回游戏的完美联动！

---

## 📝 许可证 (License)

This project is licensed under the MIT License - see the LICENSE file for details.
本程序仅用于学习交流及娱乐，严禁用于任何商业用途。
