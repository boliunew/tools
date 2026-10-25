#!/usr/bin/env bash
# 部署 cf/worker.js 到 Cloudflare（GitHub Actions 里跑）。需要 CLOUDFLARE_API_TOKEN、CLOUDFLARE_ACCOUNT_ID。
# 自动：注册 workers.dev 子域名（第一次）、建 KV、从首页读密码校验值 CHECK、部署、设置密钥、冒烟测试、把接口地址写进 cf.json。
set -uo pipefail
cd "$(dirname "$0")/.."
note() { echo "::notice title=Cloudflare::$*"; }
die() { echo "::error title=Cloudflare::$*"; exit 1; }
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] && [ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ] || die "没有设置 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID"
API="https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID"
cf() { curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" "$@"; }
NAME=tools-api

# 1. workers.dev 子域名
SUB=$(cf "$API/workers/subdomain" | jq -r '.result.subdomain // empty')
if [ -z "$SUB" ]; then
  for want in boliunew boliunew-tools "boliunew-$(date +%s | tail -c 5)"; do
    r=$(cf -X PUT "$API/workers/subdomain" -d "{\"subdomain\":\"$want\"}")
    if [ "$(echo "$r" | jq -r .success)" = true ]; then SUB=$want; break; fi
    echo "subdomain $want: $(echo "$r" | jq -c .errors)"
  done
fi
[ -n "$SUB" ] || die "注册 workers.dev 子域名失败（到 Cloudflare 后台 Workers & Pages 里点一次 Set up subdomain 再重跑）"
URL="https://$NAME.$SUB.workers.dev"

# 2. KV
KV=$(cf "$API/storage/kv/namespaces?per_page=100" | jq -r '.result[]? | select(.title=="tools-api-kv") | .id' | head -1)
[ -n "$KV" ] || KV=$(cf -X POST "$API/storage/kv/namespaces" -d '{"title":"tools-api-kv"}' | jq -r '.result.id // empty')
[ -n "$KV" ] || die "创建 KV 失败"

# 3. 首页密码的校验值（解锁后浏览器存的那串密钥 sha256 后等于它）
CHECK=$(grep -o "CHECK = '[0-9a-f]\{64\}'" index.html | head -1 | grep -o "[0-9a-f]\{64\}")
[ -n "$CHECK" ] || note "首页没有密码锁，/ocr 只能用测试密钥调用"

cat > cf/wrangler.toml <<TOML
name = "$NAME"
main = "worker.js"
compatibility_date = "2025-09-01"
workers_dev = true
[ai]
binding = "AI"
[[kv_namespaces]]
binding = "KV"
id = "$KV"
[vars]
CHECK = "$CHECK"
SITE = "https://boliunew.github.io/tools"
[triggers]
crons = ["*/5 13-21 * * 1-5"]
TOML

# 4. 部署
npx --yes wrangler@4 deploy --config cf/wrangler.toml 2>&1 | tail -25
code=${PIPESTATUS[0]}
[ "$code" = 0 ] || die "wrangler deploy 失败（看上面的日志）"

# 5. 密钥：测试密钥每次重新生成；Telegram 有就带上
TEST_KEY=$(openssl rand -hex 24); echo "::add-mask::$TEST_KEY"
jq -n --arg t "$TEST_KEY" --arg b "${TG_BOT_TOKEN:-}" --arg c "${TG_CHAT_ID:-}" \
  '{TEST_KEY:$t} + (if $b != "" and $c != "" then {TG_BOT_TOKEN:$b, TG_CHAT_ID:$c} else {} end)' > /tmp/secrets.json
npx --yes wrangler@4 secret bulk /tmp/secrets.json --config cf/wrangler.toml 2>&1 | tail -5
rm -f /tmp/secrets.json

# 6. Telegram 机器人：消息推到 /tg/<密钥>，再设好命令菜单
if [ -n "${TG_BOT_TOKEN:-}" ]; then
  HOOK=$(printf 'tg-hook:%s' "$TG_BOT_TOKEN" | sha256sum | cut -c1-32)
  r=$(curl -sS "https://api.telegram.org/bot$TG_BOT_TOKEN/setWebhook" -H "Content-Type: application/json" \
      -d "{\"url\":\"$URL/tg/$HOOK\",\"secret_token\":\"$HOOK\",\"allowed_updates\":[\"message\",\"edited_message\"],\"drop_pending_updates\":true}")
  note "Telegram webhook：$(echo "$r" | jq -c '{ok, description}')"
  curl -sS "https://api.telegram.org/bot$TG_BOT_TOKEN/setMyCommands" -H "Content-Type: application/json" -d '{"commands":[
    {"command":"help","description":"我能做什么"},
    {"command":"q","description":"查股价：/q NVDA"},
    {"command":"alert","description":"设提醒：/alert VOO 跌到 650"},
    {"command":"list","description":"我的提醒"},
    {"command":"del","description":"删除提醒：/del 3"},
    {"command":"brief","description":"今天的简报"}]}' >/dev/null
