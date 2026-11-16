---
title: 出问题了怎么办
tags: [科技, Ubuntu]
summary: 没网、没声音、磁盘满了、软件装不上、图形界面黑屏、忘记密码——按症状找排查步骤，再加一个万能的看日志方法。
---

# 出问题了怎么办

这篇是手册，不是教程：出了问题直接按症状翻到对应的一节，按步骤往下查，不用从头读。开始之前先记住排查的通用思路：

1. **先看报错原文。**报错信息是最好的线索，整段复制去搜索，九成的问题别人都遇到过。
2. **一次只改一个地方。**同时改好几处，好了也不知道是哪一步起的作用。
3. **改配置前先备份。**`sudo cp 原文件 原文件.bak`，改坏了能恢复。
4. **先看日志再动手。**日志在文末有专门一节，查不下去的时候就去看日志。

## 没网了

先确认是"网线/Wi-Fi 没连上"还是"连上了但打不开网页"：

```bash
ip a
```

```bash
ping -c 3 1.1.1.1
```

```bash
ping -c 3 www.ubuntu.com
```

`ip a` 看网卡有没有拿到 IP 地址（`inet 192.168.x.x` 这样的行）；`ping 1.1.1.1` 通、但 `ping www.ubuntu.com` 不通，是 DNS 的问题；两个都不通，是网络本身的问题。

| 现象 | 先试什么 |
|---|---|
| 网卡没有 IP | 检查网线 / Wi-Fi 是否连上；`nmcli device status` 看设备状态 |
| 能 ping IP、不能 ping 域名 | DNS 问题，`resolvectl status` 看 DNS 配置，重启网络服务 |
| 之前好好的突然不行 | 重启 NetworkManager（下面这条），再不行重启电脑 |

```bash
nmcli device status
```

```bash
resolvectl status
```

```bash
sudo systemctl restart NetworkManager
```

> 虚拟机里没网多半是虚拟机的网络模式问题（NAT / 桥接），先在虚拟机设置里确认；双系统下 Windows 开了"快速启动"会导致 Ubuntu 下网卡异常，进 Windows 关掉快速启动再试。

## 没声音了

先看最简单的：系统设置 → 声音 → 输出设备选对了没有（HDMI 显示器会抢走默认输出，改回内置扬声器或耳机）。没解决再往下查。

装个图形化的音量控制，看看声音到底输出到哪了：

```bash
sudo apt install pavucontrol
```

打开 pavucontrol，在"输出设备"和"播放"两个标签里确认输出设备和音量。还不行就重启声音服务（24.04 用的是 PipeWire）：

```bash
systemctl --user restart pipewire pipewire-pulse
```

再不行看声卡有没有被静音：

```bash
alsamixer
```

在 alsamixer 里用方向键选到 Master，按 `M` 取消静音（`MM` 是静音，`OO` 是有声），按 `Esc` 退出。

> 24.04 和 22.04 的差别：24.04 默认声音系统是 PipeWire，22.04 默认是 PulseAudio。网上老教程里 `pulseaudio -k`、`systemctl --user restart pulseaudio` 这种命令在 24.04 上不适用，照着上面 PipeWire 的办法来。

## 磁盘满了

先看满的是哪个分区：

```bash
df -h
```

再看是哪个目录占的地方：

```bash
sudo du -sh /* 2>/dev/null | sort -h
```

最大的在最下面。常见的清理目标：

```bash
sudo apt clean
```

```bash
sudo apt autoremove
```

```bash
sudo journalctl --vacuum-size=100M
```

`apt clean` 清安装包缓存，`autoremove` 清没用的依赖，`journalctl --vacuum-size` 把日志压到 100MB 以内。还有 Snap 的旧版本、浏览器缓存、回收站（图形界面清空或 `rm -rf ~/.local/share/Trash/*`）。如果 `/home` 是被某个大文件占满的，用 `ncdu ~` 图形化找（见[每天用得到的技巧](ubuntu-daily-tips.md)）。

> 磁盘满到 100% 时图形界面可能直接进不去（登录后闪退或黑屏）。这时候按 `Ctrl+Alt+F3` 进文字终端，登录后清掉一些文件再重启，见下面黑屏一节。

## 软件装不上

最常见的是软件列表太旧，先刷新：

```bash
sudo apt update
```

```bash
sudo apt install vlc
```

