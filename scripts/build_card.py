"""Build the data for card.html (每日一句 · 单词抽卡).

From the vocab dataset embedded in vocab.html and the idioms in english.html:
  card/idx.txt        the 20,000 words in frequency order (one per line) → rank lookup, rarity
  card/cNN.json       500 words per chunk: [phonetic, short meaning, example en, example zh]
  card/daily.json     the 每日一句 pool: public-domain quotes (translated here) + idioms / 口头禅 / 易错
Run whenever vocab.html or english.html's idioms change:  python scripts/build_card.py
"""
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "card")
CHUNK = 500
NAME = re.compile(r"男子名|女子名|人名|姓氏|地名|（姓）|\(姓\)|美国.{0,6}(州|城市)|英国.{0,4}城市")

# Quotes by authors who died before 1929 (public domain), checked against their sources;
# popular misattributions in the source list were dropped.
QUOTES = [
    ("Ralph Waldo Emerson", "The only way to have a friend is to be one.", "想要有朋友，唯一的办法是先成为别人的朋友。"),
    ("Ralph Waldo Emerson", "Life is a progress, and not a station.", "人生是一段前行的旅程，而不是一个停靠的车站。"),
    ("Ralph Waldo Emerson", "Make the most of yourself, for that is all there is of you.", "尽力活出最好的自己，因为你只有这一个自己。"),
    ("William Shakespeare", "Be great in act, as you have been in thought.", "想得伟大，也要做得伟大。"),
    ("William Shakespeare", "Having nothing, nothing can he lose.", "一无所有，也就无所可失。"),
    ("Oscar Wilde", "Anybody can make history. Only a great man can write it.", "谁都能创造历史，但只有伟人才写得出历史。"),
    ("William Shakespeare", "Speak low, if you speak love.", "若要诉说爱意，请轻声细语。"),
    ("Oscar Wilde", "The only thing to do with good advice is to pass it on. It is never of any use to oneself.", "好的忠告唯一的用处就是转送给别人——它对自己从来没用。"),
    ("William Shakespeare", "Love all, trust a few, do wrong to none.", "爱所有人，信任少数人，不负任何人。"),
    ("George Eliot", "What do we live for, if it is not to make life less difficult for each other?", "我们活着，若不是为了让彼此的生活少些艰难，又是为了什么？"),
    ("Mark Twain", "A thing long expected takes the form of the unexpected when at last it comes.", "期待已久的事，真正到来时，反倒像是意料之外。"),
    ("William Shakespeare", "We know what we are, but know not what we may be.", "我们知道自己现在是什么，却不知道将来会成为什么。"),
    ("Benjamin Disraeli", "One secret of success in life is for a man to be ready for his opportunity when it comes.", "成功的秘诀之一，是机会来临时你已经准备好了。"),
    ("Oscar Wilde", "Experience is the name every one gives to their mistakes.", "所谓经验，不过是每个人给自己的错误起的名字。"),
    ("Benjamin Franklin", "Well done is better than well said.", "说得好不如做得好。"),
    ("Ralph Waldo Emerson", "So is cheerfulness, or a good temper, the more it is spent, the more remains.", "好心情也是这样：越是付出，剩下的越多。"),
    ("Abraham Lincoln", "As our case is new, so we must think anew, and act anew.", "我们面对的是新局面，就必须用新的方式去思考、去行动。"),
    ("Thomas Jefferson", "Never put off till tomorrow what you can do today.", "今天能做的事，绝不要拖到明天。"),
    ("Hannah More", "It is not so important to know everything as to appreciate what we learn.", "无所不知并不那么重要，珍惜所学才重要。"),
    ("Ralph Waldo Emerson", "Bad times have a scientific value. These are occasions a good learner would not miss.", "困难时期自有它的研究价值，善于学习的人不会错过这样的机会。"),
    ("Mark Twain", "To get the full value of joy you must have somebody to divide it with.", "想把快乐享受到十足，就得有人和你分享。"),
    ("Frederick Douglass", "If there is no struggle, there is no progress.", "没有奋斗，就没有进步。"),
    ("Ralph Waldo Emerson", "Nature is a mutable cloud which is always and never the same.", "自然像一朵变幻的云，永远是它，又永远不是它。"),
    ("William Shakespeare", "God has given you one face, and you make yourselves another.", "上帝给了你们一张脸，你们却给自己另造了一张。"),
    ("Benjamin Disraeli", "Action may not always bring happiness; but there is no happiness without action.", "行动不一定带来幸福，但没有行动就一定没有幸福。"),
    ("Ralph Waldo Emerson", "The years teach much which the days never know.", "岁月教给我们的，是一天一天里体会不到的东西。"),
    ("Benjamin Franklin", "One today is worth two tomorrows.", "一个今天抵得上两个明天。"),
    ("Benjamin Disraeli", "Never apologize for showing feeling. When you do so, you apologize for truth.", "不要为流露感情而道歉，那等于为真实道歉。"),
    ("Mark Twain", "When in doubt, tell the truth.", "拿不准的时候，就说实话。"),
    ("William Shakespeare", "He that is giddy thinks the world turns round.", "自己头晕的人，以为是世界在转。"),
    ("Ralph Waldo Emerson", "Skill to do comes of doing.", "做事的本领来自做事本身。"),
    ("Benjamin Disraeli", "The greatest good you can do for another is not just to share your riches but to reveal to him his own.", "你能给别人最大的帮助，不只是分享你的财富，而是让他发现自己的财富。"),
    ("Benjamin Disraeli", "Through perseverance many people win success out of what seemed destined to be certain failure.", "靠着坚持，许多人从看似注定的失败中赢得了成功。"),
    ("Benjamin Franklin", "Experience keeps a dear school, but fools will learn in no other.", "经验这所学校学费昂贵，可愚人偏偏只肯在这里学。"),
    ("Elbert Hubbard", "There is no failure except in no longer trying.", "除了不再尝试，没有真正的失败。"),
    ("Henry David Thoreau", "The only way to speak the truth is to speak lovingly.", "说真话唯一的方式，是怀着爱去说。"),
    ("Ralph Waldo Emerson", "In skating over thin ice, our safety is in our speed.", "在薄冰上滑行，速度就是安全。"),
    ("Francis Bacon", "A wise man will make more opportunities than he finds.", "智者创造的机会比他找到的多。"),
    ("Ralph Waldo Emerson", "Our distrust is very expensive.", "我们的不信任，代价非常高。"),
    ("Abraham Lincoln", "Always bear in mind that your own resolution to succeed is more important than any other one thing.", "永远记住：你自己想成功的决心，比任何别的事情都重要。"),
    ("Elbert Hubbard", "The greatest mistake you can make in life is to be continually fearing you will make one.", "人生最大的错误，就是总担心自己会犯错。"),
    ("Ralph Waldo Emerson", "Nothing is at last sacred but the integrity of your own mind.", "归根到底，没有什么比你自己内心的正直更神圣。"),
    ("Henry David Thoreau", "The world is but a canvas to our imagination.", "世界不过是想象力的一块画布。"),
    ("Ralph Waldo Emerson", "Nothing great was ever achieved without enthusiasm.", "没有热情，就成就不了任何伟大的事。"),
    ("Ralph Waldo Emerson", "Good luck is another name for tenacity of purpose.", "好运不过是坚持目标的另一个名字。"),
    ("Benjamin Disraeli", "Ignorance never settles a question.", "无知从来解决不了问题。"),
    ("Abraham Lincoln", "Truth is generally the best vindication against slander.", "面对诽谤，真相通常是最好的辩护。"),
    ("William Shakespeare", "The fault, dear Brutus, is not in our stars, but in ourselves, that we are underlings.", "亲爱的勃鲁托斯，我们屈居人下，错不在命运，而在我们自己。"),
    ("Abraham Lincoln", "A house divided against itself cannot stand.", "一座自相分裂的房子是站不住的。"),
    ("Francis Bacon", "A prudent question is one half of wisdom.", "问得明智，就已经有了一半的智慧。"),
    ("Elizabeth Barrett Browning", "Whoso loves, believes the impossible.", "心中有爱的人，相信不可能的事。"),
    ("Abraham Lincoln", "Important principles may, and must, be inflexible.", "重要的原则可以而且必须毫不动摇。"),
    ("Henry David Thoreau", "Things do not change; we change.", "事物没有改变，是我们改变了。"),
    ("Ralph Waldo Emerson", "What is a weed? A plant whose virtues have not yet been discovered.", "什么是杂草？就是优点还没被发现的植物。"),
    ("Elbert Hubbard", "To avoid criticism, do nothing, say nothing, be nothing.", "想不被批评？那就什么都别做、什么都别说、什么都别是。"),
    ("Benjamin Franklin", "There never was a good knife made of bad steel.", "坏钢从来打不出好刀。"),
    ("William Shakespeare", "To climb steep hills requires slow pace at first.", "攀登陡峭的山，起初要放慢脚步。"),
    ("Elbert Hubbard", "A failure is a man who has blundered, but is not able to cash in the experience.", "失败者是犯了错，却不会把教训变成收获的人。"),
    ("Ralph Waldo Emerson", "Our strength grows out of our weaknesses.", "我们的力量，从我们的弱点中生长出来。"),
    ("Ralph Waldo Emerson", "We aim above the mark to hit the mark.", "瞄准得比目标高一点，才能射中目标。"),
    ("Benjamin Disraeli", "The secret of success is constancy to purpose.", "成功的秘诀在于始终如一地坚持目标。"),
    ("James Russell Lowell", "A weed is no more than a flower in disguise.", "杂草不过是乔装打扮的花。"),
    ("Ralph Waldo Emerson", "Self-trust is the first secret of success.", "自信是成功的第一个秘诀。"),
    ("Ralph Waldo Emerson", "Thought is the blossom; language the bud; action the fruit behind it.", "思想是花，语言是蕾，行动是其后的果实。"),
    ("Mark Twain", "The exercise of an extraordinary gift is the supremest pleasure in life.", "施展非凡的天赋，是人生最大的乐趣。"),
    ("Ralph Waldo Emerson", "A hero is no braver than an ordinary man, but he is braver five minutes longer.", "英雄并不比普通人更勇敢，只是多勇敢了五分钟。"),
    ("Abraham Lincoln", "Character is like a tree and reputation like its shadow. The shadow is what we think of it; the tree is the real thing.", "品格如树，名声如影。影子是别人眼中的它，树才是它本身。"),
    ("Ralph Waldo Emerson", "Truth, and goodness, and beauty, are but different faces of the same All.", "真、善、美，不过是同一整体的不同面孔。"),
    ("Henry Ward Beecher", "Every artist dips his brush in his own soul, and paints his own nature into his pictures.", "每个画家都是用自己的灵魂蘸笔，把自己的本性画进作品里。"),
    ("Robert Louis Stevenson", "To be what we are, and to become what we are capable of becoming, is the only end of life.", "做真实的自己，并成为自己能够成为的人，这是人生唯一的目的。"),
    ("Ralph Waldo Emerson", "Each man has his own vocation; his talent is his call. There is one direction in which all space is open to him.", "每个人都有自己的天职，天赋就是召唤；总有一个方向，整片天地都为他敞开。"),
    ("Henry Wadsworth Longfellow", "He that respects himself is safe from others; he wears a coat of mail that none can pierce.", "自重的人不受他人伤害，他身穿一副无人能刺穿的铠甲。"),
    ("Ralph Waldo Emerson", "Everything in the universe goes by indirection. There are no straight lines.", "宇宙万物都是迂回前行的，世上没有直线。"),
    ("Ralph Waldo Emerson", "Great men are they who see that spiritual is stronger than any material force, that thoughts rule the world.", "伟大的人看得出：精神比任何物质力量都强大，思想统治着世界。"),
    ("Benjamin Franklin", "Beware of little expenses; a small leak will sink a great ship.", "当心小开销，小小的漏洞也能让大船沉没。"),
    ("Ralph Waldo Emerson", "Imagination is not a talent of some men but is the health of every man.", "想象力不是少数人的天赋，而是每个人的健康。"),
    ("Benjamin Disraeli", "We make our fortunes and we call them fate.", "命运是我们自己造就的，我们却称之为天意。"),
    ("Ralph Waldo Emerson", "Good thoughts are no better than good dreams, unless they be executed.", "好的想法若不付诸实行，和美梦没什么两样。"),
    ("William Shakespeare", "How far that little candle throws his beams! So shines a good deed in a naughty world.", "那支小小的蜡烛，光芒照得多远！一件善行在这污浊的世上也是这样闪耀。"),
    ("Ralph Waldo Emerson", "Do not waste yourself in rejection, nor bark against the bad, but chant the beauty of the good.", "不要把自己耗在否定上，也不要对坏事狂吠，去歌颂美好的事物吧。"),
    ("Elbert Hubbard", "A little more persistence, a little more effort, and what seemed hopeless failure may turn to glorious success.", "再多一点坚持，再多一点努力，看似无望的失败也许就会变成辉煌的成功。"),
    ("Ralph Waldo Emerson", "If the stars should appear one night in a thousand years, how would men believe and adore.", "假如星星一千年才出现一夜，人们将会多么虔信、多么崇拜。"),
    ("Ralph Waldo Emerson", "To be great is to be misunderstood.", "伟大就意味着被误解。"),
    ("Robert Louis Stevenson", "There is no duty we so much underrate as the duty of being happy. By being happy, we sow anonymous benefits upon the world.", "我们最低估的责任，就是让自己快乐。快乐的时候，我们在不知不觉中为世界播下了好处。"),
    ("William Shakespeare", "Be not afraid of greatness: some are born great, some achieve greatness, and some have greatness thrust upon 'em.", "不要害怕伟大：有人生而伟大，有人成就伟大，有人被迫伟大。"),
    ("Tryon Edwards", "He that never changes his opinions, never corrects his mistakes, will never be wiser on the morrow than he is today.", "从不改变看法、从不纠正错误的人，明天也永远不会比今天更聪明。"),
    ("Mark Twain", "Wrinkles should merely indicate where smiles have been.", "皱纹只该标出曾经有过笑容的地方。"),
    ("Benjamin Franklin", "Lost time is never found again.", "失去的时间再也找不回来。"),
    ("Samuel Johnson", "Great works are performed not by strength but by perseverance.", "伟大的事业不是靠力气完成的，而是靠坚持。"),
    ("Charles Dickens", "No one is useless in this world who lightens the burdens of another.", "能为别人减轻负担的人，在这世上就不是无用的人。"),
    ("Henry David Thoreau", "If one advances confidently in the direction of his dreams, and endeavors to live the life which he has imagined, he will meet with a success unexpected in common hours.", "一个人若自信地朝梦想的方向前进，努力去过他想象中的生活，就会在平凡的日子里遇到意想不到的成功。"),
    ("Alfred Tennyson", "To strive, to seek, to find, and not to yield.", "去奋斗、去追寻、去发现，永不屈服。"),
    ("Henry Wadsworth Longfellow", "Lives of great men all remind us we can make our lives sublime.", "伟人的一生都在提醒我们：我们也能让自己的人生崇高。"),
    ("Charles Darwin", "A man who dares to waste one hour of time has not discovered the value of life.", "敢浪费一小时的人，还没有发现生命的价值。"),
]
def short_trans(t):
    t = t.replace("\\r", "").replace("\r", "")
    keep = []
    for p in re.split(r"[；\n]", t):
        p = p.strip()
        if not p or "[计]" in p or re.match(r"^\[[^\]]{1,4}\]", p):
            continue
        p = re.sub(r"\[[^\]]{1,4}\]\s*", "", p)
        m = re.match(r"^([a-z]+\.(?:\s*&\s*[a-z]+\.)?)\s*(.*)$", p)
        pos, body = (m.group(1) + " ", m.group(2)) if m else ("", p)
        body = "，".join([x.strip() for x in re.split(r"[,，]", body) if x.strip()][:4])
        keep.append(pos + body)
        if len("；".join(keep)) > 24 or len(keep) >= 2:
            break
    s = "；".join(keep) or re.sub(r"\[[^\]]*\]\s*", "", re.split(r"[；\n]", t)[0]).strip()
    return s[:44]


