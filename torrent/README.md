# 🧲 种子下载器 · 边下边播

在自己电脑上跑的网页版下载器，一个 Python 文件。

- 磁力链接、.torrent 文件/网址、http/https/ftp 直链、迅雷 thunder://、QQ旋风 qqdl://、快车 flashget:// 都能加
- 每个任务都有「▶ 直接播」：边下边播，拖进度条会优先下载那一段；带字幕文件的自动加载字幕
- 浏览器放不了的格式（H.265/HEVC、AC3/DTS 音轨等），一键交给电脑上的 VLC / PotPlayer / mpv，或者复制串流地址到手机 VLC
- 关掉再开会接着下

## 用法

```
pip install libtorrent
python torrent_hub.py          # 浏览器打开 http://127.0.0.1:8800
python torrent_hub.py --lan    # 同一个 Wi-Fi / Tailscale 里的手机也能打开、能播
python torrent_hub.py --dir D:\Downloads --port 9000
```

Windows 上也可以直接双击 `启动种子下载器.bat`。

进度和设置存在 `~/.torrent_hub/`。直链任务关掉程序后不会自动恢复，重新粘贴一次就会接着下。
