#!/usr/bin/env bash
# 🏠 One-command setup of the tools site on a home mini PC (Ubuntu Server 24.04 LTS).
#
#   git clone https://github.com/boliunew/tools.git ~/tools
#   bash ~/tools/selfhost/install.sh
#
# What it does (safe to run again — it only fills in what is missing):
#   1. system packages (Python, ffmpeg, git) and a Python venv with everything the jobs need
#   2. the web server (selfhost/server.py) as a service that starts at boot
#   3. the data jobs (stocks / earnings / news / deals / radio / monitor) on timers, same times as on GitHub
#   4. Tailscale — only your own phone and computer can open the site, over HTTPS
#   5. ntfy — private push notifications to your phone (股价提醒, 网页监控, job errors)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
ME="$(id -un)"
CFG="$HERE/config.env"
say() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }

if [ "$(id -u)" = 0 ]; then echo "请用普通用户运行（脚本里需要的地方会自己用 sudo）"; exit 1; fi
sudo -v

# ------------------------------------------------------------------ 1. packages + venv
say "1/5 安装系统软件和 Python 环境（第一次要几分钟）"
sudo timedatectl set-timezone America/Los_Angeles || true
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git curl ffmpeg ca-certificates >/dev/null
ok "系统软件"
[ -x "$ROOT/.venv/bin/python" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -q --upgrade pip
"$ROOT/.venv/bin/pip" install -q -r "$HERE/requirements.txt"
ok "Python 库"
if ! ls "$HOME/.cache/ms-playwright" 2>/dev/null | grep -q chromium; then
  sudo "$ROOT/.venv/bin/python" -m playwright install-deps chromium >/dev/null 2>&1 || true
  "$ROOT/.venv/bin/python" -m playwright install chromium >/dev/null 2>&1 || echo "  (网页监控用的浏览器没装好，不影响其他功能)"
fi
ok "网页监控用的无头浏览器"
mkdir -p "$ROOT/.local-data/logs" "$ROOT/.local-data/kv"

# ------------------------------------------------------------------ config
if [ ! -f "$CFG" ]; then
  TOPIC="tools-$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  cat > "$CFG" <<EOF
# home server settings (created by install.sh; not in git)
PORT=8080
OWNER=boliunew
TOOLS_DATA=$ROOT/.local-data
NTFY_TOPIC=$TOPIC
NTFY_URL=
NTFY_SUB=
PUBLIC_URL=
EOF
fi
set -a; . "$CFG"; set +a
setcfg() { if grep -q "^$1=" "$CFG"; then sed -i "s|^$1=.*|$1=$2|" "$CFG"; else echo "$1=$2" >> "$CFG"; fi; }

# ------------------------------------------------------------------ 2. web service
say "2/5 网页服务（开机自动启动）"
sudo tee /etc/systemd/system/tools-web.service >/dev/null <<EOF
[Unit]
Description=tools site (home server)
After=network-online.target
Wants=network-online.target

[Service]
User=$ME
WorkingDirectory=$ROOT
EnvironmentFile=$CFG
Environment=PYTHON=$ROOT/.venv/bin/python
ExecStart=$ROOT/.venv/bin/python $HERE/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now tools-web >/dev/null 2>&1
sudo systemctl restart tools-web
sleep 1
curl -fs "http://127.0.0.1:${PORT}/api/ping" >/dev/null && ok "网页服务在 127.0.0.1:${PORT} 运行" || echo "  ⚠️ 网页服务没起来：sudo journalctl -u tools-web -n 50"

# ------------------------------------------------------------------ 3. timers
say "3/5 定时任务（和以前 GitHub 上的时间一样，太平洋时间）"
sudo tee /etc/systemd/system/tools-job@.service >/dev/null <<EOF
[Unit]
Description=tools data job: %i
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ME
WorkingDirectory=$ROOT
EnvironmentFile=$CFG
ExecStart=$HERE/run-job.sh %i
TimeoutStartSec=90min
Nice=5
EOF
timer() {  # name, description, OnCalendar lines…
  local name="$1" desc="$2"; shift 2
  {
    echo "[Unit]"; echo "Description=$desc"; echo; echo "[Timer]"
    for c in "$@"; do echo "OnCalendar=$c"; done
    echo "Persistent=true"; echo "RandomizedDelaySec=60"; echo "Unit=tools-job@$name.service"; echo; echo "[Install]"; echo "WantedBy=timers.target"
  } | sudo tee "/etc/systemd/system/tools-$name.timer" >/dev/null
  sudo systemctl enable "tools-$name.timer" >/dev/null 2>&1
}
timer stocks   "股票池扫描 + 股价提醒（收盘后、晚上补一次、第二天早上再补一次）" "Mon..Fri 14:47" "Mon..Fri 18:17" "Tue..Sat 06:47"
timer earnings "财报与经济日历" "Mon..Fri 05:37" "Sun 11:37"
timer news     "英文新闻 + 每日一句" "*-*-* 06:07" "*-*-* 18:07"
timer deals    "打折雷达" "*-*-* 06:17" "*-*-* 17:17"
timer radio    "通勤电台" "*-*-* 06:20"   # 早上的新闻 6:07 跑完再生成，7 点出门前肯定好了
timer monitor  "网页监控（每 4 小时）" "*-*-* 00/4:17"
sudo systemctl daemon-reload
sudo systemctl restart tools-stocks.timer tools-earnings.timer tools-news.timer tools-deals.timer tools-radio.timer tools-monitor.timer
ok "6 个定时任务（查看：systemctl list-timers 'tools-*'）"

# ------------------------------------------------------------------ 4. Tailscale
say "4/5 Tailscale：只让你自己的手机和电脑访问"
if ! command -v tailscale >/dev/null; then curl -fsSL https://tailscale.com/install.sh | sh; fi
if ! tailscale status >/dev/null 2>&1; then
  echo "  下面会出现一个登录链接，用手机打开并登录（和手机上 Tailscale App 用同一个账号）："
  sudo tailscale up
fi
DNS="$(tailscale status --json | python3 -c 'import sys,json; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
echo "  如果下面提示要开启 HTTPS / Serve，按提示打开链接点一下「Enable」，脚本会自动继续。"
sudo tailscale serve --bg "${PORT}" >/dev/null
ok "网站地址：https://$DNS"
setcfg PUBLIC_URL "https://$DNS"

# ------------------------------------------------------------------ 5. ntfy
say "5/5 ntfy 手机推送（自己架设，消息不经过任何第三方）"
if ! command -v ntfy >/dev/null; then
  ARCH="$(dpkg --print-architecture)"
  URL="$(curl -fsSL https://api.github.com/repos/binwiederhier/ntfy/releases/latest | python3 -c "import sys,json; a=[x['browser_download_url'] for x in json.load(sys.stdin)['assets'] if x['name'].endswith('linux_${ARCH}.deb')]; print(a[0] if a else '')")"
  if [ -n "$URL" ]; then curl -fsSL -o /tmp/ntfy.deb "$URL" && sudo apt-get install -y -qq /tmp/ntfy.deb >/dev/null; fi
fi
if command -v ntfy >/dev/null; then
  sudo mkdir -p /etc/ntfy
  sudo tee /etc/ntfy/server.yml >/dev/null <<EOF
base-url: "https://$DNS:8443"
listen-http: "127.0.0.1:8090"
behind-proxy: true
cache-file: "/var/cache/ntfy/cache.db"
cache-duration: "72h"
EOF
  sudo mkdir -p /var/cache/ntfy && sudo chown -R ntfy:ntfy /var/cache/ntfy 2>/dev/null || true
  sudo systemctl enable --now ntfy >/dev/null 2>&1; sudo systemctl restart ntfy
  sudo tailscale serve --bg --https=8443 http://127.0.0.1:8090 >/dev/null
  setcfg NTFY_URL "http://127.0.0.1:8090/$NTFY_TOPIC"
  setcfg NTFY_SUB "https://$DNS:8443/$NTFY_TOPIC"
  ok "ntfy 运行中"
else
  echo "  ⚠️ ntfy 没装上（网络问题？）。提醒照样会记录在「通知中心」页面，之后重新运行本脚本即可补装。"
fi
sudo systemctl restart tools-web
set -a; . "$CFG"; set +a
[ -n "${NTFY_URL:-}" ] && curl -fs -m 10 -H "Title: 🏠 家里的主机已就绪" -d "以后的股价提醒、网页监控都会推到这里。" "$NTFY_URL" >/dev/null || true

# ------------------------------------------------------------------ first data
say "第一次拉取数据（在后台跑，十几分钟内陆续完成）"
for j in news earnings deals stocks monitor radio; do sudo systemctl start --no-block "tools-job@$j.service"; done
ok "进度：tail -f $ROOT/.local-data/logs/stocks.log"

cat <<EOF

────────────────────────────────────────────────────────
🎉 装好了！

  网站：      https://$DNS
              （手机和电脑都要装 Tailscale App、登录同一个账号）
  手机推送：  ntfy App → ＋ → Use another server → 填
              ${NTFY_SUB:-（ntfy 未安装）}
  搬旧数据：  在旧网站打开 migrate.html「导出」，到新网站 migrate.html「导入」
  通知中心：  https://$DNS/issues.html

  常用命令：
    systemctl list-timers 'tools-*'          看定时任务
    $HERE/run-job.sh stocks                  手动跑一次（stocks/news/deals/…/all）
    tail -n 50 $ROOT/.local-data/logs/news.log   看日志
    $HERE/update.sh                          以后更新代码
────────────────────────────────────────────────────────
EOF
