# 🏠 搬家包：把工具网站搬到家里的迷你主机

搬完以后：

- 网站只有你自己的手机和电脑能打开（通过 Tailscale），外人根本看不到。
- 股价提醒、网页监控都存在家里。触发时用自己架设的 ntfy 推送到手机，不再经过 GitHub。
- 语境词库进度、自选股、购物清单会在手机和电脑之间自动同步（以前是各存各的）。
- 数据任务（股票池、财报、新闻、打折、电台、网页监控）在主机上按原来的时间自动跑。

## 需要准备

- 一台迷你主机，装 **Ubuntu Server 24.04 LTS**。安装时勾选 **Install OpenSSH server**。
- 第一次装系统时，接一下屏幕和键盘（电视的 HDMI 口就行）。装完就可以拔掉，以后都用手机管理。
- 手机上装两个 App：**Tailscale** 和 **ntfy**（都在 Google Play）。

## 安装（大约 15 分钟）

用手机上的 Termux（或 Termius）登录主机：`ssh 你的用户名@主机的局域网IP`，然后运行：

```bash
git clone https://github.com/boliunew/tools.git ~/tools
bash ~/tools/selfhost/install.sh
```

中间有两处需要你点一下：

1. **登录 Tailscale**：屏幕上会出现一个链接，用手机打开并登录，要和手机上 Tailscale App 用同一个账号。
2. **开启 HTTPS**（只在第一次出现）：Tailscale 会提示打开一个链接，在里面点 Enable。

装完后屏幕上会显示你的网站地址，类似 `https://minipc.xxxx.ts.net`。

## 装好之后

1. **手机打开网站**：先打开 Tailscale App 连上，再在浏览器里输入上面的地址，然后「添加到主屏幕」。
2. **订阅推送**：打开 ntfy App → ＋ → 勾选 Use another server → 填安装结束时显示的订阅地址。网站里的「📬 通知中心」页面也能看到这个地址。
3. **搬旧数据**：
   - 在旧网站（GitHub 上那个）打开「🧳 搬家」页面，点「导出全部进度」→ 复制。
   - 在新网站打开「🧳 搬家」页面，粘贴 → 导入。
   - 词库进度、自选股、购物清单就都过来了，而且之后会在各设备间同步。
4. **股价提醒**：在股票池的自选股旁边点 🔔，选好条件后点「✅ 设好提醒」。不用再去 GitHub。
5. 确认一切正常后，**关掉 GitHub 上的旧网站**：
   - 打开 GitHub 仓库 → Settings → Pages → 关闭；Actions → 每个定时任务点 Disable workflow。
   - 再把仓库改成 Private（Settings → General → 最下面 Change visibility）。代码还在，相当于免费备份。
   - 注意：如果仓库改成私有，以后在主机上运行 `update.sh` 拉代码时，需要登录 GitHub（或换成个人访问令牌）。

## 日常管理（用手机 SSH 登录后）

| 想做什么 | 命令 |
|---|---|
| 看定时任务下次什么时候跑 | `systemctl list-timers 'tools-*'` |
| 马上跑一次某个任务 | `~/tools/selfhost/run-job.sh stocks`（stocks / earnings / news / deals / radio / monitor / all） |
| 看某个任务的日志 | `tail -n 50 ~/tools/.local-data/logs/stocks.log` |
| 网页服务的日志 | `sudo journalctl -u tools-web -n 50` |
| 更新到最新代码 | `~/tools/selfhost/update.sh` |
| 重启网页服务 | `sudo systemctl restart tools-web` |

定时任务失败时，ntfy 会推送一条「tools job failed」，并附上最后几行日志。

## 隐私：哪些东西还会出门

- **会出门的**：主机会去 Yahoo Finance、Nasdaq、Flipp、新闻网站、维基百科这些公开网站拿数据。发出去的只是「给我某只股票的价格」这类公开请求，不带你的个人信息。电台的语音合成用的是微软 Edge 的在线朗读，朗读的内容是新闻和单词。
- **不会出门的**：你的自选股、提醒条件、词库进度、购物清单、监控的网页、推送内容，都只在你家主机和你自己的设备上。
- **网站本身**：服务只监听本机（127.0.0.1），只能通过 Tailscale 访问。家里局域网的其他设备、外网都打不开。

## 文件说明

| 文件 | 作用 |
|---|---|
| `install.sh` | 一键安装，可以重复运行 |
| `server.py` | 网页服务，加上同步、提醒、监控的接口 |
| `localgh.py` | 本地版「issue」，原来存在 GitHub 上的提醒和监控改存在这里，留言就是推送 |
| `run-job.sh` | 跑数据任务（和原来 GitHub Actions 的步骤一样） |
| `update.sh` | 更新代码，同时保留家里产生的数据 |
| `config.env` | 安装时生成的设置（推送地址等），不进 git |
| `../.local-data/` | 同步数据、提醒记录、日志，不进 git |