如果提示 `dpkg was interrupted`（上次安装被打断），先修复：

```bash
sudo dpkg --configure -a
```

如果提示依赖问题：

```bash
sudo apt -f install
```

如果提示 `Could not get lock`，是另一个 apt 正在运行（比如系统自动更新）：等它跑完，或者用下面这条确认没有 apt 在跑，再试。**不要直接删 lock 文件**，正在运行的 apt 被强行打断很容易搞坏软件包数据库。

```bash
ps aux | grep -i apt
```

如果 `apt update` 报 404 错误，是软件源地址失效了：检查是不是换了镜像源之后写错了地址，或者按[装好之后先做的事](ubuntu-first-steps.md)里的方法换一个源。

## 图形界面黑屏 / 进不了桌面

先试试能不能进文字终端：按 `Ctrl+Alt+F3`（F3 不行就试 F2、F4、F5），能看到登录提示就说明系统本身没死，只是图形界面起不来。登录后按顺序查：

```bash
df -h
```

磁盘满了是黑屏的常见原因（见上一节），先排除。再看显示管理器状态：

```bash
systemctl status gdm3
```

```bash
sudo systemctl restart gdm3
```

`gdm3` 是 Ubuntu 的登录界面服务，重启它相当于重新进一次桌面。如果是装了 NVIDIA 驱动之后黑屏，重新检测并安装驱动：

```bash
ubuntu-drivers devices
```

```bash
sudo ubuntu-drivers autoinstall
```

```bash
sudo reboot
```

如果黑屏发生在刚装完系统第一次启动，可能是显卡太新、开源驱动还没支持：开机时在 GRUB 菜单按 `e`，在 `linux` 那行末尾加上 `nomodeset` 再按 `Ctrl+X` 启动，进系统后装好官方驱动就好了。

## 忘记登录密码

重启电脑，开机时按住 `Shift`（传统 BIOS）或狂按 `Esc`（UEFI），调出 GRUB 菜单，选「高级选项」→ 带 `(recovery mode)` 的那一项，进恢复模式后选 `root`（进入 root 命令行）。先把根分区改成可写：

```bash
mount -o remount,rw /
```

再改密码（把 `用户名` 换成你的）：

```bash
passwd 用户名
```

输两次新密码，成功后重启：

```bash
reboot
```

> 这招能改掉任何没加密的 Ubuntu 的密码——所以物理接触电脑的人本来就能绕过密码。真要防这一手，得装系统时开全盘加密（LUKS），那是另一个话题了。

## 看日志：查不下去时的万能办法

系统日志用 journalctl 看（要加 sudo 才能看完整系统日志）：

```bash
sudo journalctl -xe
```

```bash
sudo journalctl -b -1
```

```bash
sudo journalctl -f
```

`-xe` 看最近的报错（结尾的红色行就是线索），`-b -1` 看上一次启动的日志（系统崩溃重启后查上次死在哪），`-f` 实时滚动（复现问题时开着它）。只看某个服务的日志：

```bash
sudo journalctl -u ssh --since "1 hour ago"
```

内核和硬件相关的消息：

```bash
sudo dmesg | tail -n 50
```

常见的日志文件位置：

| 位置 | 里面有什么 |
|---|---|
| `/var/log/syslog` | 系统总日志 |
| `/var/log/apt/history.log` | 装过、卸过什么软件 |
| `/var/log/auth.log` | 登录、sudo 记录 |
| `~/.xsession-errors` | 图形界面程序的报错（旧版有，24.04 多数情况看 journalctl 就行） |

## 求助时带上这些信息

去论坛或问别人之前，先准备好这几样，别人才能帮你定位：

```bash
lsb_release -a
```

```bash
uname -r
```

再加上：你做了什么操作、完整的报错原文（复制文字不要只截图）、之前改过什么配置。只说"我的 Ubuntu 坏了"是没法帮的。

## 相关阅读

- [Ubuntu 装好之后先做的事](ubuntu-first-steps.md)：换源、显卡驱动的正确做法
- [把 Ubuntu 当家里的小服务器](ubuntu-home-server.md)：服务起不来时看 `journalctl -u 服务名`
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读

## 来源/延伸阅读

- Ubuntu 官方文档：https://documentation.ubuntu.com/
- Ask Ubuntu（英文问答社区，绝大多数问题都有现成答案）：https://askubuntu.com/
