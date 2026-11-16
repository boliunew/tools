---
title: 远程连接与局域网共享
tags: [科技, Ubuntu]
summary: 从 Windows 笔记本、手机连上 Ubuntu 电脑：SSH 登录、SFTP 传文件、Samba 共享文件夹、adb 连安卓手机，四种办法各管什么。
---

# 远程连接与局域网共享

Ubuntu 电脑放在家里，最常用它的方式不一定是坐在它面前：从 Windows 笔记本上敲命令、从手机上打开它共享的文件夹、用数据线让它和安卓手机传文件。这篇讲四种连接办法，各管不同的事：

| 办法 | 用来干什么 | 对端用什么 |
|---|---|---|
| SSH | 在别的电脑上敲这台电脑的终端命令 | Windows 终端 / 手机上的 SSH 客户端 |
| SFTP | 通过 SSH 传文件（加密） | 文件管理器、FileZilla、WinSCP |
| Samba | 把文件夹共享成"网上邻居"，Windows 和手机直接打开 | Windows 文件资源管理器 / 手机文件 App |
| adb | 连安卓手机传文件、调试 | 数据线或同一 Wi-Fi |

开始之前先记下 Ubuntu 的局域网 IP（四种办法都要用）：

```bash
hostname -I
```

显示的第一个地址就是，比如 `192.168.1.100`。下面例子里的 IP 都用这个，请换成你自己的。

## SSH：远程敲命令

先在 Ubuntu 上装 SSH 服务：

```bash
sudo apt install openssh-server
```

```bash
sudo systemctl enable --now ssh
```

```bash
sudo ufw allow ssh
```

`enable --now` 是"开机自启并且现在就启动"。防火墙放行之后，从 Windows 上打开终端（PowerShell 或 Windows Terminal，Win10 之后自带 SSH 客户端）：

```bash
ssh john@192.168.1.100
```

把 `john` 换成你的 Ubuntu 用户名。第一次连接会问"是否信任这台主机"，输入 `yes` 回车，再输 Ubuntu 的登录密码就进去了。看到 `john@ubuntu:~$` 这样的提示符，说明你已经在操作 Ubuntu 了，敲的每条命令都在 Ubuntu 上执行。

退出 SSH 按 `Ctrl+D` 或者输入 `exit`。

### 免密码登录（密钥）

每次输密码很烦，还可以用密钥登录。在** Windows 那台电脑**上生成一对密钥：

```bash
ssh-keygen -t ed25519
```

一路回车用默认设置就行（也可以给密钥再设一个密码）。再把公钥传到 Ubuntu 上：

```bash
ssh-copy-id john@192.168.1.100
```

输一次密码，之后再 `ssh` 就不用密码了。密钥文件在 Windows 的 `C:\Users\你的用户名\.ssh\` 里，私钥（`id_ed25519`）不要发给任何人。

> 安全提醒：SSH 只在局域网里用很安全；如果哪天想从外网连回来（比如在公司连家里的电脑），一定要先改成只允许密钥登录、关掉密码登录，做法见[把 Ubuntu 当家里的小服务器](ubuntu-home-server.md)。

## SFTP：通过 SSH 传文件

装了 SSH 就自带 SFTP，不用另外装。命令行用法：

```bash
sftp john@192.168.1.100
```

进去后 `put 本地文件` 是上传，`get 远程文件` 是下载，`ls` / `cd` 和终端里一样，`exit` 退出。图形界面更方便：Ubuntu 文件管理器地址栏输入 `sftp://john@192.168.1.100` 就能像本地文件夹一样打开；Windows 上用 FileZilla 或 WinSCP，协议选 SFTP，填 IP、用户名、密码就行。

传单个文件还有更简单的 `scp`（不用进交互界面）：

```bash
scp photo.jpg john@192.168.1.100:~/
```

## Samba：共享文件夹给 Windows 和手机

Samba 是把 Ubuntu 的文件夹共享成 Windows 能直接打开的"网络文件夹"，适合长期共享：电影、照片、备份目录放上去，家里所有设备都能看。

先装 Samba：

```bash
sudo apt install samba
```

备份原配置文件，再建一个要共享的文件夹：

```bash
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak
```

