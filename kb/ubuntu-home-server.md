---
title: 把 Ubuntu 当家里的小服务器
tags: [科技, Ubuntu]
summary: 让 Ubuntu 电脑 24 小时开着干活：用 systemd 做开机自启服务、跑本地网站、提供内网文件服务，以及别把端口暴露到公网的安全提醒。
---

# 把 Ubuntu 当家里的小服务器

一台不怎么关机的 Ubuntu 电脑，放着也是放着，不如让它干点活：跑个本地网站、共享文件、定时备份。要求不高——能开机自启、能在局域网里访问、别给外网留口子就行。这篇以"跑一个本地网站"为例，把 systemd 服务从头到尾做一遍。

## systemd 服务：让程序开机自己跑

systemd 是 Ubuntu 的服务管理器，开机自启、崩溃重启、看日志都归它管。举个例子：把 `~/tools` 里的静态网站用 Python 自带的简易服务器跑在 8000 端口。

先确认你的用户名（服务文件里要用到）：

```bash
whoami
```

写服务文件（`$USER` 会自动换成你的用户名）：

```bash
sudo tee /etc/systemd/system/tools-site.service > /dev/null <<EOF
[Unit]
Description=Tools 本地网站
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/tools
ExecStart=/usr/bin/python3 -m http.server 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
```

关键几行：`WorkingDirectory` 是网站文件所在目录，`ExecStart` 是启动命令，`Restart=on-failure` 是崩了自动重启。让 systemd 读到新服务并启动：

```bash
sudo systemctl daemon-reload
```

```bash
sudo systemctl enable --now tools-site
```

`enable` 是开机自启，`--now` 是现在就启动。看它跑起来没有：

```bash
systemctl status tools-site
```

看到 `active (running)` 就是跑起来了。在浏览器打开 `http://localhost:8000`，应该能看到 `~/tools` 里的网站。想在终端里快速测一下（curl 在《装好之后先做的事》里装过）：

```bash
curl -I http://localhost:8000
```

返回 `HTTP/1.0 200 OK` 就是通的。看运行日志（排错就靠它）：

```bash
sudo journalctl -u tools-site -f
```

按 `Ctrl+C` 退出。停掉服务、取消自启：

```bash
sudo systemctl stop tools-site
```

```bash
sudo systemctl disable tools-site
```

> 服务文件改了之后，要先 `sudo systemctl daemon-reload` 再 `restart`，否则改动不生效。服务名（`tools-site`）和文件名（`tools-site.service`）要对应，命令里写服务名时 `.service` 可以省略。

## 局域网里访问：先测通，再谈别的

本机能打开 `http://localhost:8000` 之后，局域网里的手机、笔记本用 `http://<Ubuntu 的 IP>:8000` 访问。先查 IP：

```bash
hostname -I
```

如果别的设备打不开，按这个顺序查：

| 查什么 | 怎么做 |
|---|---|
| 服务在跑吗 | `systemctl status tools-site` 看是不是 active |
| 防火墙放行了吗 | 下面 `sudo ufw allow 8000/tcp` |
| IP 对吗 | `hostname -I` 重新确认，IP 可能变了 |
| 网络本身通吗 | 从手机 ping 一下 Ubuntu 的 IP（很多路由器开"AP 隔离"时设备之间互相看不见） |

最后一条最容易被忽略：有些网络（比如合租、宿舍、公司 Wi-Fi）开了 AP 隔离，设备之间根本连不通，这时候不是服务器的问题，换手机热点或 USB 共享网络就能验证。

想让 IP 固定不变，去路由器后台把这台电脑的 IP 设为静态分配（DHCP 保留），不同路由器菜单位置不一样，搜"路由器型号 + DHCP 保留"就行。

## 内网文件服务：不用重复造轮子

文件共享不需要新装什么，前面文章里讲过的两样直接用：

| 需求 | 用什么 | 在哪篇 |
|---|---|---|
| Windows、手机打开共享文件夹 | Samba | [远程连接与局域网共享](ubuntu-remote-sharing.md) |
| 加密传文件 | SFTP（SSH 自带） | [远程连接与局域网共享](ubuntu-remote-sharing.md) |

服务跑起来之后，记得它也是个"小服务器"了：重要数据要备份，思路见[家里主机的备份方案](homelab-backup.md)。

## 安全提醒：三条红线

**1. 别把端口暴露到公网。**局域网里跑服务很安全，但千万别去路由器上做端口转发、把 22 或 8000 端口映射到公网——一旦暴露，全网的扫描器几分钟内就会开始试你的 SSH 密码。真想从外网访问，先学 Tailscale 或 WireGuard 这类内网穿透工具（只对你自己的设备开放），不要直接开端口。

**2. 防火墙只开必要的端口。**默认拒绝所有入站，只放行你明确需要的：

```bash
sudo ufw enable
```

```bash
sudo ufw allow 22/tcp
```

```bash
sudo ufw allow 8000/tcp
```

```bash
sudo ufw status
```

`ufw status` 能看到当前放行了哪些端口，定期看一眼，不用的就 `sudo ufw delete allow 8000/tcp` 关掉。

**3. SSH 关掉密码登录（只留密钥）。**前提是你已经配好密钥登录（见[远程连接与局域网共享](ubuntu-remote-sharing.md)）并且确认不用密码能登上。满足条件后：

```bash
echo "PasswordAuthentication no" | sudo tee /etc/ssh/sshd_config.d/60-disable-password.conf
```

```bash
sudo systemctl reload ssh
```

> 操作顺序很重要：先在**新开一个终端**里测试密钥登录能用，再关密码登录；不要关掉当前这个 SSH 连接——万一密钥有问题，当前连接还在，还能改回来。

另外可以装 fail2ban，自动封禁反复试密码的 IP：

```bash
sudo apt install fail2ban
```

装好默认就启用，不用额外配置。系统安全更新 Ubuntu 默认会自动安装（unattended-upgrades），不用管。

## 相关阅读

- [远程连接与局域网共享](ubuntu-remote-sharing.md)：SSH 密钥登录、Samba 文件共享
- [出问题了怎么办](ubuntu-troubleshooting.md)：服务起不来时看 `journalctl -u 服务名`
- [家里主机的备份方案（3-2-1、restic、自动化）](homelab-backup.md)：服务器数据的备份思路
- [家庭网络基础](home-network-basics.md)：局域网、IP、路由器这些概念的入门
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读

## 来源/延伸阅读

- systemd 官方文档：https://systemd.io/
- Ubuntu Server 指南（服务、安全）：https://documentation.ubuntu.com/server/
- Tailscale（安全的远程访问方案）：https://tailscale.com/
