#!/usr/bin/env bash
# 🤖 Turn on「AI 研判」on the home mini PC: TradingAgents writes a short multi-analyst
# verdict for the top few stocks in today's pool, shown at the top of 今日股票池.
#
#   bash ~/tools/selfhost/setup-agents.sh
#
# Safe to run again (to change the key / model / number of stocks).
# The API key is stored only in selfhost/config.env (not in git).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(dirname "$HERE")"
CFG="$HERE/config.env"
say() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
[ -f "$CFG" ] || { echo "先运行 selfhost/install.sh"; exit 1; }
setcfg() { if grep -q "^$1=" "$CFG"; then sed -i "s|^$1=.*|$1=$2|" "$CFG"; else echo "$1=$2" >> "$CFG"; fi; }

say "1/3 安装 TradingAgents（单独的 Python 环境，第一次要几分钟）"
[ -x "$ROOT/.venv-agents/bin/python" ] || python3 -m venv "$ROOT/.venv-agents"
"$ROOT/.venv-agents/bin/pip" install -q --upgrade pip
"$ROOT/.venv-agents/bin/pip" install -q -r "$ROOT/stocks/requirements-agents.txt"
ok "TradingAgents $("$ROOT/.venv-agents/bin/python" -c 'import tradingagents;print(tradingagents.__version__)')"

say "2/3 选大模型（按调用量付费，不是免费的）"
cat <<'EOF'
  1) DeepSeek   最便宜，推荐（每只股票大约几美分）   platform.deepseek.com
  2) Google Gemini                                    aistudio.google.com
  3) OpenAI                                           platform.openai.com
  4) Anthropic Claude                                 console.anthropic.com
EOF
read -rp "  选 1-4 [1]: " n; n="${n:-1}"
case "$n" in
  1) P=deepseek;  K=DEEPSEEK_API_KEY ;;
  2) P=google;    K=GOOGLE_API_KEY ;;
  3) P=openai;    K=OPENAI_API_KEY ;;
  4) P=anthropic; K=ANTHROPIC_API_KEY ;;
  *) echo "无效选择"; exit 1 ;;
esac
cur="$(grep "^$K=" "$CFG" | cut -d= -f2- || true)"
read -rsp "  粘贴 $K${cur:+（直接回车保留现有的）}: " key; echo
key="${key:-$cur}"; [ -n "$key" ] || { echo "没有 key，退出"; exit 1; }
setcfg "$K" "$key"
setcfg TRADINGAGENTS_LLM_PROVIDER "$P"
read -rp "  每天研判股票池里前几只？[3]: " N; setcfg AGENTS_N "${N:-3}"
read -rp "  另外每天固定研判的代码（逗号分隔，可留空，如 VOO,NVDA）: " X; setcfg AGENTS_EXTRA "$(echo "$X" | tr -d ' ' | tr a-z A-Z)"
chmod 600 "$CFG"
ok "已写入 $CFG"

say "3/3 定时任务：股票池扫描完成后跑（太平洋时间 周一到周五 15:37，第二天早上 07:17 补一次）"
sudo tee /etc/systemd/system/tools-agents.timer >/dev/null <<EOF
[Unit]
Description=tools job timer: AI 研判（TradingAgents）

[Timer]
OnCalendar=Mon..Fri 15:37
OnCalendar=Tue..Sat 07:17
Persistent=true
RandomizedDelaySec=60
Unit=tools-job@agents.service

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now tools-agents.timer >/dev/null 2>&1
ok "已开启（同一天已做过的不会重复花钱）"

echo
read -rp "  现在马上跑一次试试？[Y/n]: " go
if [ "${go:-Y}" != "n" ] && [ "${go:-Y}" != "N" ]; then
  sudo systemctl start --no-block tools-job@agents.service
  echo "  在后台跑，几分钟后刷新股票池页面。进度：tail -f $ROOT/.local-data/logs/agents.log"
fi