```bash
mkdir -p ~/share
```

把共享配置追加到配置文件末尾（`$USER` 会自动换成你的用户名）：

```bash
sudo tee -a /etc/samba/smb.conf > /dev/null <<EOF

[share]
   path = /home/$USER/share
   browseable = yes
   writable = yes
   valid users = $USER
EOF
```

给 Samba 单独设密码（可以和登录密码一样，也可以不一样）：

```bash
sudo smbpasswd -a $USER
```

重启服务、放行防火墙、检查配置有没有写错：

```bash
sudo systemctl restart smbd
```

```bash
sudo ufw allow samba
```

```bash
testparm -s
```

`testparm` 没报错就说明配置没问题。

Windows 上打开文件资源管理器，地址栏输入 `\\192.168.1.100\share`，填 Ubuntu 用户名和刚才设的 Samba 密码就能打开。手机上用文件 App（比如三星的"我的文件"或 CX 文件管理器）添加网络存储，地址填 `smb://192.168.1.100/share`。

### 免密码共享（访客模式）

如果嫌每次输密码麻烦，可以改成局域网内免密码访问。先删掉上面那行的用户限制、换成访客允许：

```bash
sudo sed -i '/valid users/d' /etc/samba/smb.conf
```

```bash
sudo sed -i '/^\[share\]/a\   guest ok = yes' /etc/samba/smb.conf
```

```bash
sudo sed -i '/^\[global\]/a\   map to guest = Bad User' /etc/samba/smb.conf
```

访客访问的是 `nobody` 这个系统账号，需要给共享文件夹和主目录放开权限：

```bash
chmod 777 ~/share
```

```bash
chmod o+x ~
```

第二条很关键：Ubuntu 21.04 之后主目录默认是 `750` 权限，访客账号连 `~/share` 的门都进不了，`chmod o+x ~` 只放开"经过主目录"的权限，不会暴露主目录里的其他文件。改完重启服务：

```bash
sudo systemctl restart smbd
```

> 两个提醒：一是访客模式意味着局域网里任何人都能读写这个文件夹，只适合信任的家庭网络，不要暴露到公网；二是 Windows 默认会拒绝免密码的访客共享，要在 Windows 上以管理员身份执行 `Set-SmbClientConfiguration -EnableInsecureGuestLogons $true`（或在组策略里开"启用不安全的来宾登录"）才能打开。

## adb：连安卓手机传文件

手机开 USB 调试（设置 → 开发者选项 → USB 调试；开发者选项没出现的话，在"关于手机"里连续点版本号 7 次）。Ubuntu 上装 adb：

```bash
sudo apt install adb
```

三星手机需要一条 udev 规则，否则 adb 会显示 `no permissions`：

```bash
sudo tee /etc/udev/rules.d/51-android.rules > /dev/null <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev"
EOF
```

```bash
sudo udevadm control --reload-rules
```

手机用数据线连上电脑，手机上点"允许 USB 调试"，再看设备：

```bash
adb devices
```

看到设备序列号后面是 `device` 就是连上了。传文件：

```bash
adb push photo.jpg /sdcard/Download/
```

```bash
adb pull /sdcard/DCIM/ ~/Pictures/phone/
```

`adb push` 是电脑传手机，`adb pull` 是手机传电脑。传大文件或整个文件夹时，adb 比直接用文件管理器拖要稳得多。

> 小知识：手机里的 `/sdcard` 其实是个符号链接，指向 `/storage/emulated/0`。在手机上用 `find` 命令遍历时要加 `-H`（`find -H /sdcard`），否则只会返回链接本身、看不到里面的文件。

## 相关阅读

- [把 Ubuntu 当家里的小服务器](ubuntu-home-server.md)：SSH 关掉密码登录、防火墙只开必要端口
- [家庭网络基础](home-network-basics.md)：局域网、IP、路由器这些概念的入门
- [出问题了怎么办](ubuntu-troubleshooting.md)：连不上时按步骤排查
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读

## 来源/延伸阅读

- OpenSSH 官方文档：https://www.openssh.com/
- Samba 官方文档：https://www.samba.org/samba/docs/
- Android adb 文档：https://developer.android.com/tools/adb