def load_vocab():
    html = open(os.path.join(ROOT, "vocab.html"), encoding="utf-8").read()
    raw = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
    return raw["w"], raw["s"]


def load_idioms():
    html = open(os.path.join(ROOT, "english.html"), encoding="utf-8").read()
    i = html.index("var IDI = ") + len("var IDI = ")
    obj, _ = json.JSONDecoder().raw_decode(html[i:])
    return obj


def gloss_for(text, rank, rows, skip_below=2000):
    out, seen = [], set()
    for tok in re.findall(r"[A-Za-z]+(?:'[a-z]+)?", text):
        w = tok.lower()
        cand = [w]
        for suf, rep in (("ies", "y"), ("ied", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ly", ""), ("er", ""), ("est", "")):
            if w.endswith(suf) and len(w) > len(suf) + 2:
                cand.append(w[: -len(suf)] + rep)
        for c in cand:
            r = rank.get(c)
            if r is not None and r >= skip_below and c not in seen and not NAME.search(rows[r][2]):
                seen.add(c)
                out.append([c, rows[r][0], rows[r][1], r])
                break
    return out[:5]


def main():
    W, S = load_vocab()
    os.makedirs(OUT, exist_ok=True)
    # ---- words: index + chunks
    rows, rank = [], {}
    for i, w in enumerate(W):
        ex = [S[j] for j in w[3] if j < len(S)]
        ex = [e for e in ex if 12 <= len(e[0]) <= 110]
        ex.sort(key=lambda e: (0 if e[1] else 1, len(e[0])))
        e = ex[0] if ex else ["", ""]
        rows.append([w[1], short_trans(w[2]), e[0], e[1] if len(e) > 1 else ""])
        rank.setdefault(w[0].lower(), i)
    with open(os.path.join(OUT, "idx.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(w[0] for w in W))
    for c in range(0, len(rows), CHUNK):
        with open(os.path.join(OUT, "c%02d.json" % (c // CHUNK)), "w", encoding="utf-8") as f:
            json.dump(rows[c:c + CHUNK], f, ensure_ascii=False, separators=(",", ":"))
    # ---- 每日一句 pool
    rnd = random.Random(20261001)
    A = [{"k": "名言", "en": e, "zh": z, "by": a, "g": gloss_for(e, rank, rows)} for a, e, z in QUOTES]
    IDI = load_idioms()
    lvname = {"elem": "小学", "mid": "初中", "high": "高中", "col": "大学"}
    B, C = [], []
    for lv in ("elem", "mid", "high", "col"):
        for it in IDI[lv]["idiom"]:
            B.append({"k": "习语", "en": it[0], "lit": it[1], "zh": it[3] or it[2], "note": it[2], "ex": it[4], "exzh": it[5], "lv": lvname[lv]})
        for it in IDI[lv]["talk"]:
            B.append({"k": "口头禅", "en": it[0], "zh": it[1], "note": it[2], "ex": it[3], "exzh": it[4], "lv": lvname[lv]})
        for it in IDI[lv]["fix"]:
            C.append({"k": "易错", "en": it[1], "bad": it[0], "zh": it[2], "note": it[3], "lv": lvname[lv]})
    for x in B:
        x["g"] = gloss_for(re.sub(r"[\[\]]", "", x.get("ex", "")), rank, rows, 2500)
    nq = len(A)
    rnd.shuffle(A); rnd.shuffle(B); rnd.shuffle(C)
    pool, pat = [], "ABACBA"      # a quote every other day, idioms / 口头禅 in between, a 易错 now and then
    qs = {"A": A, "B": B, "C": C}
    k = 0
    while any(qs.values()):
        src = qs[pat[k % len(pat)]] or qs["B"] or qs["A"] or qs["C"]
        pool.append(src.pop())
        k += 1
    with open(os.path.join(OUT, "daily.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 1, "items": pool}, f, ensure_ascii=False, separators=(",", ":"))
    print("words:", len(rows), "chunks:", (len(rows) + CHUNK - 1) // CHUNK, "| daily pool:", len(pool), "(%d quotes)" % nq)


if __name__ == "__main__":
    main()
