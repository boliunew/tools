---
title: 装软件的五种办法
tags: [科技, Ubuntu]
summary: apt、Snap、Flatpak、.deb、AppImage 五种装软件的办法各自有什么优缺点、一句话选用原则，再附几个常用软件到底该用哪种装。
---

# 装软件的五种办法

Ubuntu 装软件不像 Windows 只有一个"下载安装包双击"的办法，常用的有五种。新手不用全会，先记住结论：**优先 apt，应用商店里没有的再考虑其他**。这篇把五种办法讲清楚，遇到具体软件时能选对。

## 五种办法一览

| 办法 | 软件从哪来 | 优点 | 缺点 | 适合装什么 |
|---|---|---|---|---|
| apt | Ubuntu 官方仓库 | 最稳定，和系统一起更新，卸载干净 | 版本偏旧，有些软件没有 | 系统工具、开发工具、日常软件 |
| Snap | Snap 商店（Canonical 官方） | 版本新，沙箱隔离，自动更新 | 第一次启动慢，占空间大 | 桌面应用（火狐就是 Snap 版） |
| Flatpak | Flathub 等仓库 | 版本新，跨发行版通用 | 要自己装支持，占用空间大 | GIMP、OBS 这类桌面大软件 |
| .deb | 软件官网下载 | 官方版本，和 apt 一样管理 | 不会自动加更新源的要手动更新 | VS Code、Chrome 等官网软件 |
| AppImage | 软件官网下载 | 不用安装，双击就跑 | 不自动更新，不进应用菜单 | 临时试用、不想安装的工具 |

## apt：默认首选

apt 从 Ubuntu 官方仓库装软件，装上的软件会跟着系统一起更新，卸载也干净。先刷新列表再装：

```bash
sudo apt update
```

```bash
sudo apt install vlc
```

找软件、删软件：

```bash
apt search gimp
```

```bash
sudo apt remove vlc
```

```bash
sudo apt autoremove
```

`apt search` 不用加 sudo（只是查）。`autoremove` 是清掉不再被需要的依赖包，定期跑一次能省空间。

> `apt` 和 `apt-get` 都是同一个仓库的两套命令，日常用 `apt` 就行（输出更友好）；`apt-get` 主要给脚本用。新手看到教程里写 `apt-get`，当成 `apt` 理解就可以。

## Snap：Ubuntu 自带的应用商店

Ubuntu 24.04 的应用中心（App Center）背后就是 Snap。Snap 应用自带运行环境、沙箱隔离、自动更新，代价是第一次启动慢一点、占磁盘多一点。火狐在 24.04 里就是 Snap 版，装系统时已经自带了。

```bash
snap list
```

```bash
sudo snap install spotify
```

```bash
sudo snap refresh
```

`snap list` 看已装的 Snap 应用，`refresh` 是手动更新全部 Snap（平时系统会自动更新，不用管）。

## Flatpak：另一个通用打包格式

Flatpak 和 Snap 思路类似，但由社区主导、跨发行版通用，很多桌面软件（GIMP、OBS、LibreOffice 新版）在 Flathub 上的版本比 Ubuntu 仓库新。Ubuntu 默认没装 Flatpak 支持，要先装：

```bash
sudo apt install flatpak
```

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

第二条是添加 Flathub 仓库（最大的 Flatpak 软件源）。之后装软件：

```bash
flatpak install flathub org.gimp.GIMP
```

```bash
flatpak run org.gimp.GIMP
```

```bash
flatpak update
```

装完在应用菜单里也能找到，不用每次都 `flatpak run`。想在图形界面的软件中心里也看到 Flatpak 软件，再装一个插件：

```bash
sudo apt install gnome-software-plugin-flatpak
```

## .deb：官网下载的安装包

有些软件不在 Ubuntu 仓库里，官网提供 .deb 安装包（最典型的就是 VS Code 和 Chrome）。下载后双击就能在应用中心里安装；用终端装也行，进到下载目录：

```bash
cd ~/Downloads
```

```bash
sudo apt install ./code_*.deb
```

`./` 不能省，它告诉 apt"装本地这个文件"，而不是去仓库里找。`code_*` 是通配符，匹配你下载的 VS Code 安装包（文件名里的版本号每次都不一样）。用 `apt install` 装 .deb 的好处是依赖问题它会自动解决。

老办法是用 `dpkg`，但它不解决依赖，缺依赖时要再补一条：

```bash
sudo dpkg -i package.deb
```

```bash
sudo apt -f install
```

> .deb 装的软件能不能自动更新，看它装的时候有没有顺便加上官方软件源：Chrome 和 VS Code 的 .deb 都会自动加，以后跟着 `apt upgrade` 一起更新；没加源的 .deb 就要自己去官网下新版重装。

## AppImage：不用安装，双击就跑

AppImage 是把整个软件打进一个文件，下载后给它加上可执行权限，双击就能运行，不用安装、不动系统：

```bash
chmod +x ~/Downloads/*.AppImage
```

加上权限后在文件管理器里双击就能打开。AppImage 的代价是：不自动更新，不会自动出现在应用菜单里，卸载就是删文件。适合临时试用某个工具，或者只想用一次的软件。

如果双击没反应，可能是缺运行库，老 AppImage 在 24.04 上需要补一个包：

```bash
sudo apt install libfuse2
```

## 选用原则（一句话版）

1. 仓库里有的，优先 `apt`——最省心。
2. apt 里版本太旧、或者应用中心里推荐 Snap 版的，用 Snap。
3. 桌面大软件想要最新版（GIMP、OBS），用 Flatpak。
4. 官网只给 .deb（VS Code、Chrome），就装 .deb。
5. 只想临时用一下、不想安装，用 AppImage。

## 常用软件怎么装（举例）

| 软件 | 推荐办法 | 说明 |
|---|---|---|
| VLC | apt | 仓库里有，直接装 |
| GIMP | apt 或 Flatpak | apt 版够用；要最新版用 Flatpak（`org.gimp.GIMP`） |
| VS Code | .deb | 官网下载 .deb，装完自动加更新源 |
| Chrome | .deb | 官网下载 .deb，装完自动加更新源 |
| Spotify | Snap | Snap 商店里有官方版本 |
| OBS Studio | Flatpak | Flathub 上的 `com.obsproject.Studio` |
| Telegram | Snap 或官网 | Snap 版 `telegram-desktop`，或官网下载压缩包 |

## 相关阅读

- [Ubuntu 装好之后先做的事](ubuntu-first-steps.md)：必装软件清单和换源
- [终端入门：常用命令速查](ubuntu-terminal-basics.md)：apt、chmod 这些命令的详细用法
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读

## 来源/延伸阅读

- Flathub（Flatpak 软件目录）：https://flathub.org/
- Snap 商店：https://snapcraft.io/store
- Ubuntu 软件包搜索（查某个软件在哪个仓库、叫什么名字）：https://packages.ubuntu.com/
