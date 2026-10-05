---
title: 常用技术指标用 Python 怎么算
tags: [量化, 投资, 编程]
summary: SMA/EMA、RSI、MACD、布林带、ATR、成交量均线、最大回撤——每个指标的算法、pandas 代码，以及它到底能干什么、不能干什么。
---

# 常用技术指标用 Python 怎么算

技术指标本质上都是对价格和成交量做的**简单统计**：平均、差值、标准差、最大值。它们不预测未来，只是把已经发生的走势换一种方式描述出来。自己写一遍，比调用现成的库更清楚每个数字是怎么来的，也更容易发现不同软件「同一个指标算出来不一样」的原因。

下面的代码都假设有一个按日期升序排列的 DataFrame `df`，包含 `Close`、`High`、`Low`、`Volume` 四列。用 yfinance 拿数据：

```python
import numpy as np
import pandas as pd
import yfinance as yf

df = yf.download("VOO", start="2015-01-01", auto_adjust=True, progress=False)
# 新版 yfinance 即使只下一个代码也可能返回两层列名，压平成一层
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df = df[["Close", "High", "Low", "Volume"]].dropna()
```

`auto_adjust=True` 表示用复权价，拆股和分红不会在价格上留下假的跳空。为什么这很重要，见 [回测里最常见的坑](backtest-pitfalls.md)。

## 一览

| 指标 | 常用参数 | 用到的列 | 一句话 |
|---|---|---|---|
| SMA / EMA | 20、50、200 | Close | 平滑后的价格，看趋势方向 |
| RSI | 14 | Close | 最近涨的力量占比，0–100 |
| MACD | 12、26、9 | Close | 快慢两条 EMA 的差，看动量变化 |
| 布林带 | 20、2 | Close | 均线上下各加几倍标准差，看波动 |
| ATR | 14 | High、Low、Close | 平均每天波动多少钱，常用来定止损 |
| 成交量均线 | 20、50 | Volume | 今天的量相对平时是多是少 |
| 最大回撤 | — | Close 或净值 | 从最高点最多跌了多少 |

## SMA 和 EMA：移动平均

**SMA（简单移动平均）**：最近 N 天收盘价加起来除以 N。每天往前滑一格。

**EMA（指数移动平均）**：今天的 EMA = α × 今天收盘价 + (1 − α) × 昨天的 EMA，其中 α = 2 / (N + 1)。越近的价格权重越大，所以比 SMA 反应快。

```python
df["SMA50"]  = df["Close"].rolling(50).mean()
df["SMA200"] = df["Close"].rolling(200).mean()
df["EMA20"]  = df["Close"].ewm(span=20, adjust=False).mean()
```

`adjust=False` 就是上面那个递推公式，和大多数看盘软件一致。前 49 天 `SMA50` 是 NaN，这是正常的——数据不够就不该有值。

**有什么用**：判断趋势方向最朴素的办法。价格在 200 日均线上方，通常说明处于上升趋势；50 日上穿 200 日俗称「金叉」。很多长期策略（比如「跌破 200 日线就减仓」）就建立在这一条上。

**局限**：均线永远是滞后的，参数越大越滞后。在横盘震荡的市场里会反复上穿下穿，每次都是假信号。EMA 反应快，代价是假信号也更多。

## RSI：相对强弱（Wilder 算法）

步骤：

1. 每天的涨跌 = 今天收盘 − 昨天收盘。
2. 涨的部分记为「涨幅」，跌的部分取绝对值记为「跌幅」，另一边记 0。
3. 分别对涨幅、跌幅做 **Wilder 平滑**（本质是 α = 1/N 的指数平均）。
4. RS = 平均涨幅 ÷ 平均跌幅，RSI = 100 − 100 / (1 + RS)。

```python
def rsi_wilder(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)

df["RSI14"] = rsi_wilder(df["Close"])
```

注意是 `alpha=1/n`，**不是** `span=n`。用 `span=14` 相当于 α = 2/15，算出来会比看盘软件波动大，这是最常见的写错方式。Wilder 原版用前 N 天的简单平均作为起点，上面的写法起点略有不同，但几十天后两者就基本重合了。

**有什么用**：RSI 高于 70 常被叫做「超买」，低于 30 叫「超卖」。对宽基指数来说，RSI 跌到 30 以下往往出现在恐慌性下跌里，可以作为「市场情绪很差」的一个温度计。

**局限**：强势上涨时 RSI 可以连续几周停在 70 以上，按「超买就卖」做会卖在半山腰；单边下跌时也能一直在 30 以下。它更适合震荡市，在趋势市里单独用很容易吃亏。

## MACD

1. MACD 线 = 12 日 EMA − 26 日 EMA。
2. 信号线 = MACD 线的 9 日 EMA。
3. 柱状图 = MACD 线 − 信号线。

```python
ema12 = df["Close"].ewm(span=12, adjust=False).mean()
ema26 = df["Close"].ewm(span=26, adjust=False).mean()
df["MACD"]   = ema12 - ema26
df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
df["Hist"]   = df["MACD"] - df["Signal"]
```

**有什么用**：MACD 线在 0 以上说明短期均线在长期均线上方；柱状图由负转正说明动量在改善。它其实就是「均线交叉」的另一种画法，只是更直观地显示了两条线之间的距离。

