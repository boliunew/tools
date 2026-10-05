---
title: 家里主机的备份方案（3-2-1、restic、自动化）
tags: [电脑, 主机]
summary: 网站和数据搬到家里的迷你主机后，硬盘坏了、手滑删了、被勒索了怎么办：3-2-1 原则、为什么 RAID 不算备份、用 rsync 和 restic 备份到外接硬盘和云端、systemd 定时自动跑，以及最容易被忽略的一步——测试恢复。
---

# 家里主机的备份方案

迷你主机一般只有一块固态硬盘。它坏的那天不会提前打招呼。备份要防的不只是硬盘坏，还有**自己手滑删错**、**升级把系统搞坏**、**被盗或进水**、**勒索软件把文件全加密**。

一句话原则：**没测试过恢复的备份，不算备份。**

## 3-2-1 原则

| 数字 | 意思 | 防什么 |
|---|---|---|
| **3** 份 | 原始数据 + 两份备份 | 一份备份本身也可能坏 |
| **2** 种介质 | 比如主机固态 + 外接硬盘 | 同一批次、同一种盘一起坏 |
| **1** 份异地 | 云端，或放在亲友家 | 火灾、被盗、整屋断电烧坏 |

对家里一台小主机来说，最实际的落地是：**主机本身 + 一块外接 USB 硬盘 + 一份加密的云端备份**。

## RAID 不是备份

RAID 1（镜像）是两块盘写一样的内容，坏一块还能继续跑。它解决的是**可用性**，不是**能找回**：

- 你删了一个文件，两块盘**同时**删掉；
- 勒索软件加密了文件，两块盘**同时**被加密；
- 电源烧了，两块盘可能一起完蛋。

RAID 可以有，但它不能替代备份。小主机通常也没地方装第二块盘，不用纠结。

## 先想清楚：备份什么

系统本身重装一次也就半小时，真正值钱的是**你自己产生的、别处没有的东西**：

| 内容 | 举例 | 备注 |
|---|---|---|
| 网站和代码 | `~/tools` | 已经推到 GitHub 的部分其实有异地备份了 |
| 程序数据 | `~/tools/.local-data`（同步数据、记录、日志） | 不进 git，**最该备份** |
| 配置和密钥 | `selfhost/config.env`、`~/.ssh`、`/etc` 里改过的文件 | 含密码，备份必须加密 |
| 数据库 | SQLite 文件、或数据库导出的 `.sql` | 运行中直接复制可能不一致，先导出或用 `sqlite3 x.db ".backup y.db"` |
| 照片、文档 | 手机同步过来的相册 | 体积最大，见下面「手机照片」 |

可以不备份：`.venv`、`node_modules`、缓存、下载的安装包——这些都能重新生成。

## 方法一：rsync 镜像到外接硬盘

`rsync` 是 Ubuntu 自带的同步工具，简单直接，备份出来就是普通文件，拿到任何电脑上都能直接打开。

```bash
# 外接硬盘挂载在 /mnt/backup
rsync -aAX --delete --info=progress2 \
  --exclude '.venv/' --exclude '__pycache__/' \
  ~/tools/ /mnt/backup/tools/
```

- `-a` 保留权限、时间等属性并递归；`-AX` 额外保留 ACL 和扩展属性。
- `--delete` 让目标和源完全一致（源里删了，备份里也删）。
- **源路径末尾的 `/` 很重要**：`~/tools/` 表示「复制里面的内容」，`~/tools` 表示「把 tools 这个文件夹本身复制过去」。
- 第一次跑之前加 `-n`（试运行），看看会改哪些文件再说。

**缺点：** 它只是镜像。今天误删了文件，晚上 rsync 一跑，备份里也没了；只能找回「上次同步时」的样子。所以 rsync 适合当「快速完整副本」，真正的历史版本交给 restic。

## 方法二：restic 做带历史的加密备份

**restic** 会把数据切块、去重、加密后存进一个「仓库」，每次备份是一个**快照**。只有变化的部分会占新空间，所以保留几十个版本也不会大多少。同一个工具既能备份到外接硬盘，也能备份到云端。

安装：`sudo apt install restic`

```bash
# 1. 密码存到一个只有自己能读的文件里（丢了密码 = 备份全部作废，另外抄一份放安全的地方）
echo '一个很长的随机密码' > ~/.restic-pass && chmod 600 ~/.restic-pass
export RESTIC_PASSWORD_FILE=~/.restic-pass

# 2. 初始化仓库（只做一次）
restic -r /mnt/backup/restic init

# 3. 备份
restic -r /mnt/backup/restic backup ~/tools /etc \
  --exclude '.venv' --exclude '__pycache__'

# 4. 看有哪些快照
restic -r /mnt/backup/restic snapshots

# 5. 按规则清理旧快照：保留最近 7 天、4 周、6 个月
restic -r /mnt/backup/restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune

# 6. 检查仓库完整性
restic -r /mnt/backup/restic check
```

备份 `/etc` 需要 root 权限，可以把整个命令放进 root 的定时任务里跑（下面有例子）。

## 快照：给系统拍「时间点照片」

快照和备份不同：它**在同一块盘上**记录某个时间点的状态，几乎瞬间完成、几乎不占空间，适合「升级前拍一张，搞坏了马上回滚」。

