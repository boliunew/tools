---
title: Ubuntu 装好之后先做的事
tags: [科技, Ubuntu]
summary: 新装 Ubuntu 24.04 的第一天：更新系统、换软件源、装中文输入法、必装软件、显卡驱动和备份习惯，一次配好以后省心。
---

# Ubuntu 装好之后先做的事

刚装好的 Ubuntu 就能用，但有几件事越早做越好：系统更新补安全漏洞，软件源决定下载速度，中文输入法决定能不能顺手打字，显卡驱动决定画面流不流畅。按这篇的顺序做一遍，大概半小时，之后就不用反复折腾了。

文中所有命令都在终端里执行。打开终端按 `Ctrl+Alt+T`。命令前的 `sudo` 表示用管理员身份执行，第一次用会让你输登录密码（输入时屏幕上不显示星号，输完直接回车）。

## 1. 先更新系统

```bash
sudo apt update && sudo apt upgrade -y
```

`apt update` 是刷新软件列表，`apt upgrade` 是把已装的软件升到最新。刚装好的系统通常有几百 MB 更新，耐心等它跑完。如果提示要重启（比如内核更新了），重启一次再继续。

以后养成习惯：每周跑一次上面这条命令，或者打开「软件更新」图形工具点一下也一样。

## 2. 换软件源（下载慢才需要）

Ubuntu 默认从官方服务器下载软件。如果你在国内、下载速度只有几十 KB/s，换成国内镜像能快很多倍；如果下载速度本来就正常，这一步可以直接跳过。

图形界面换法：打开「软件和更新」→「下载自」下拉菜单 →「其他站点」→「选择最佳服务器」，等它测速完选一个最快的，点「选择服务器」，再输密码确认。

终端换法（以阿里云镜像为例，先备份原文件）：

```bash
sudo cp /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.bak
```

```bash
sudo sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list.d/ubuntu.sources
```

```bash
sudo apt update
```

> 24.04 和 22.04 的差别：24.04 的软件源配置文件是 `/etc/apt/sources.list.d/ubuntu.sources`（新格式），22.04 是 `/etc/apt/sources.list`（老格式）。上面这条 sed 命令只改网址部分，两种格式的路径不同，照着自己的版本改文件名就行。清华源（`mirrors.tuna.tsinghua.edu.cn`）也是常用选择，把命令里的 `mirrors.aliyun.com` 换掉即可。

## 3. 装中文输入法

在「设置」→「键盘」→「输入源」里点 `+`，选「中文」→「中文（智能拼音）」，就能用默认的 IBus 智能拼音打字，`Super+空格` 切换中英文输入。

如果列表里没有智能拼音，先装上：

```bash
sudo apt install ibus-libpinyin
```

装完注销再登录，重新添加输入源。

想要更好用的输入法可以换 fcitx5（词库和联想更强，支持双拼、云联想）：

```bash
sudo apt install fcitx5 fcitx5-chinese-addons
```

```bash
im-config -n fcitx5
```

注销再登录后，在右上角输入法图标里添加「拼音」即可。IBus 和 fcitx5 二选一，日常使用差别不大，智能拼音够用就不用换。

## 4. 必装的常用软件

一口气装上以后经常用到的工具：

```bash
sudo apt install -y git curl vim htop vlc gnome-tweaks
```

| 软件 | 干什么的 |
|---|---|
| git | 下载 GitHub 代码、版本管理，玩 Linux 必备 |
| curl | 命令行下载文件、测试网址 |
| vim | 终端里的文本编辑器（新手也可以只用 nano，系统自带） |
| htop | 看 CPU、内存、进程，比系统监视器直观 |
| vlc | 万能播放器，什么格式都能放 |
| gnome-tweaks | 调整 GNOME 桌面细节（主题、字体、窗口按钮位置） |

再装解码器和常用字体（播视频、看某些网页需要）：

```bash
sudo apt install ubuntu-restricted-extras
```

安装时会弹出微软字体的许可协议，按 `Tab` 键把光标移到「确定」上再回车，选「是」接受即可。

想要图形界面装 GNOME 扩展（比如桌面天气、系统监控小部件）：

```bash
sudo apt install gnome-shell-extension-manager
```

## 5. 显卡驱动

Intel 核显和 AMD 显卡用系统自带的开源驱动就行，一般不用管。NVIDIA 独显需要装官方驱动：

```bash
ubuntu-drivers devices
```

这条命令会列出适合你这张卡的驱动版本，`recommended` 标记的就是推荐装的。直接自动装：

```bash
sudo ubuntu-drivers autoinstall
```

```bash
sudo reboot
```

重启后画面正常、分辨率正常就是装好了。如果装完黑屏或分辨率不对，见[出问题了怎么办](ubuntu-troubleshooting.md)里的黑屏一节。

## 6. 顺手做的三件事

**打开防火墙。**Ubuntu 自带 ufw 防火墙，默认没启用：

```bash
sudo ufw enable
```

启用后只放行你主动允许的端口，局域网共享需要放行时再单独开（见[远程连接与局域网共享](ubuntu-remote-sharing.md)）。

**记下这台电脑的 IP 地址**（以后远程连接要用）：

```bash
hostname -I
```

显示的第一个地址就是局域网 IP，比如 `192.168.1.100`。

**建一个备份习惯。**装 Timeshift，定期给系统拍快照，玩坏了能一键恢复：

```bash
sudo apt install timeshift
```

第一次打开按向导选 RSYNC 模式、定个每周自动快照就行。系统自带的「备份」（Deja Dup）可以备份你的个人文件到移动硬盘。数据更重要的话，看看[家里主机的备份方案](homelab-backup.md)。

## 检查清单

| 做完了吗 | 事项 |
|---|---|
| ☐ | 系统更新到最新 |
| ☐ | 软件源速度正常（慢就换镜像） |
| ☐ | 中文输入法能打字 |
| ☐ | git、curl、vim、htop、vlc 装好 |
| ☐ | 显卡驱动正常（NVIDIA 用户） |
| ☐ | 防火墙已启用 |
| ☐ | Timeshift 快照已设置 |

## 相关阅读

- [终端入门：常用命令速查](ubuntu-terminal-basics.md)：这篇里的命令是什么意思、还能怎么用
- [装软件的五种办法](ubuntu-software-install.md)：apt 之外，Snap、Flatpak、.deb、AppImage 各适合装什么
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读
- [家里主机的备份方案（3-2-1、restic、自动化）](homelab-backup.md)：备份的完整思路

## 来源/延伸阅读

- Ubuntu 官方桌面文档：https://documentation.ubuntu.com/desktop/
- Ubuntu 中文 Wiki（换源、输入法等条目）：https://wiki.ubuntu.org.cn/