**局限**：MACD 是**价格单位**，不是百分比。VOO 在 200 美元和 500 美元时，同样的 MACD 数值意义完全不同，不能拿不同时期或不同股票的 MACD 直接比较。要比较的话可以除以价格（类似 PPO 指标）。

## 布林带

- 中轨 = 20 日 SMA
- 上轨 = 中轨 + 2 × 20 日标准差
- 下轨 = 中轨 − 2 × 20 日标准差

```python
mid = df["Close"].rolling(20).mean()
std = df["Close"].rolling(20).std(ddof=0)
df["BB_mid"] = mid
df["BB_up"]  = mid + 2 * std
df["BB_low"] = mid - 2 * std
df["BB_pctB"]  = (df["Close"] - df["BB_low"]) / (df["BB_up"] - df["BB_low"])  # 0=下轨，1=上轨
df["BB_width"] = (df["BB_up"] - df["BB_low"]) / mid                           # 带宽，衡量波动
```

pandas 的 `std()` 默认是样本标准差（`ddof=1`），而布林带的原始定义和多数软件用的是总体标准差（`ddof=0`）。两者在 20 个样本时相差约 2.6%，不大，但和软件对数时要知道。

**有什么用**：带宽收窄说明近期波动很小，之后常常会出现一段较大波动（方向不确定）。`%B` 把价格在带里的位置换成 0–1，方便做筛选。

**局限**：「碰到上轨就卖、碰到下轨就买」只在震荡市里有效。真正的大趋势里价格会贴着上轨或下轨一路走。另外价格并不服从正态分布，「2 倍标准差外只有 5% 的概率」这种说法并不成立。

## ATR：平均真实波幅

**真实波幅（TR）**取下面三个数里最大的那个：

- 今天最高 − 今天最低
- |今天最高 − 昨天收盘|
- |今天最低 − 昨天收盘|

后两项是为了把跳空也算进去。ATR = TR 的 Wilder 平滑（α = 1/N）。

```python
prev_close = df["Close"].shift(1)
tr = pd.concat([
    df["High"] - df["Low"],
    (df["High"] - prev_close).abs(),
    (df["Low"]  - prev_close).abs(),
], axis=1).max(axis=1)
df["ATR14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
df["ATR_pct"] = df["ATR14"] / df["Close"]   # 换成百分比，方便跨时期比较
```

**有什么用**：ATR 不管方向，只管「一天大概能动多少」。最常见的用途是定止损和仓位：比如止损放在买入价下方 2 倍 ATR，波动大的股票自动放宽止损、减小仓位。

**局限**：同样是价格单位，跨股票比较要用 `ATR_pct`。它只反映过去的波动，财报、突发新闻造成的跳空它事先不会告诉你。

## 成交量均线

最简单：成交量的 20 日（或 50 日）SMA，再算今天的量是均量的几倍。

```python
df["VolMA20"] = df["Volume"].rolling(20).mean()
df["VolRatio"] = df["Volume"] / df["VolMA20"]
```

**有什么用**：突破时 `VolRatio` 大于 1.5 或 2，说明有较多资金参与，突破更可信一些；缩量上涨则可能动力不足。

**局限**：ETF 的成交量受很多和方向无关的因素影响：季度末、期权到期日、指数调仓、做市商活动。另外节假日前后量天然偏低。成交量信号的噪音比价格信号更大，最好只作为辅助条件。

## 最大回撤

回撤 = 当前值 ÷ 历史最高值 − 1。最大回撤就是这个序列里最小（最负）的那个数。

```python
def drawdown(series):
    peak = series.cummax()
    return series / peak - 1

dd = drawdown(df["Close"])
max_dd = dd.min()
trough = dd.idxmin()
peak_date = df["Close"].loc[:trough].idxmax()
print(f"最大回撤 {max_dd:.1%}，从 {peak_date.date()} 到 {trough.date()}")
```

**有什么用**：这是衡量「拿着它有多难受」最直观的数字，比波动率好理解得多。回测一个策略时，最大回撤往往比年化收益更能决定你实际能不能坚持下去。下跌 50% 需要上涨 100% 才能回本，这个不对称性也是看回撤的原因。

**局限**：最大回撤只是历史上**一次**最坏的情况，样本只有一个。未来完全可能出现更深的回撤。用复权价和不复权价算出来也不一样，比较策略时要统一口径。回撤的持续时间（多久才回到前高）同样重要，可以从 `dd` 序列里数连续小于 0 的天数。

## 写指标时的几个通用注意

- **NaN 是好事**：前 N 天没有值，说明代码没有偷看数据。不要用 `fillna(0)` 把它们填掉，否则 RSI 会凭空出现 0 和 100。
- **对数一致**：不同软件对 RSI、ATR 的起始值和标准差口径不同，前几十天的数字对不上很正常，后面应该能对到小数点后一两位。对不上时先查 `alpha` / `span` 和 `ddof`。
- **指标是今天收盘后才知道的**：用它产生交易信号时，最早只能在**下一个**交易日执行。回测里忘了这一点是最常见的错误，见 [回测里最常见的坑](backtest-pitfalls.md)。
- **指标不是越多越好**：上面这些大部分都是同一份收盘价的变形，高度相关。叠五个指标并不会得到五倍的信息。

对于长期持有 VOO 这类指数基金的人，这些指标更适合用来**了解市场处于什么状态**，而不是频繁买卖的依据。指数长期投资的思路见 [指数基金与定投](index-fund-dca.md)。

> 本文只是技术说明，不构成投资建议。
