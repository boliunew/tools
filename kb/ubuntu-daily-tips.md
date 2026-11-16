---
title: 每天用得到的技巧
tags: [科技, Ubuntu]
summary: 快捷键、alias 别名、历史命令、cron 定时任务、磁盘清理、截屏录屏——每天都在用的小技巧，配好一次天天省时间。
---

# 每天用得到的技巧

这篇不讲大道理，全是每天用电脑时顺手能用的东西：记住几个快捷键、给常用命令起个别名、让重复的活定时自动跑、磁盘满了知道往哪清。每个技巧独立，看到哪个用哪个。

## 常用快捷键

| 快捷键 | 作用 |
|---|---|
| `Ctrl+Alt+T` | 打开终端 |
| `Super` | 打开活动总览（搜应用、看窗口） |
| `Alt+Tab` | 在应用之间切换 |
| `Super+←` / `Super+→` | 窗口贴左边 / 右边（分屏） |
| `Super+↑` | 窗口最大化 |
| `Ctrl+Super+←` / `→` | 切换到左 / 右边的工作区 |
| `Super+L` | 锁屏 |
| `Print` | 打开截图界面（选区、窗口、全屏、录屏都在这） |
| `Ctrl+Alt+Shift+R` | 直接开始 / 停止录屏 |

`Super` 就是键盘左下角带 Windows 标志的那个键。`Print` 键在 24.04 里打开的是 GNOME 自带的截图界面，点"录制"还能直接录屏，录好的视频存在 `~/Videos/Screencasts/`。

想要更强的截图工具（标注、贴图、长截图）可以装 Flameshot：

```bash
sudo apt install flameshot
```

## alias 别名：把长命令变短

把常用的长命令起个别名，写在 `~/.bashrc` 里，每次打开终端自动生效。比如：

```bash
echo "alias update='sudo apt update && sudo apt upgrade -y'" >> ~/.bashrc
```

```bash
echo "alias ..='cd ..'" >> ~/.bashrc
```

```bash
echo "alias myip='hostname -I'" >> ~/.bashrc
```

加完让它立即生效（不然要重开终端）：

```bash
source ~/.bashrc
```

之后敲 `update` 就等于敲了整条更新命令。别名可以随时改，直接用 nano 打开 `~/.bashrc` 找到那几行编辑就行。

| 别名 | 原命令 | 干什么 |
|---|---|---|
| `update` | `sudo apt update && sudo apt upgrade -y` | 更新系统 |
| `..` | `cd ..` | 回上一级目录 |
| `myip` | `hostname -I` | 看本机 IP |

## 历史命令：不用重复打字

终端记着你敲过的每条命令：

```bash
history
```

```bash
history | grep ssh
```

按 `↑` 键翻上一条命令；按 `Ctrl+R` 再输入几个关键字，能反向搜索历史命令；`!!` 是"再执行上一条命令"（最常见的用法是上一条忘了加 `sudo`，直接敲 `sudo !!`）。

## cron 定时任务：让电脑自己干活

cron 是系统自带的定时器，适合"每天早上 9 点备份一次"这种重复任务。编辑自己的定时任务表：

```bash
crontab -e
```

第一次会问用哪个编辑器，选 nano（一般是选项 1）。时间格式是 `分 时 日 月 周 命令`。先做一个真正能跑的最小备份脚本（每天把 `~/Documents` 打包到 `~/backups`，只留 30 天内的）：

```bash
cat > ~/backup.sh << 'EOF'
#!/bin/bash
mkdir -p ~/backups
tar -czf ~/backups/docs-$(date +%F).tar.gz ~/Documents 2>/dev/null
find ~/backups -name 'docs-*.tar.gz' -mtime +30 -delete
EOF
```

```bash
chmod +x ~/backup.sh
```

先手动跑一次，确认 `~/backups` 里生成了当天的压缩包：

```bash
~/backup.sh
```

没问题的话，再让 cron 每天早上 9 点自动跑它（把 `用户名` 换成你自己的，`whoami` 可以查）：

```
0 9 * * * /home/用户名/backup.sh
```

保存退出后自动生效。几个常用写法：

| 写法 | 意思 |
|---|---|
| `0 9 * * *` | 每天 9:00 |
| `*/30 * * * *` | 每 30 分钟 |
| `0 0 * * 0` | 每周日 0:00 |
| `0 3 1 * *` | 每月 1 号 3:00 |

查看当前定时任务：

```bash
crontab -l
```

> cron 里执行的命令要用绝对路径（`/home/用户名/xxx.sh`），因为 cron 的环境变量和你在终端里不一样，相对路径和 `~` 容易找不到文件。脚本本身记得 `chmod +x` 加上可执行权限。

## 磁盘清理：满了先清这几处

先看是谁占的地方：

```bash
df -h
```

```bash
du -sh ~/* 2>/dev/null | sort -h
```

`df -h` 看分区还剩多少，`du` 那条按大小列出主目录下的文件夹，最大的在最下面。想图形化看每个目录占多少，装 ncdu：

```bash
sudo apt install ncdu
```

```bash
ncdu ~
```

在 ncdu 里用方向键进出目录，按 `d` 删除选中的文件（删之前会确认），按 `q` 退出。清理系统垃圾：

```bash
sudo apt autoremove
```

```bash
sudo apt autoclean
```

```bash
sudo journalctl --vacuum-size=200M
```

`autoremove` 清掉没用的依赖包，`autoclean` 清掉旧安装包缓存，`journalctl --vacuum-size` 把系统日志压缩到 200MB 以内。还有回收站，图形界面清空就行，或者：

```bash
rm -rf ~/.local/share/Trash/*
```

## 快速打开终端和文件管理器

在文件管理器里对着空白处点右键，选"在终端中打开"，终端就直接定位到这个文件夹。反过来，在终端里想用文件管理器打开当前目录：

```bash
xdg-open .
```

`xdg-open` 是"用默认程序打开"，后面跟文件或网址都行，比如 `xdg-open photo.jpg` 就是用看图程序打开这张照片。

想看目录结构一目了然，装 tree：

```bash
sudo apt install tree
```

```bash
tree -L 2 ~/tools
```

`-L 2` 是只看两层，层数多了会刷屏。

## 相关阅读

- [终端入门：常用命令速查](ubuntu-terminal-basics.md)：别名和历史命令背后的命令本身
- [把 Ubuntu 当家里的小服务器](ubuntu-home-server.md)：定时任务之外，开机自启服务的做法
- [出问题了怎么办](ubuntu-troubleshooting.md)：磁盘满了的完整排查
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读

## 来源/延伸阅读

- GNOME 帮助文档（快捷键、桌面使用）：https://help.gnome.org/users/gnome-help/stable/
- cron 表达式在线测试：https://crontab.guru/
