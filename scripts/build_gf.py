# -*- coding: utf-8 -*-
"""怪诞小镇 Gravity Falls 专栏 → people/gf.json

数据：scripts/gf_data.json（剧集 / 片尾密码 / 台词 / 人物 / 幕后，每条附出处）
文字：本文件里的简介、专栏文章、密码入门是我写的理解，不是官方解读。
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = json.load(open(os.path.join(HERE, "gf_data.json"), encoding="utf-8"))

INTRO = [
    "12 岁的双胞胎迪普和梅宝被爸妈送到俄勒冈森林深处的小镇，跟叔公斯坦过一个暑假。叔公开了一家专骗游客的「神秘小屋」，镇上却真的到处是怪事——地精、湖怪、会附身的梦魔。迪普在林子里捡到一本写着「3」的旧日志，里面有一句：谁也别信。",
    "《怪诞小镇》（Gravity Falls）是 Alex Hirsch（亚历克斯·赫希）创作的动画，2012 年到 2016 年在迪士尼播出，两季一共 40 集。表面上它是一部「每集一个怪物」的儿童冒险片，可从第一集起，片尾字幕后都藏着一行密码，墙上的画、路牌、背景里的涂鸦也全是线索——它从一开始就是一个写好了结局的长篇谜题。",
    "赫希把自己的生活放了进去：梅宝的原型是他的双胞胎姐姐艾莉尔，斯坦叔公的原型是他爱吹牛、爱逗孩子的祖父。所以这部剧笑点很密，底子却是真的：一个夏天里，一对姐弟怎么吵架又和好，怎么开始害怕长大；两位老兄弟怎么因为一次推搡分开三十年，又怎么用一辈子去补那一下。",
    "最难得的是它在最好的时候自己停下了。赫希说第二季就是最后一季，这「100% 是我的选择」——「这部剧不是被砍，是被完成了」。所以 40 集讲完一整个夏天，夏天结束，故事也结束，不注水，不拖。",
]

SEASONS = [
    {"n": 1, "y": "2012–2013", "eps": 20, "t": "怪事一桩接一桩",
     "p": "每集一个镇上的怪物或谜团：地精、湖怪、时间旅行者、梦境。慢慢你会发现，所有怪事都指向那本日志、指向斯坦地下室里一台嗡嗡作响的机器。片尾密码从凯撒换成埃特巴什，再换成数字。"},
    {"n": 2, "y": "2014–2016", "eps": 20, "t": "谜底，和代价",
     "p": "日志的作者是谁、斯坦藏了三十年的秘密是什么、梦里那个三角形到底想要什么——一个个揭开。前半季还是单元故事，后半季一口气冲进「怪诞末日」。片尾密码全换成带关键词的维吉尼亚密码，关键词本身也是线索。"},
]

# 专栏文章：每篇引用的台词用英文开头来定位（构建时换成编号）
ESSAYS = [
    {"icon": "🧢", "t": "一个想弄明白，一个想开心",
     "lead": "迪普和梅宝是同一天出生的两种活法。",
     "body": [
         "迪普什么都想弄明白：日志、怪物、镇上的阴谋。他焦虑、爱列清单、总怕别人不把他当回事。梅宝什么都想开心：毛衣、贴纸、男孩、小猪。她吵、夸张，看起来没心没肺。",
         "剧里最聪明的地方，是从不让其中一个「赢」。迪普的认真救过全镇，也让他错过很多快乐；梅宝的开心让所有人松一口气，也让她在该面对的时候想躲进毛衣里。他们需要彼此，正因为不一样。",
         "《袜子歌剧》里，比尔骗走了迪普的身体，问梅宝：谁会为了一个蠢兄弟放弃自己努力了一整个星期的东西？梅宝想了想：迪普会。然后她自己也那样做了。这是整部剧对「兄弟姐妹」最干脆的定义——不是不吵架，是到了那一刻，答案不用想。",
     ],
     "ask": "你身边那个和你最不一样的家人，替你扛过哪些你没注意到的事？",
     "q": ["I mean, who would sacrifice", "Dipper would.", "I'm sorry, Dipper. I spent", "I couldn't break your heart", "We've always been there"]},
    {"icon": "⛵", "t": "斯坦和福特：一推，三十年",
     "lead": "这部剧真正的主角之一，是两个六十岁的老头。",
     "body": [
         "斯坦利和斯坦福是另一对双胞胎。小时候在新泽西的海边，两人一起修了一条破船，约好长大后开着它去环游世界。后来斯坦福是天才，被名校看上；斯坦利闯了祸毁了这个机会，被父亲赶出家门。多年以后两人再见面，吵起来，斯坦利推了一把——福特掉进了自己造的传送门另一边。",
         "接下来的三十年，斯坦利冒用兄弟的名字活着，开一间骗游客的小店养活自己，夜里一个人在地下室对着看不懂的日志修那台机器。镇上人都当他是个贪财的老骗子，他也从不解释。",
         "所以《他并非表面那样》《双斯坦记》那两集才那么重。斯坦从来不是个好人模范：他撒谎、坑人、身上一堆案底。可他对家人那份笨拙的忠诚，比所有漂亮话都硬。结局里福特对他说：「你是我们的英雄，斯坦利。」那一句，等了三十年。",
         "最后两个老头真的开着船出海了。小时候说过的话，绕了一大圈，还是算数。",
     ],
     "ask": "有没有一句「对不起」或者「谢谢」，你已经欠某个人很多年了？",
     "q": ["One of these days, you and me", "I dub thee", "Stanford, come back", "You're our hero, Stanley"]},
    {"icon": "🌗", "t": "怕长大，是正常的",
     "lead": "整部剧其实只讲了一个夏天，一个快要 13 岁的夏天。",
     "body": [
         "《夏日万圣节》里迪普觉得自己太大了，不该再去要糖；梅宝急了：我们在长大，剩下的万圣节没几个了！两个人站在长大的两边，一个急着过去，一个想多留一会儿。",
         "到了结局，这件事变成了真的危险。梅宝怕夏天结束、怕回家后一切都变，于是把裂缝交给了一个承诺「夏天可以永远不结束」的家伙——世界因此差点完蛋。比尔给她造了一个永远不用长大的泡泡乐园，里面什么都有，就是没有真的东西。",
         "迪普没有骂她。他说：你害怕长大，这谁能怪你？我也害怕。这句话比任何一场打斗都更像这部剧的高潮。长大不是不再害怕，是带着害怕往前走，而且最好别一个人走。",
         "最后一集梅宝对坎迪说：夏天结束了，是时候长大了。说这句话的时候她不是认命，是准备好了。",
     ],
     "ask": "你现在害怕的那件「长大」的事，是一个人扛着，还是有人知道？",
     "q": ["We're getting older", "I just felt like I was getting", "I just wish summer could last", "When we turn thirteen", "You're scared. Of growing up", "I wanted to hide in my sweater", "Summer's over, Candy"]},
    {"icon": "🔐", "t": "「谁也别信」，然后呢",
     "lead": "日志的第一句话是警告，整部剧却在讲怎么去信。",
     "body": [
         "日志上写着「TRUST NO ONE」——谁也别信。迪普把它当成第一条规矩。他怀疑斯坦、怀疑镇长、怀疑每一个人，而且很多时候他怀疑对了。",
         "可是到了《他并非表面那样》，问题被推到了最尖的地方：斯坦求梅宝别按关机键，说「你得相信我」；迪普说他可能在撒谎，这东西会毁了宇宙，用你的脑子想想！证据都站在迪普那边。梅宝看了斯坦很久，说：我相信你。",
         "她赌对了，但剧没有说迪普错。它说的是另一件事：怀疑能保护你，但只有信任能把人留在身边。写下「谁也别信」的福特自己，正是因为曾经信错了人（那个三角形），才一个人在别的世界漂了三十年。",
     ],
     "ask": "你更像迪普还是梅宝？上一次你明知有风险还选择相信一个人，是什么时候？",
     "q": ["Please don't press that shutdown", "Mabel, what if he's lying", "I trust you.", "Bill wasn't always my enemy", "Sometimes I feel like Stan hates me", "We already know how Stan feels"]},
    {"icon": "🔺", "t": "最会说话的那个",
     "lead": "比尔·赛弗不是靠力气赢的，是靠交易。",
     "body": [
         "比尔从来不硬抢。他找上的都是心里有缺口的人：想要答案的福特、想破解电脑密码的迪普、想要夏天不结束的梅宝、想夺走神秘小屋的吉迪恩。他给你想要的，代价写在你没看的那一行。",
         "第二季有一句密码说得很明白：心思简单、耳根又软的人，会轻信他听到的耳语。比尔的可怕不在于三角形和火焰，在于他总是在你最累、最孤单、最想被理解的时候出现，而且他说的话一半是真的。",
         "福特后来承认：比尔一开始是他的朋友，是他的「缪斯」。他当时太孤独了，一个肯听他说话的声音就够了。这大概是全剧最成年人的一课：最危险的诱惑，往往长得像陪伴。",
     ],
     "ask": "回头看，哪一次「太好了，正是我想要的」，后来是你付出代价最多的一次？",
     "q": ["Remember: reality is an illusion", "Pain is hilarious", "Summer in Gravity Falls can last", "This party never stops", "Bill wasn't always my enemy"]},
    {"icon": "👁️", "t": "无知是福，但幸福很无聊",
     "lead": "镇上有一群人，专门帮大家忘掉怪事。",
     "body": [
         "「盲眼社」是全剧最让人发冷的设定之一：一群穿袍子的镇民，用一把枪抹掉所有人看到的怪事。全镇都活得轻松愉快，代价是谁也不知道自己忘了什么。创立它的人是麦古吉特——一个天才，因为看到了太可怕的东西，一次次删自己的记忆，删到疯了。",
         "那一集的片尾密码是：无知是福。但幸福很无聊。这差不多就是这部剧的态度：世界是怪的，有可怕的东西，也有美的东西；你可以闭上眼过得舒服，也可以睁开眼，把怪当成冒险。",
         "结局最温柔的反转也在记忆上：斯坦为了打败比尔，让人把自己的记忆整个抹掉。是梅宝的剪贴簿——一整个夏天的照片和贴纸——一页一页把他找了回来。有些记忆疼，可它们就是你。",
     ],
     "ask": "有没有一段你曾经很想忘掉的经历，现在回头看，它其实成了你的一部分？",
     "q": ["REVEAL YOURSELF", "Take a trip. Find it", "Hey, look at me. Turn around"]},
    {"icon": "🍂", "t": "每一个愿望都实现了",
     "lead": "最后，双胞胎坐上回家的大巴。",
     "body": [
         "最后一集，镇上的人在车站给两个孩子过 13 岁生日。迪普的旁白说：这个夏天开始时，我许了一个愿，希望能逃离平凡的生活；看着你们所有人，我发现每一个愿望都实现了。",
         "他许的愿是「冒险」，得到的却是一群人：嘴硬心软的叔公、终于回家的另一个叔公、苏斯、温蒂、甚至曾经的对手。冒险是怪物给的，愿望是人给的。",
         "斯坦送他们上车时还在嘴硬：你们这两个小捣蛋，除了添乱什么也不会，可算把你们送走了。下一秒抱住他们不撒手。这部剧从头到尾都是这样——最重的话，用最不正经的方式说出来。",
         "旁白最后一句是给观众的：去旅行吧，去找它。它就在那片林子里的什么地方，等着。",
     ],
     "ask": "如果给你的这个「夏天」写一句结尾旁白，你会写什么？",
     "q": ["But looking here at all of you", "Kids, you knuckleheads", "Take a trip. Find it"]},
]

THEMES = {
    "siblings": ["👫", "兄弟姐妹"], "grow": ["🌱", "长大"], "family": ["🏠", "家"], "trust": ["🤝", "信任"],
    "weird": ["🌀", "怪诞"], "courage": ["🛡️", "勇气"], "sacrifice": ["❤️", "牺牲"], "memory": ["📒", "记忆"], "humor": ["😂", "好笑"],
}

CIPHERS = [
    {"k": "caesar", "t": "凯撒密码", "when": "第 1–6 集（还有《地毯换身》）",
     "how": "每个字母往回退 3 位：D→A、E→B、F→C……A 往回退就绕到 X。", "eg": ["ZHOFRPH", "WELCOME"],
     "tip": "看到 WKH 很可能就是 THE。"},
    {"k": "atbash", "t": "埃特巴什密码", "when": "第 7–13 集",
     "how": "字母表首尾对折：A↔Z、B↔Y、C↔X……第 6 集的密码就预告了：「凯撒先生下周请假，由埃特巴什先生代课。」", "eg": ["GSV", "THE"],
     "tip": "看到 GSV 就是 THE；它自己就是自己的反函数，加密和解密一样。"},
    {"k": "a1z26", "t": "A1Z26 数字密码", "when": "第 14–19 集",
     "how": "A=1、B=2……Z=26，字母之间用短横连，单词之间空格。", "eg": ["20-15 2-5", "TO BE"],
     "tip": "最简单的一种，但第一季结局把它和另外两种叠在一起用。"},
    {"k": "combo", "t": "组合密码", "when": "第 20 集和几集的「结束页」",
     "how": "三层套娃：先 A1Z26 把数字变字母，再埃特巴什对折，最后凯撒退 3 位。", "eg": ["5-19-23-6-21-16", "SEARCH"],
     "tip": "解码器里选「组合」一步到位。"},
    {"k": "vigenere", "t": "维吉尼亚密码", "when": "第二季全部",
     "how": "要一个关键词。关键词的每个字母代表一个位移量（A=0、B=1……），轮流套在密文上往回退。没有关键词几乎解不开。", "eg": ["SMOFZQA", "WELCOME（关键词 WIDDLE）"],
     "tip": "第二季的关键词通常藏在当集画面里，或者上一集的密码会预告。"},
]

# ---------------- 组装 ----------------
quotes = []
for i, q in enumerate(D["quotes"]):
    x = dict(q); x["n"] = i
    quotes.append(x)

def find(prefix):
    for q in quotes:
        if q["en"].startswith(prefix):
            return q["n"]
    raise SystemExit("找不到台词：" + prefix)

essays = []
for e in ESSAYS:
    x = dict(e); x["q"] = [find(p) for p in e["q"]]
    essays.append(x)

eps = []
for e in D["episodes"]:
    c = e.get("cipher") or {}
    x = {"code": e["code"], "title": e["title"], "zh": e["zh"], "date": e["date"], "note": e["note"], "star": bool(e.get("star"))}
    cs = []
    for cc in [c] + (c.get("extra") or []):
        if cc.get("encoded"):
            t = cc["type"]
            k = {"Caesar": "caesar", "Atbash": "atbash", "A1Z26": "a1z26", "combined": "combo"}.get(t, "vigenere")
            cs.append({"k": k, "enc": cc["encoded"], "dec": cc["decoded"], "zh": cc.get("zh") or "", "key": cc.get("key") or "",
                       "note": cc.get("note") or "", "part": cc.get("verified") == "partial"})
    x["ci"] = cs
    if not cs:
        x["miss"] = c.get("note") or "未能核实"
    eps.append(x)

# 人物：附上他们的台词
SPK = {"dipper": "Dipper", "mabel": "Mabel", "stan": "Grunkle Stan", "ford": "Ford", "bill": "Bill", "wendy": "Wendy", "candy-grenda": "Candy"}
ICON = {"dipper": "🧢", "mabel": "🌈", "stan": "🎩", "ford": "📓", "soos": "🔧", "wendy": "🪓", "bill": "🔺", "gideon": "🔮",
        "pacifica": "💎", "waddles": "🐷", "mcgucket": "🦝", "candy-grenda": "👯", "robbie": "🎸", "journal3": "📕"}
people = []
for p in D["people"]:
    x = dict(p); x["icon"] = ICON.get(p["id"], "🌲")
    key = SPK.get(p["id"])
    x["q"] = [q["n"] for q in quotes if key and q["who"].startswith(key)]
    people.append(x)

out = {
    "intro": INTRO, "seasons": SEASONS, "essays": essays, "themes": THEMES, "ciphers": CIPHERS,
    "quotes": quotes, "people": people, "episodes": eps, "shorts": D["shorts"], "trivia": D["trivia"],
}
json.dump(out, open(os.path.join(ROOT, "people", "gf.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("gf.json:", len(quotes), "句台词,", len(eps), "集,", sum(len(e["ci"]) for e in eps), "条密码,", len(people), "个人物,", len(essays), "篇专栏")
