# 部署指南

## 1. 安裝 Python

只需要 Python 3.8 以上，**不需要安裝任何第三方套件**。

**Windows**：到 [python.org/downloads](https://www.python.org/downloads/) 下載安裝，
安裝畫面第一頁務必勾選 **「Add python.exe to PATH」**。

> ⚠ **Windows 10/11 內建一個「假的」python.exe。**
> 它位於 `WindowsApps` 資料夾，執行後只會打開 Microsoft Store，不能真的跑程式。
> 所以在命令提示字元打 `python` 有反應，**不代表** Python 已經裝好。
> `start.bat` 會實際執行一次來驗證，不會被這個假的騙過去。

**macOS**：內建通常已有 `python3`，若無則 `brew install python`。

如果醫院電腦禁止安裝軟體，請資訊室協助；Python 本身是免費開源，通常不難通過。

---

## 2. 放置檔案

把整個 `ntm-registry` 資料夾複製到這台電腦，路徑建議：

```
Windows:  C:\NTM\ntm-registry\
macOS:    ~/NTM/ntm-registry/
```

**路徑裡不要出現 OneDrive、Google Drive、Dropbox、iCloud** —— 那會讓資料自動上雲。

---

## 3. 建立設定檔

複製 `config.example.json` 成 `config.json`，預設值就是最安全的設定：

```json
{
  "host": "0.0.0.0",
  "port": 3001,
  "allowed_ips": ["*"],
  "session_hours": 12,
  "max_login_attempts": 5,
  "lockout_seconds": 300,
  "portal_url": "http://10.100.144.109:3000/index.html",
  "tb_url": "http://10.100.144.109:3000/TB主系統整合.html"
}
```

沒有 `config.json` 也能跑，程式會用同樣的預設值。
`portal_url` / `tb_url` 是「核而為一」入口頁與 TB 系統的位址，
會套用到側邊欄與衛教專區頁的連結；改位址只要動這個檔，不必改程式。

---

## 4. 第一次啟動

Windows 雙擊 `start.bat`；macOS/Linux 執行 `./start.sh`。
第一次會要求建立管理員帳號，之後開瀏覽器輸入 `http://127.0.0.1:3001/`。

建議把這個網址加到瀏覽器書籤。

---

## 5. 開機自動啟動

### Windows（工作排程器）

1. 開始功能表搜尋「工作排程器」
2. 右側「建立工作」
   - 一般：名稱 `NTM 個案資料庫`，勾選「不論使用者登入與否均執行」→ 若只在登入後用，
     選「只有使用者登入時才執行」比較簡單
   - 觸發程序：新增 → 「當電腦啟動時」（或「登入時」）
   - 動作：新增 → 啟動程式
     - 程式：`C:\Windows\System32\cmd.exe`
     - 引數：`/c "C:\NTM\ntm-registry\start.bat"`
     - 起始位置：`C:\NTM\ntm-registry`
   - 條件：取消勾選「僅於電腦使用 AC 電源時才啟動」

### macOS（launchd）

建立 `~/Library/LaunchAgents/tw.hospital.ntm.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>tw.hospital.ntm</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/你的帳號/NTM/ntm-registry/server.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/你的帳號/NTM/ntm-registry</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

```
launchctl load ~/Library/LaunchAgents/tw.hospital.ntm.plist
```

### Linux（systemd user service）

`~/.config/systemd/user/ntm.service`：

```ini
[Unit]
Description=NTM 個案資料庫

[Service]
WorkingDirectory=%h/NTM/ntm-registry
ExecStart=/usr/bin/python3 %h/NTM/ntm-registry/server.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```
systemctl --user enable --now ntm.service
```

---

## 6. 自動備份排程

### Windows：雙擊 `setup_backup.bat` 就好

```
setup_backup.bat            → 每天 18:00 自動備份
setup_backup.bat 12:30      → 改成每天 12:30
```

它會用 `schtasks` 建一個叫 **NTM_Backup** 的工作排程，
以目前登入的使用者身分執行，**不需要系統管理員權限**。
備份檔放在 `backups\`，檔名像 `ntm-20260824-180000.db`，只留最近 60 份。

其他相關指令：

| 想做的事 | 怎麼做 |
| --- | --- |
| 立刻備份一次 | 雙擊 `backup.bat` |
| 看排程還在不在 | 工作排程器 → 工作排程器程式庫 → `NTM_Backup` |
| 取消排程 | `schtasks /delete /tn NTM_Backup /f` |
| 還原 | `python tools\restore.py`（列出所有備份讓你挑） |

排程是「這台電腦、這個使用者」的：**電腦關機或沒登入就不會跑**。
所以每個月請看一次 `backups\` 裡最新一份的日期，確認排程真的有在動。

### macOS / Linux（cron）

```
crontab -e
```

加入：

```
0 18 * * * cd ~/NTM/ntm-registry && /usr/bin/python3 tools/backup.py --keep 60
```

### 還原演練（建議做一次）

備份沒還原過等於沒有備份。找個不忙的時間：

1. 關掉伺服器（黑色視窗按 Ctrl+C）
2. `python tools\restore.py` → 挑一份 → 輸入 `yes`
   （目前的資料庫會先被另存成 `data\ntm-取代前-時間.db`，按錯救得回來）
3. 重新啟動 `start.bat`，登入看個案數對不對

### 備份要放哪裡

`backups\` 跟資料庫在同一顆硬碟 —— 硬碟壞掉時兩份一起沒了。
**每個月請把最新一份複製到院內核可的加密外接碟**，這才是真正的備援。
不要放 OneDrive / Google Drive / Dropbox，那等於把個案資料上雲。

---

## 7. 開放給科內其他電腦（目前的預設設定）

目前預設已經是開放院內網路連線（`host: "0.0.0.0"`、`allowed_ips: ["*"]`）。
**請先跟資訊室報備**，並完成以下設定，其他電腦才真的連得到。

### 步驟

1. 查出這台電腦的內網 IP
   - Windows：`ipconfig`，看「IPv4 位址」
   - macOS/Linux：`ip addr` 或 `ifconfig`
2. 請資訊室把這個 IP 設成**固定 IP**（DHCP 換 IP 會讓設定失效）
3. 修改 `config.json`：

```json
{
  "host": "10.1.2.34",
  "port": 3001,
  "allowed_ips": ["127.0.0.1", "10.1.2.35", "10.1.2.36", "10.1.2.37"]
}
```

`allowed_ips` 要把**每一台**允許連線的電腦 IP 都列出來。不在名單上的一律 403。

4. 開防火牆連接埠（Windows PowerShell，需系統管理員）：

```powershell
New-NetFirewallRule -DisplayName "NTM Registry" -Direction Inbound `
  -LocalPort 3001 -Protocol TCP -Action Allow `
  -RemoteAddress 10.1.2.35,10.1.2.36,10.1.2.37
```

`-RemoteAddress` 再限縮一次來源，跟 `allowed_ips` 形成雙重防護。

5. 其他電腦用 `http://10.1.2.34:3001/` 連線。

### 這個模式下務必知道

- 連線是 **HTTP 明文**，密碼與資料在院內網路上是可被側錄的。
  若要跨電腦使用，應該請資訊室協助架設 HTTPS，或改用 VPN / 院內既有的加密通道。
- 單機模式（`127.0.0.1`）沒有這個問題，因為流量從未離開這台電腦。
- **建議：真的要多人共用，就走資訊室的正式流程，不要用這個模式長期營運。**

---

## 8. 疑難排解

**「python 不是內部或外部命令」**
Python 沒裝，或安裝時沒勾 Add to PATH。重裝並勾選該選項。

**畫面顯示「使用 python 啟動中」後立刻失敗，卻沒有任何錯誤訊息**
八成是踩到 Windows 內建的 Microsoft Store 假 python.exe（見第 1 節的警告）。
到 python.org 安裝真正的 Python，安裝時勾選 Add python.exe to PATH。

**連接埠被占用（`Address already in use`）**
另一個程式在用 3001。改 `config.json` 的 `port`（例如 3002），或用
`python server.py --port 3002` 臨時指定。

**瀏覽器顯示「此網站僅限本機使用」**
來源 IP 不在 `allowed_ips` 白名單內。這是正常的防護行為。

**忘記密碼（任何帳號，含管理員）**
在這台電腦上雙擊 `reset_password.bat`，它會先列出所有帳號，
輸入帳號後直接設定新密碼 —— **不需要舊密碼**，因為能操作這台電腦的人
本來就讀得到資料庫，問舊密碼並不會多一層保護。
指令版：`python tools/manage_user.py passwd <帳號>`。
改完該帳號在其他電腦的既有登入會一併失效，要用新密碼重新登入。

如果連「有哪些帳號」都忘了：`python tools/manage_user.py list`。
萬一所有管理員帳號都進不去，再開一個新的管理員即可：
`python tools/manage_user.py add <新帳號> --role admin`。

**資料庫鎖住（`database is locked`）**
同時有備份或其他程式在寫入。等幾秒重試；若持續發生，確認沒有重複啟動兩個伺服器。

**想搬到新電腦**
複製整個 `ntm-registry` 資料夾（含 `data/`）過去即可，SQLite 是跨平台的單一檔案。
搬完記得把舊電腦的資料**安全刪除**，不是丟到資源回收筒。
