---
title: 终端入门：常用命令速查
tags: [科技, Ubuntu]
summary: 第一次用终端不用慌：文件操作、sudo 与权限、管道重定向、查找、进程磁盘这些最常用的命令，一张速查表够用很久。
---

# 终端入门：常用命令速查

终端就是用文字命令操作电脑的窗口。刚开始会觉得不如鼠标直观，但它的好处是**精确、可重复、能批量处理**：鼠标点半小时的活，一条命令几秒就做完。这篇只讲最常用的命令，目标是"会查、会用"，不是背下来。

打开终端按 `Ctrl+Alt+T`。看到类似 `john@ubuntu:~$` 的提示符：`john` 是用户名，`ubuntu` 是电脑名，`~` 表示当前在主目录（`/home/john`），`$` 表示普通用户（`#` 是管理员）。

## 文件操作：最常用的十几个命令

| 命令 | 作用 |
|---|---|
| `pwd` | 显示当前在哪个目录 |
| `ls` | 列出当前目录的文件（`ls -la` 显示隐藏文件和详细信息） |
| `cd` | 切换目录（`cd ~/tools` 进目录，`cd ..` 回上一级，`cd ~` 回主目录） |
| `mkdir` | 新建目录（`mkdir -p a/b/c` 一次建多级） |
| `cp` | 复制（`cp -r` 复制整个目录） |
| `mv` | 移动或改名 |
| `rm` | 删除（没有回收站！`rm -r` 删目录） |
| `touch` | 新建空文件或刷新时间 |
| `cat` | 显示文件内容 |
| `less` | 分页看大文件（按 `q` 退出） |

实际敲几遍就记住了：

```bash
pwd
```

```bash
ls -la
```

```bash
cd ~/tools
```

```bash
mkdir -p ~/practice/test
```

```bash
cp notes.txt notes.txt.bak
```

```bash
mv old-name.txt new-name.txt
```

```bash
touch hello.txt
```

```bash
cat hello.txt
```

> `rm` 删掉的文件不进回收站，找不回来。删之前先用 `ls` 确认一遍，尤其不要对 `rm -rf` 后面跟的路径手滑——`rm -rf /` 这种命令会删掉整个系统，网上任何教程让你执行它都是恶作剧。拿不准时加 `-i`，每个文件删之前都会问你一声。

## 看文件内容：cat、less、head、tail

```bash
cat ~/.bashrc
```

```bash
less ~/.bashrc
```

```bash
head -n 20 ~/.bashrc
```

```bash
tail -n 20 ~/.bashrc
```

`less` 里按 `q` 退出，按 `/` 可以搜索。`tail -f` 会实时追着看文件末尾（看日志时很有用，按 `Ctrl+C` 退出），系统日志要加 `sudo` 才看得到：

```bash
sudo tail -f /var/log/syslog
```

## sudo 与权限

Linux 里普通用户不能碰系统文件，`sudo` 的意思是"用管理员身份执行这一条命令"：

```bash
sudo apt update
```

第一次用 `sudo` 会要求输登录密码，输的时候屏幕上什么都不显示，输完回车就行。密码 15 分钟内有效，之后再用要重新输。

每个文件都有权限。`ls -l` 看到的 `-rw-r--r--` 就是权限位，分成三组：所有者、同组人、其他人，`r` 读、`w` 写、`x` 执行。常用数字写法：

| 数字 | 含义 | 常见用法 |
|---|---|---|
| 755 | 所有者全权，其他人读+执行 | 文件夹、脚本 |
| 644 | 所有者读写，其他人只读 | 普通文件 |
| 600 | 只有所有者能读写 | 密钥、私密文件 |

```bash
chmod +x script.sh
```

```bash
chmod 644 notes.txt
```

```bash
sudo chown $USER:$USER file.txt
```

`chown` 是改文件的主人（`$USER` 会自动换成你自己的用户名）。最常见的一种情况：用 `sudo` 建出来的文件属于 root，普通用户改不了，用 `chown` 改回自己就行。