fi

# 7. 冒烟测试
for i in 1 2 3 4 5 6; do h=$(curl -sS "$URL/health"); echo "$h" | jq -e .ok >/dev/null 2>&1 && break; sleep 10; done
note "已部署 $URL ｜ health: $h"
python3 - "$URL" "$TEST_KEY" <<'PY'
import base64, io, json, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont
url, key = sys.argv[1], sys.argv[2]
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36"
img = Image.new("RGB", (900, 520), (178, 34, 34))           # 红色箱门
d = ImageDraw.Draw(img)
try:
    big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 78)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
except Exception:
    big = small = ImageFont.load_default()
d.text((60, 70), "CSQU 305438", fill="white", font=big)
d.rectangle((640, 62, 720, 160), outline="white", width=5); d.text((660, 70), "3", fill="white", font=big)
d.text((60, 200), "22G1", fill="white", font=small)
d.text((60, 300), "MAX GROSS 30,480 KG", fill="white", font=small)
d.text((60, 380), "TARE 2,200 KG", fill="white", font=small)
buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
body = json.dumps({"image": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}).encode()
req = urllib.request.Request(url + "/ocr", data=body, method="POST", headers={"Content-Type": "application/json", "X-Tools-Key": key, "User-Agent": UA})
import time
for attempt in range(4):   # 新密钥生效要几秒
    try:
        urllib.request.urlopen(urllib.request.Request(url + "/intraday", data=b"", method="POST", headers={"X-Tools-Key": key, "User-Agent": UA}), timeout=30)
        break
    except urllib.error.HTTPError as e:
        if e.code != 401: break
        time.sleep(10)
    except Exception:
        time.sleep(5)
try:
    r = json.loads(urllib.request.urlopen(req, timeout=90).read())
    best = (r.get("containers") or [{}])[0]
    print("::notice title=柜号识别测试::%s ｜ 期望 CSQU3054383，读到 %s（校验%s）｜ %s ms ｜ 全部：%s" % (
        r.get("model"), best.get("no"), "通过" if best.get("ok") else "不通过", r.get("ms"), json.dumps(r, ensure_ascii=False)[:600]))
except urllib.error.HTTPError as e:
    print("::warning title=柜号识别测试::HTTP %s %s" % (e.code, e.read()[:600].decode("utf-8", "replace")))
except Exception as e:
    print("::warning title=柜号识别测试::%s" % e)
try:
    st = urllib.request.urlopen(urllib.request.Request(url + "/selftest", data=b"", method="POST", headers={"X-Tools-Key": key, "User-Agent": UA}), timeout=120).read().decode()
    print("::notice title=机器人自检（翻译 / 朗读 / 听写）::" + st[:900])
except Exception as e:
    print("::warning title=机器人自检::%s" % e)
req = urllib.request.Request(url + "/intraday?force=1", data=b"", method="POST", headers={"X-Tools-Key": key, "User-Agent": UA})
try:
    print("::notice title=盘中提醒测试::" + urllib.request.urlopen(req, timeout=60).read().decode()[:600])
except Exception as e:
    print("::warning title=盘中提醒测试::%s" % e)
PY

# 8. 把接口地址告诉网页
echo "{\"api\":\"$URL\"}" > cf.json
