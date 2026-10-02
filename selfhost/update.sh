#!/usr/bin/env bash
# Pull code updates from GitHub while keeping the data your home server produced.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(dirname "$HERE")"
cd "$ROOT"
git add -A
git -c user.name="home server" -c user.email="home@localhost" commit -qm "home data $(date '+%F %T')" || true
if git remote get-url origin >/dev/null 2>&1; then
  # on a conflict keep our side: only data files ever differ, code is never edited here
  git -c user.name="home server" -c user.email="home@localhost" pull --no-rebase --no-edit -X ours origin main
fi
"$ROOT/.venv/bin/pip" install -q -r "$HERE/requirements.txt"
python3 "$ROOT/kb/build.py" >/dev/null || true   # 主机上直接写的知识库文章也进目录
sudo systemctl restart tools-web
echo "✅ 已更新到最新代码，网页服务已重启。"