> 忠告：不要养成什么都加 `sudo` 的习惯，更不要用 `sudo` 跑来历不明的脚本。看到教程里有 `curl ... | sudo bash` 这种"下载并立即执行"的写法，先把脚本下载下来看一眼，确认没问题再执行。

## 管道和重定向：把命令连起来

`|` 把上一条命令的输出送给下一条命令，`>` 把输出写进文件（覆盖），`>>` 追加到文件末尾：

```bash
ls -la | grep ".txt"
```

```bash
cat file.txt | wc -l
```

```bash
echo "hello" > hello.txt
```

```bash
echo "world" >> hello.txt
```

```bash
ls /nonexistent 2> err.txt
```

最后一条里的 `2>` 是把报错信息（标准错误）单独写进文件，`err.txt` 里就是那条报错。

## 查找：grep 和 find

```bash
grep -r "TODO" ~/tools
```

```bash
grep -i "error" app.log
```

```bash
find ~ -name "*.jpg"
```

```bash
find /var/log -name "*.log"
```

`grep` 是在文件内容里找文字（`-r` 递归找目录里所有文件，`-i` 不区分大小写）；`find` 是按名字找文件。想知道某个命令到底装在哪：

```bash
which python3
```

## 进程与系统状态

```bash
ps aux | grep firefox
```

```bash
top
```

```bash
df -h
```

```bash
du -sh ~/Downloads
```

```bash
free -h
```

```bash
uptime
```

`top` 是实时看 CPU 和内存占用，按 `q` 退出；想更好看的界面就用 `htop`（见[装好之后先做的事](ubuntu-first-steps.md)里装过）。`df -h` 看各分区还剩多少空间，`du -sh` 看某个目录占了多大，`free -h` 看内存。进程卡住了，先 `ps` 找到它的 PID（第二列数字），再：

```bash
kill 1234
```

把 `1234` 换成实际 PID。`kill` 不管用时才用 `kill -9`（强制杀，不给进程保存的机会）。

## 文本编辑器：nano 就够了

新手只用 nano 就行：

```bash
nano notes.txt
```

打开后直接打字，`Ctrl+O` 保存（按回车确认文件名），`Ctrl+X` 退出，`Ctrl+W` 搜索。nano 底部一直显示着快捷键，不用背。

vim 是很多教程和服务器上的默认编辑器，知道最基本的进出就行：

```bash
vim notes.txt
```

按 `i` 进入编辑模式，打完字按 `Esc` 回到命令模式，输入 `:wq` 回车保存退出，`:q!` 是不保存退出。vim 功能很强，但入门期没必要专门学，nano 能应付所有日常编辑。

## 终端快捷键

| 快捷键 | 作用 |
|---|---|
| `Tab` | 自动补全命令和文件名（按两下看所有候选） |
| `↑` `↓` | 翻上一条 / 下一条命令 |
| `Ctrl+C` | 中断当前命令 |
| `Ctrl+L` | 清屏 |
| `Ctrl+R` | 搜索历史命令 |
| `Ctrl+A` / `Ctrl+E` | 光标移到行首 / 行尾 |
| `Ctrl+U` | 删掉光标前面的整行输入 |
| `Ctrl+D` | 退出当前终端（相当于输入 exit） |

`Tab` 补全是最值得养成肌肉记忆的一个：文件名打两三个字母就按 `Tab`，既省时间又不会打错。

## 相关阅读

- [Ubuntu 装好之后先做的事](ubuntu-first-steps.md)：装 htop、vim 这些终端工具
- [每天用得到的技巧](ubuntu-daily-tips.md)：别名、历史命令、定时任务，把终端用得更顺手
- [Ubuntu 系列总览](ubuntu-index.md)：回到系列导读

## 来源/延伸阅读

- 每个命令的完整手册都在本机，按 `q` 退出：

```bash
man ls
```

- Ubuntu 命令行入门（官方教程）：https://ubuntu.com/tutorials/command-line-for-beginners
