# 🧰 工具箱（boliunew/tools）

个人工具网站：现场工具、股票、新闻、学习、生活、听书电台……全部是静态页面，托管在 GitHub Pages
（<https://boliunew.github.io/tools/>），数据由 GitHub Actions 定时生成，后端功能放在 Cloudflare Workers，提醒统一推送到 Telegram。

## 整体结构

```
你的手机 / 电脑 ──► GitHub Pages（*.html + 各目录下的 data/*.json）
                       ▲  每天定时更新数据（GitHub Actions，.github/workflows/）
                       │
Telegram ◄── 推送 ── scripts/notify.py（各个自动任务）
   ▲ ▼
Cloudflare Worker（cf/worker.js）：拍照认柜号 / 单据、语音翻译、AI 问答、盘中股价提醒
```

## 页面和数据

| 板块 | 页面 | 数据 / 生成脚本 | 自动任务 |
|---|---|---|---|
| 现场工具（柜号校验、📷 拍照识别、装柜、验柜、日志） | `work.html` | 本地存储 + Cloudflare `/ocr` | — |
| 今日股票池（短线信号、回测、自选、AI 盘后解读） | `stocks.html` | `stocks/scan.py` → `stocks/data/`；`stocks/ai_review.py` | 每日股票池扫描 |
| 股价提醒 | `stocks.html` | `stocks/alerts.py`（GitHub issue「股价提醒: VOO 跌到 650」） | 股价提醒登记 + 扫描后检查 |
| 信号日报（6 只股票的 RSI / 趋势 / 吸筹） | Telegram | `stocks/signal_bot.py` | 信号日报推送 |
| 长线池 | `stocks.html` | `longterm/build.py` | 长线池（每周六） |
| 财报与经济日历、财报提醒 | `earnings.html` | `earnings/build.py`、`stocks/earn_remind.py` | 财报与经济日历 |
| 每日简报（AI 整理） | `brief.html` | `brief/build.py` | 每日简报 |
| 新闻 / 国际局势 / 每日一句 | `news.html`、`card.html` | `news/*.py`、`card/today.py` | 英文新闻精选 |
| 打折雷达 / 网页监控 | `deals.html`、`monitor.html` | `deals/`、`monitor/check.py` | 打折促销、网页监控 |
| 机票比价 | `flights.html` | 纯前端 | — |
| 知识库、全站搜索 | `kb.html`、`search.html` | `kb/build.py`、`scripts/build_search.py` | 知识库目录与全站搜索 |
| 系统状态 | `status.html` | `scripts/health_check.py` → `status/health.json` | 系统体检 |

其他页面（城市生活、Amtrak、海岸线、电台、听书、语言练习……）的数据在同名目录里，生成脚本多在 `scripts/build_*.py`。
所有页面共用：`nav.js`（左侧穿越抽屉）、`theme.js`（深浅色）、`sw.js`（离线缓存）、`sync.js`（家里主机同步）。

## 推送（Telegram）

所有提醒都走 `scripts/notify.py`：GitHub 评论风格的 Markdown 自动转成 Telegram 格式，发送失败时退回 GitHub issue 留言 + @。
想关掉某一类，编辑根目录 `notify.json` 的 `off` 列表（`signal` `alert` `monitor` `deals` `holiday` `health` `brief` `ai` `earnings`）。

## Cloudflare 后端（`cf/`）

`cf/worker.js` 由 **Cloudflare 后端** 工作流（`cf/deploy.sh`）自动部署到 `https://tools-api.boliunew.workers.dev`，部署完会自检。

- `POST /ocr`：拍照认柜号 / 封条号（Workers AI 视觉模型 + ISO 6346 校验），需要首页密码解锁后存的密钥
- Telegram 机器人：照片 → 柜号 / 单据字段；语音 → 中西英翻译（附西语朗读）；打中文 → AI 问答（带行情和股票池数据）；
  `/q` `/alert` `/list` `/del` `/brief` `/usage`
- 定时任务：美股交易时间每 5 分钟检查股价提醒和大盘异动
- 改了首页密码后，要手动运行一次 Cloudflare 后端工作流

## 需要的 Secrets（Settings → Secrets and variables → Actions）

| 名字 | 用途 |
|---|---|
| `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` | Workers AI（简报、盘后解读）、部署 Cloudflare 后端 |
| `TG_BOT_TOKEN`、`TG_CHAT_ID` | Telegram 推送和机器人 |
| `VOCAB_GIST_ID` | 语境词库备份 |

`GITHUB_TOKEN` 是自动提供的。

## 回测的局限（重要）

股票池的信号统计用的是**现在的**标普 500 + 纳指 100 成分股，存在幸存者偏差：已经做了「按调入标普 500 的日期才计入」的修正，
但这期间被调出、退市的股票拿不到免费数据，不在样本里，所以历史成绩偏乐观。详见 `stocks/scan.py` 的 `membership()`。

## 本地开发

```bash
pip install -r stocks/requirements.txt pytest
python -m pytest -q tests          # Python 核心计算的测试
node --test tests/worker.test.mjs  # Cloudflare 后端的柜号逻辑
python stocks/scan.py --demo       # 不联网，用模拟数据跑一遍扫描
python -m http.server 8000         # 本地预览网站
```

每次推送都会自动跑测试（**测试** 工作流）。

## 家里主机（可选）

`selfhost/`：把整个网站和数据任务搬到家里的迷你主机（Ubuntu + Tailscale），只有自己的设备能访问。步骤见 `selfhost/README.md`。