- 文件系统用 **Btrfs** 或 **ZFS** 才有原生快照；Ubuntu Server 默认装的是 ext4，没有这个功能，要在装系统时自己选。
- 用 LVM 的话也可以做 LVM 快照，但操作麻烦一些。
- 桌面版常用的 Timeshift 也是这个思路。

**快照在同一块盘上，盘坏了快照一起没。** 它是备份的补充，不是替代。restic 的「快照」则存在另一处，是真正的备份。

## 云端加密备份（异地那一份）

常见选择：**Backblaze B2**、**Wasabi**、**Cloudflare R2**、**AWS S3**，或者 Hetzner Storage Box 这类存储空间。restic 都能直接用。以 B2 为例：

```bash
export B2_ACCOUNT_ID='你的 keyID'
export B2_ACCOUNT_KEY='你的 applicationKey'
export RESTIC_PASSWORD_FILE=~/.restic-pass

restic -r b2:你的桶名:minipc init
restic -r b2:你的桶名:minipc backup ~/tools/.local-data ~/tools/selfhost/config.env
```

要点：

- restic 在本地加密后才上传，云服务商看不到内容。
- 给备份单独建一个**只能访问这一个桶**的密钥，别用主账号密钥。
- 有些服务支持「对象锁定」或不允许删除的密钥，能防止勒索软件连云端备份一起删掉。
- 云端按容量计费，照片这种大头先想好要不要放上去。

## 手机照片的备份思路

照片往往是家里最不可替代的数据。思路是**手机 → 一个自动同步的地方 → 再进入上面的备份链**：

| 方案 | 说明 |
|---|---|
| Google 相册 / OneDrive | 三星相册可以直接和 OneDrive 同步；最省事，但数据在别人那里 |
| **Immich**（自建） | 装在家里主机上，界面和 Google 相册类似，手机 App 自动上传；配合 Tailscale 在外面也能传 |
| Syncthing | 手机文件夹和主机文件夹双向同步，简单可靠 |

注意：

- **同步不等于备份**。双向同步时，手机上删了，主机上也会删。照片同步到主机后，主机那份必须再进 restic。
- 用自建方案，相当于把「云相册」的责任揽到自己身上，主机这边的备份就更要做好。
- 一份云相册 + 一份家里主机，本身已经很接近 3-2-1 了。

## 自动化：systemd timer（推荐）或 cron

手动备份迟早会忘。先把备份命令写成脚本，比如 `/usr/local/bin/backup.sh`：

```bash
#!/bin/bash
set -euo pipefail
export RESTIC_PASSWORD_FILE=/root/.restic-pass
REPO=/mnt/backup/restic

# 外接盘没挂上就退出，避免备份写到系统盘上
mountpoint -q /mnt/backup || { echo "外接盘未挂载"; exit 1; }

restic -r "$REPO" backup /home/你的用户名/tools /etc --exclude '.venv' --exclude '__pycache__'
restic -r "$REPO" forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
```

`sudo chmod 700 /usr/local/bin/backup.sh`，然后建两个文件：

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=restic 备份

[Service]
Type=oneshot
ExecStart=/usr/local/bin/backup.sh
```

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=每天凌晨 3 点备份

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now backup.timer
systemctl list-timers          # 看下次什么时候跑
sudo systemctl start backup.service   # 立刻手动跑一次
journalctl -u backup.service   # 看日志
```

`Persistent=true` 的意思是：凌晨 3 点主机刚好关机的话，下次开机会补跑一次。

**用 cron 也行**，`sudo crontab -e` 加一行：

```
0 3 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
```

cron 更简单，但关机错过就错过了，日志也要自己处理。

## 定期测试恢复

这一步最容易被跳过，也最重要。建议每隔一两个月做一次：

```bash
# 恢复最新快照到临时目录
restic -r /mnt/backup/restic restore latest --target /tmp/restore-test

# 或者只恢复某个文件夹
restic -r /mnt/backup/restic restore latest --target /tmp/restore-test --include /home/你的用户名/tools/.local-data

# 不恢复，直接把仓库挂成文件夹浏览（需要 fuse）
restic -r /mnt/backup/restic mount /mnt/restic
```

检查清单：

- 恢复出来的文件能打开吗？数据库能读吗？
- 换一台电脑（比如 Windows 上装 restic），只靠**密码和云端密钥**能恢复吗？这两样有没有存在主机以外的地方？
- 定时任务真的在跑吗？`restic snapshots` 里最新一条是不是昨天的？
- 偶尔跑 `restic check --read-data-subset=5%`，抽查一部分数据确实可读。

## 最小可行方案

懒得一步到位的话，按这个顺序做，每一步都比上一步安全很多：

1. 代码推到 GitHub（已经在做）。
2. 买一块外接硬盘，restic 每天自动备份 `.local-data`、配置和 `/etc`。
3. 再加一个云端 restic 仓库，只放小而重要的数据。
4. 手机照片自动同步，并纳入第 2、3 步。
5. 每两个月测一次恢复。

相关：外接硬盘用什么线接、USB 口速度怎么看，见 [USB-C 充电头和线怎么选](usb-pd-and-cables.md)；主机的网络和 Tailscale，见 [家庭网络入门](home-network-basics.md)。
