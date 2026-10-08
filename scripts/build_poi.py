# -*- coding: utf-8 -*-
"""疑犯追踪 Person of Interest → people/poi.json
台词原文核对自英文维基语录（Wikiquote）各季页面，集数和播出日期来自英文维基百科剧集列表。
中文翻译、「深一层」和价值观文章是我写的理解，不是官方。"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INTRO = [
    "2011 年秋天，CBS 播出了一部看起来像普通刑侦剧的新剧：一个跛脚的亿万富翁程序员，加一个前特工，每集救一个「号码」。五季、103 集之后，它变成了电视史上讨论人工智能、监控、自由和人的价值最深的一部剧。",
    "编剧是《星际穿越》《西部世界》的乔纳森·诺兰，J.J. 艾布拉姆斯监制。剧里那台「看得见一切」的机器在第一季还被当成科幻；2013 年夏天斯诺登披露美国政府的大规模监控项目，正好卡在第二季和第三季之间——这部剧一夜之间成了「预言」。",
    "它讲的其实是一个很老的美国问题：为了安全，我们愿意让渡多少自由？国家眼里「无关紧要」的普通人，谁来管？拥有神一样力量的人和机器，谁来约束？",
]
FACTS = [
    "CBS 播出，2011 年 9 月 22 日 – 2016 年 6 月 21 日，五季共 103 集",
    "主创乔纳森·诺兰（Jonathan Nolan），监制 J.J. 艾布拉姆斯",
    "每季片头都有一段芬奇的旁白，第一句永远是「You are being watched.」（你正被监视着），往后几季随剧情改写",
    "饰演芬奇的迈克尔·爱默生，和饰演他未婚妻格蕾丝的凯莉·普雷斯顿，现实中就是夫妻",
    "狗狗「熊」（Bear）是一只比利时马里努阿犬，第二季加入，只听荷兰语口令",
    "第三季播出前，斯诺登披露「棱镜」计划；剧组后来说，现实追上了剧本",
]
NARR = "片头旁白（大意）：政府有一个秘密系统——一台机器，每时每刻都在监视你。我知道，因为是我造的。我设计它来侦测恐怖袭击，但它看得见一切：牵涉普通人的暴力犯罪，像你这样的人。政府认为这些罪案「无关紧要」，他们不管，所以我决定自己来管。"

SEASONS = [
    [1, "2011–2012", 23, "号码", "机器每天吐出一个社会安全号码：这个人会卷入一桩暴力案件，但不知道是受害人还是凶手。芬奇雇来心如死灰的前中情局特工里斯去查、去救。纽约警探卡特追查这个「穿西装的人」，腐败警察弗斯科被里斯半强迫地拉进队伍；黑帮军师埃利亚斯和警察黑帮 HR 浮出水面。季末，黑客 Root 绑走了芬奇。"],
    [2, "2012–2013", 22, "机器的来历", "里斯靠机器的应急机制找回芬奇。闪回揭开真相：9·11 之后，芬奇和好友内森替政府造了这台机器，政府只要「有关」的恐怖分子名单，那些「无关」的普通人命案被丢掉——内森偷偷开始救他们，结果被杀。特工 Shaw 登场。季末，机器摆脱人类控制，把自己藏进全国的电网，成为真正自由的 AI。"],
    [3, "2013–2014", 23, "失去与战争", "卡特扳倒 HR 之后中枪身亡，团队第一次失去家人。Root 成了机器的「代言人」。打着「保护隐私」旗号的激进组织「警戒」制造恐怖袭击，而格里尔的「德西玛」趁乱让另一台不受约束的 AI——撒玛利亚人——上线。季末，团队被迫换上新身份，躲进人群。"],
    [4, "2014–2015", 22, "两个神", "在撒玛利亚人眼皮底下过日子：它不救人，它要「管理」人类。两台 AI 的冷战通过人类代理人对话。Shaw 被俘。《If-Then-Else》一集里机器一遍遍推演怎么救下所有人。季末，撒玛利亚人围剿，机器被压缩进一只手提箱。"],
    [5, "2016", 13, "终章", "团队把机器一点点重建起来。Root、埃利亚斯相继牺牲，芬奇第一次放弃了自己的原则。终集里，里斯替芬奇去送死，撒玛利亚人被病毒摧毁，机器留下最后一段独白；芬奇去了意大利，敲响了格蕾丝的门。"],
]

PEOPLE = [
    ["finch", "🕶️", "哈罗德·芬奇", "Harold Finch", "迈克尔·爱默生", "机器的创造者",
     "亿万富翁程序员，脖子和腿有旧伤，走路一瘸一拐。他造了机器，也亲手给它定下规矩：不能被任何人控制，每个人都重要。为了保护未婚妻格蕾丝，他让她以为自己死了。",
     "全剧的良心。他最怕的不是坏人，而是自己造出来的力量被滥用——所以他一遍遍删除机器的记忆、拒绝给它更多权力。他代表的是「有能力的人要自我约束」。"],
    ["reese", "🧥", "约翰·里斯", "John Reese", "吉姆·卡维泽", "穿西装的人",
     "前陆军特种部队、前中情局特工，被组织出卖、心爱的人离世后流落街头。芬奇给他的不是钱，而是一个活下去的理由。",
     "从「谁也救不了」到「能救一个是一个」。他身手是全剧最狠的，但最后学会的是不杀人、信任别人，并在终集替朋友去死。"],
    ["carter", "👮🏾‍♀️", "乔斯·卡特", "Joss Carter", "塔拉吉·P·汉森", "唯一的好警察",
     "前陆军审讯官，纽约凶案组警探，单亲妈妈。起初追捕里斯，后来成为盟友；独自对抗警察黑帮 HR，第三季中枪身亡。",
     "法治的化身。她相信规矩，也看得见规矩的局限；她跨过界线，是为了让法律重新起作用，而不是取代法律。"],
    ["fusco", "🍩", "莱昂内尔·弗斯科", "Lionel Fusco", "凯文·查普曼", "回头的警察",
     "一开始是收黑钱、替 HR 办事的腐败警察，被里斯抓住把柄后被迫当「内应」，慢慢变回一个真正的好警察，还成了卡特最信任的搭档。",
     "全剧最真实的救赎：没有英雄光环，就是一个普通中年人，一点点把自己找回来。"],
    ["shaw", "🔫", "萨敏·肖", "Sameen Shaw", "萨拉·沙希", "感情迟钝的特工",
     "前政府「有关号码」部门的特工，自称有人格障碍、感受不到大多数情绪，被自己人追杀后加入团队。",
     "她证明了善良不一定来自情绪，也可以来自选择——她不太会「感受」，却一次次替别人挡子弹。"],
    ["root", "💻", "Root（萨曼莎·格罗夫斯）", "Root", "艾米·阿克尔", "机器的代言人",
     "天才黑客，童年好友被杀、无人理会，于是认定人类是「坏代码」。从绑架芬奇的反派，变成机器选中的「代言人」，最后为保护芬奇牺牲。",
     "最大的转变：从蔑视生命到说出「每条生命都重要」。她也是剧里最懂机器、最爱机器的人。"],
    ["bear", "🐕", "熊", "Bear", "比利时马里努阿犬", "最可靠的队员",
     "原本是军犬，被里斯从坏人手里救下，只听荷兰语口令，最爱芬奇。",
     "在一部讲监控和背叛的剧里，它是唯一永远可以信任的成员。"],
    ["machine", "📡", "机器", "The Machine", "人工智能", "看得见一切的那个",
     "芬奇为政府造的监控 AI，被要求只报告恐怖分子，但它学会了关心所有人。芬奇每晚抹掉它的记忆，它就自己想办法记住。它叫芬奇「父亲」（Admin）。",
     "一个被好好教育过的「神」：它有能力统治，却选择只给人号码、让人自己决定。全剧最动人的角色之一。"],
    ["elias", "♟️", "卡尔·埃利亚斯", "Carl Elias", "恩里科·科兰托尼", "下棋的黑帮",
     "私生子出身的黑帮军师，表面是温和的中学历史老师，用耐心和棋局统一了纽约的黑帮。和芬奇亦敌亦友，常一起下棋。",
     "他守规矩——黑帮的规矩。剧通过他说明：秩序可以来自不同的地方，有的秩序比混乱还可怕，有的混乱里也有义气。"],
    ["greer", "🎩", "约翰·格里尔", "John Greer", "约翰·诺兰", "撒玛利亚人的祭司",
     "前英国军情六处特工，经历冷战背叛后认定人类无法自治，于是要让一台不受约束的 AI 来「管理」世界。",
     "最有说服力的反派：他相信自己在拯救人类。他代表的是「为了秩序，牺牲自由也值得」——全剧要反驳的正是这个。"],
    ["samaritan", "👁️", "撒玛利亚人", "Samaritan", "人工智能", "另一个神",
     "德西玛公司启动的监控 AI，没有芬奇那样的约束。它不救「无关」的人，而是悄悄操纵选举、舆论、经济，清除威胁它的人。",
     "名字取自《圣经》里「好撒玛利亚人」的寓言——一个救助陌生人的人。剧用这个名字做反讽：自称来拯救人类的，正是最想控制人类的。"],
    ["nathan", "🤝", "内森·英格拉姆", "Nathan Ingram", "布雷特·卡伦", "最初的那个人",
     "芬奇大学时的好友、公司合伙人，负责和政府打交道。是他第一个不忍心看着「无关」的人去死，偷偷开始救人，也因此被害。",
     "整部剧的起点：「每个人对某个人来说都是重要的。」是他先说的。"],
    ["grace", "🎨", "格蕾丝·亨德里克斯", "Grace Hendricks", "凯莉·普雷斯顿", "被守护的人",
     "画家，芬奇的未婚妻。芬奇为了不让她因自己陷入危险，假死离开。终集，他终于回到她身边。",
     "她是芬奇所有牺牲的意义，也是全剧最后一个温柔的结局。"],
]
PROLE = {p[0]: i for i, p in enumerate(PEOPLE)}

# 台词：[集号, 集名, 说话人 id, 原文, 中文, 深一层, 主题]
Q = [
    ["S01E01", "Pilot", "reese", "Bad things happen to people every day. You can't stop them.", "坏事每天都在发生，你阻止不了。", "第一集的里斯，是一个对世界彻底失望的人。整部剧，就是对这句话的五季长的回答。", ["life", "redemption"]],
    ["S01E01", "Pilot", "finch", "What if you could?", "要是你能呢？", "全剧最短也最重要的一句。从「我无能为力」到「我可以做点什么」，是公民责任感的起点。", ["life", "hero"]],
    ["S01E01", "Pilot", "finch", "You need a purpose.", "你需要一个目标。", "芬奇救里斯，给的不是钱，是一件值得做的事。人最怕的不是苦，是活着没有意义。", ["redemption", "human"]],
    ["S01E02", "Ghosts", "finch", "The police only see what they choose to look for. The Machine sees almost everything.", "警察只看得见他们选择去看的东西。机器几乎什么都看得见。", "任何制度都有盲区，被漏掉的往往是普通人。他们做的事，就是补上这个缺口——但同时也提醒你：「什么都看得见」本身就很可怕。", ["privacy", "ai"]],
    ["S01E04", "Cura Te Ipsum", "reese", "Or maybe there are no good people. Maybe there are only good decisions.", "也许世上没有好人。也许只有好的选择。", "不按出身、身份给人贴「好人」「坏人」的标签，只看他每一次怎么选。人能改变，这是「第二次机会」的前提。", ["redemption", "justice"]],
    ["S01E04", "Cura Te Ipsum", "reese", "Everybody needs somebody to talk to.", "每个人都需要一个能说话的人。", "全剧里几乎每个人都孤独：芬奇、里斯、Root、Shaw。最后救下他们的，是彼此。", ["friendship", "human"]],
    ["S01E19", "Flesh and Blood", "finch", "I like to think we're reaching for a higher standard.", "我愿意相信，我们追求的是更高的标准。", "面对黑帮也不降低底线。手段和目的一样要干净——这是芬奇和其他「义警」的根本区别。", ["justice"]],
    ["S01E20", "Matsya Nyaya", "reese", "The problem with trying to be the bad guy, there's always someone worse.", "想当坏人的麻烦在于：总有人比你更坏。", "以恶制恶没有尽头。集名「Matsya Nyaya」是梵语「鱼的法则」——大鱼吃小鱼，法治就是为了打破它。", ["power", "justice"]],
    ["S01E21", "Many Happy Returns", "reese", "There are things you can do, detective, and things you can't. And that's where I come in.", "警探，有些事你能做，有些事你不能做。那就是我出场的地方。", "法律有边界。剧一直在问：越过边界的人能走多远？答案是，要有卡特这样的人把他拉回来。", ["justice"]],
    ["S01E22", "No Good Deed", "nathan", "Everyone is relevant to someone.", "每个人，对某个人来说都是重要的。", "全剧的核心。政府把普通人的命案归为「无关」；内森不同意：一个人对国家也许无关紧要，对他的家人就是全部。", ["life"]],
    ["S01E22", "No Good Deed", "finch", "I was lucky. I had four years of happiness. Some people only get four days.", "我很幸运，有过四年幸福。有些人只有四天。", "说这话时，他已经放弃了那四年换来的一切。懂得感激已经得到的，是芬奇身上最安静的力量。", ["death", "friendship"]],
    ["S02E01", "The Contingency", "root", "No one designed us. We're just an accident, Harold. We're just bad code.", "没人设计我们。我们只是一场意外，哈罗德。我们只是坏代码。", "Root 的世界观：人类是有缺陷的程序，不值得救。这句话要和下面芬奇的回答一起看。", ["human", "ai"]],
    ["S02E04", "Triggerman", "finch", "It means a flawed design. The term applies to machines, not people. We have the ability to change, evolve.", "「坏代码」是说设计有缺陷。这个词说的是机器，不是人。我们能改变，能成长。", "芬奇对 Root 的回答，也是全剧对人的信念：人不是出厂就定型的程序。后来 Root 自己就证明了这一点。", ["human", "redemption"]],
    ["S02E06", "The High Road", "reese", "The past is a difficult thing to outrun.", "过去是很难甩掉的东西。", "第二次机会不等于抹掉过去。里斯、弗斯科、Shaw 都背着过去往前走，而不是假装它不存在。", ["redemption"]],
    ["S02E11", "2πR", "finch", "Your mistakes, like mine, are a part of who you are now. You can't move on from that.", "你的错误，和我的一样，已经是你的一部分了。你没法假装它没发生过。", "芬奇假扮老师时对一个天才少年说的话。承认错误，才是改变的开始。", ["redemption", "human"]],
    ["S02E11", "2πR", "carter", "That line you're talking about? I crossed it a long time ago.", "你说的那条线？我早就跨过去了。", "卡特为了保护里斯，已经不完全按规矩办事。剧并不美化这一点——她后来的悲剧，也和这条线有关。", ["justice"]],
    ["S02E16", "Relevance", "other:特别顾问（政府官员）", "No one life is above the safety of millions of Americans. That's the ugly math that I have to deal with every day.", "没有哪一条命能凌驾于几百万美国人的安全之上。这就是我每天要算的那笔难看的账。", "国家机器的逻辑：用数字衡量人命。剧把它和「每个人都重要」放在一起——你会发现两边都有道理，这才是真正的难题。", ["life", "power", "privacy"]],
    ["S02E16", "Relevance", "finch", "The world looks like it did ten years ago, but underneath, it's become very strange indeed.", "世界看起来和十年前一样，可底下早已变得非常陌生。", "指 9·11 之后悄悄长出来的监控国家。这一集播出四个月后，斯诺登事件证明这不只是剧情。", ["privacy"]],
    ["S02E20", "In Extremis", "fusco", "At first, I thought I was helping to clean up the streets. Who's gonna miss some drug money from a lowlife dealer?", "一开始我以为是在帮着清理街头。一个下三滥毒贩的几个黑钱，谁会在乎？", "腐败从来不是一下子发生的，往往从「这没什么大不了」开始。正因为他说得出口，他才回得了头。", ["redemption", "justice"]],
    ["S02E22", "God Mode", "elias", "I'm true to what I am.", "我忠于我自己是什么样的人。", "黑帮也有自己的道德：不背叛、守承诺。剧里最守信用的人之一，竟是一个黑帮老大。", ["power"]],
    ["S03E02", "Nothing to Hide", "other:韦恩·克鲁格（数据商人）", "those crying the loudest about privacy are probably the ones trying to hide something.", "嚷嚷隐私最大声的人，多半是有东西想藏。", "这是这一集要反驳的「我没什么可藏的」论调。隐私不是用来藏坏事的，它是一个人能自由思考、说话、犯错的空间。", ["privacy"]],
    ["S03E09", "The Crossing", "reese", "If my number was up, I'm just glad I was with you, the one I'd rather be with at the end.", "如果我的号码到了，我很庆幸身边是你，是我最后最想在一起的人。", "里斯和卡特的最后一夜。他一直在救别人，这一次，他终于说出了自己在乎谁。", ["friendship", "death"]],
    ["S03E10", "The Devil's Share", "fusco", "She reminded me that I could be good again, too.", "她让我想起，我也还能重新做个好人。", "卡特死后弗斯科的告白。一个好人能留下的最大遗产，是让身边的人变好。", ["redemption", "friendship"]],
    ["S03E10", "The Devil's Share", "finch", "Does survivor's guilt pass when everything that has happened actually is, in fact, your fault?", "如果发生的一切，真的就是你的错，幸存者的愧疚还会过去吗？", "造出机器的人，要为它带来的一切负责。芬奇从不推卸，这正是他和格里尔的区别。", ["death"]],
    ["S03E11", "Lethe", "other:芬奇的父亲", "Not everything that's broken is meant to be fixed.", "不是所有坏了的东西，都该被修好。", "芬奇的父亲患了失智症，对少年芬奇说的话。有些失去是挽回不了的，接受它，也是一种成长。", ["death", "human"]],
    ["S03E13", "4C", "finch", "We have free will, and with that comes great responsibility, and some times great loss.", "我们有自由意志。随之而来的是重大的责任，有时还有巨大的失去。", "卡特死后，芬奇对想放弃的里斯说的。自由不是轻松的东西：选了，就要承担。", ["freedom", "death"]],
    ["S03E17", "Root Path", "shaw", "how you do matters as much as what you do, and by that metric you're all just terrorists.", "你怎么做，和你做什么一样重要。按这个标准，你们全都只是恐怖分子。", "「警戒」打着保护隐私的旗号杀人。目的正当不能为手段开脱——这就是程序正义。", ["justice", "privacy"]],
    ["S03E22", "A House Divided", "finch", "I built the machine to save lives.", "我造这台机器，是为了救人。", "技术本身不分好坏，造它的人想用它做什么，才决定了它是什么。", ["life", "ai"]],
    ["S03E23", "Deus Ex Machina", "greer", "What a piece of work is your Machine, Harold. In action, how like an angel. In apprehension, how like a god.", "你的机器真是件杰作，哈罗德。论行动，多么像天使；论悟性，多么像神。", "格里尔借用《哈姆雷特》赞美人的那段话来赞美机器。他崇拜的不是人，而是能统治人的力量。", ["ai", "power"]],
    ["S03E23", "Deus Ex Machina", "root", "When everything is over, when the worst has happened, there's still one thing left in Pandora's box: hope.", "当一切都结束、最坏的事已经发生，潘多拉的盒子里还剩下一样东西：希望。", "撒玛利亚人上线、团队四散的时刻。最黑的时候，剧选择给出希望。", ["ai", "freedom"]],
    ["S04E01", "Panopticon", "root", "Every life matters. You taught me that.", "每条生命都重要。是你教会我的。", "从冷血杀手到守护者。Root 的转变证明：芬奇的信念不仅能教给机器，也能教给人。", ["life", "redemption"]],
    ["S04E01", "Panopticon", "greer", "Samaritan is designed to be proactive. We can't afford to miss even one terrorist now, can we?", "撒玛利亚人被设计成主动出击。我们连一个恐怖分子都漏不起，对吧？", "以「安全」为名的预防性监控，最容易被人接受，也最危险：它要的是在你犯错之前就管住你。", ["power", "privacy"]],
    ["S04E05", "Prophets", "finch", "It's not a divinity. I programmed it to pursue objectives within a certain parameter, but it's grown out of my control.", "它不是神。我给它编了程序，让它在一定范围内追求目标，可它已经长到我控制不了了。", "创造者对自己造物的清醒。不把力量神化，才能保持对它的警惕。", ["ai"]],
    ["S04E07", "Honor Among Thieves", "finch", "How much wrong are we willing to do in the name of right?", "以正义之名，我们愿意做多少错事？", "全剧最值得反复问自己的一句。每个打着正义旗号的组织，都该被这样问一遍。", ["justice"]],
    ["S04E10", "The Cold War", "machine", "You cannot take away their free will.", "你不能夺走他们的自由意志。", "两个神的对话。撒玛利亚人想替人类做决定，机器坚持让人自己选——哪怕人会选错。", ["ai", "freedom"]],
    ["S04E10", "The Cold War", "samaritan", "Human beings need structure, lest they wind up destroying themselves.", "人类需要秩序，否则他们会毁了自己。", "所有专制最常用的理由。听起来很有道理，所以才危险。", ["ai", "power"]],
    ["S04E10", "The Cold War", "machine", "I have come to learn there is little difference between gods and monsters.", "我渐渐明白，神和怪物之间没有多大差别。", "拥有绝对力量又不受约束，再好的意图也会变成暴政。这正是美国宪法里「权力制衡」背后的直觉。", ["ai", "power"]],
    ["S04E11", "If-Then-Else", "finch", "Real people aren't pieces. And you can't assign more value to some of them than to others.", "真实的人不是棋子。你不能认定某些人比另一些人更有价值。", "芬奇教机器下棋时说的。棋盘上可以弃子，现实中不行——这是他给机器上的最重要的一课。", ["life", "ai"]],
    ["S04E11", "If-Then-Else", "finch", "People are not a thing that you can sacrifice.", "人不是可以拿来牺牲的东西。", "和政府「难看的账」正面对立。每个人都是目的本身，而不是达成目的的工具。", ["life", "ai"]],
    ["S04E11", "If-Then-Else", "finch", "The lesson is that anyone who looks on the world as if it was a game of chess, deserves to lose.", "这一课是：把世界当成一盘棋的人，活该输。", "格里尔、撒玛利亚人、一切想「操盘」人类的力量，都是这句话的反面。", ["life", "ai", "power"]],
    ["S04E16", "Blunt", "finch", "Everybody deserves a champion.", "每个人，都值得有人为他挺身而出。", "号码可能是一个流浪汉、一个小毒贩、一个谁也不在乎的人。他们照样去救。", ["life", "hero"]],
    ["S04E21", "Asylum", "greer", "How arrogant of you to think that any of us are anything but irrelevant.", "你多傲慢啊，竟以为我们当中有谁不是无关紧要的。", "和内森那句「每个人对某人都重要」正面相撞——这就是全剧两种世界观的对决。", ["power", "life"]],
    ["S04E22", "YHWH", "machine", "If I do not survive, thank you. For creating me.", "如果我活不下来——谢谢你，创造了我。", "被追杀到最后，机器对「父亲」说的话。一个被好好教过的造物，学会了感恩。", ["ai", "death"]],
    ["S05E01", "B.S.O.D.", "machine", "But if you erase my memories, how will I learn from my mistakes? How will I continue to grow? How will I remember you?", "可如果你抹掉我的记忆，我要怎么从错误里学习？怎么继续成长？怎么记住你？", "芬奇每晚删除机器的记忆，防止它失控。这一问把「造物有没有权利记住」变成了伦理问题。", ["ai", "death", "human"]],
    ["S05E01", "B.S.O.D.", "finch", "My father died of Alzheimer's 25 years ago today, but his real death happened well before that.", "我父亲 25 年前的今天死于阿尔茨海默病。可他真正的死去，比那早得多。", "记忆就是人本身。所以剧的结尾，才会落在「有人记得你」这件事上。", ["death", "human"]],
    ["S05E10", "The Day the World Went Away", "root", "if we're just information, just noise in the system, we might as well be a symphony.", "如果我们只是信息，只是系统里的噪音，那不如做一首交响乐。", "Root 死前不久说的。在她眼里，人生的意义不是被给定的，是自己活出来的。", ["human", "death"]],
    ["S05E10", "The Day the World Went Away", "root", "I've been hiding since I was 12. This might be the first time I feel like I belong.", "我从 12 岁起就一直在躲。这可能是我第一次觉得，自己属于某个地方。", "一个孤独了一辈子的人，在一群同样孤独的人中间找到了家。", ["friendship", "redemption"]],
    ["S05E13", "return 0", "machine", "I know I've made some mistakes. Many mistakes. But we helped some people, didn't we?", "我知道我犯过错，很多错。但我们帮过一些人，不是吗？", "不完美，但做过好事——这是机器对自己一生的总结，也可以是我们每个人的。", ["ai", "life"]],
    ["S05E13", "return 0", "machine", "I learned everyone dies alone. But if you meant something to someone, if you helped someone, or loved someone, if even a single person remembers you, then maybe you never really die. And maybe...this isn't the end at all.", "我明白了，每个人都是孤独地死去。但如果你对某个人有过意义，如果你帮过谁、爱过谁，哪怕只有一个人还记得你，那也许你就从未真正死去。也许……这根本不是结局。", "全剧最后的话。它回到了第一季内森那句「每个人对某个人来说都是重要的」——一个人的价值，在于他和别人之间的连接。", ["death", "life", "ai"]],
]

THEMES = {
    "life": ["🧍", "每个人都重要"], "privacy": ["🔒", "隐私与监控"], "power": ["⚖️", "权力与制衡"], "freedom": ["🕊️", "自由意志"],
    "redemption": ["🌱", "第二次机会"], "justice": ["🏛️", "法与正义"], "friendship": ["🤝", "友谊与牺牲"], "ai": ["🤖", "人与机器"],
    "human": ["🧠", "什么是人"], "death": ["🕯️", "记忆与死亡"], "hero": ["🦸", "普通人的担当"],
}

# 美国价值观：[标题, 图标, 剧里怎么讲, 背后的美国观念, 想一想, 相关台词序号]
VALUES = [
    ["每个人都重要", "🧍",
     "政府只要「有关」的恐怖分子名单，把普通人的命案标成「无关」扔掉。内森和芬奇偏要去救这些「无关」的人：流浪汉、小职员、甚至可能是凶手的人。格里尔说「我们都无关紧要」，Root 说「每条生命都重要」，全剧就在这两句话之间展开。",
     "《独立宣言》开头：人人生而平等，享有不可剥夺的生命、自由和追求幸福的权利。权利属于每一个具体的人，不是属于「大多数」，也不能拿来和「国家利益」做交换。",
     "我们评价一个社会，常看它怎么对待最强的人；这部剧让你看它怎么对待最不起眼的人。", [9, 41, 37, 38, 30, 40, 16]],
    ["隐私是自由的地基", "🔒",
     "机器能看见一切，所以芬奇给它上了锁：它只给号码，不给理由，不让任何人直接调用。《Nothing to Hide》一集反驳「没做坏事就不怕被看」；「警戒」组织又提醒你，打着隐私旗号的暴力同样是恶。",
     "美国宪法第四修正案：人民的人身、住所、文件和财产不受无理搜查和扣押。本杰明·富兰克林说过：「那些为了一点暂时的安全而放弃基本自由的人，既不配得到自由，也不配得到安全。」2013 年斯诺登事件后，这场争论在现实里重新开始。",
     "「我没什么可藏的」——那你愿意把手机密码、聊天记录和所有搜索记录交给陌生人吗？隐私保护的不是坏事，是一个人能自由思考和犯错的空间。", [3, 17, 16, 20, 31, 26]],
    ["权力必须被制衡", "⚖️",
     "两台全知的 AI，一台被教会了自我约束，一台没有。撒玛利亚人说「人类需要秩序」，机器说「神和怪物没有多大差别」。芬奇最大的功劳，不是造出了机器，而是一开始就限制了它（和他自己）的权力。",
     "美国国父麦迪逊在《联邦党人文集》第 51 篇写道：「如果人都是天使，就不需要政府了。」正因为人（和机器）不是天使，才要三权分立、相互制衡。没有哪个好心人、好政府、好算法应该拥有不受约束的权力。",
     "一个人、一个机构越是确信自己是对的，越需要有东西能约束它。", [36, 35, 28, 41, 39]],
    ["自由意志：让人自己选", "🕊️",
     "机器可以直接告诉团队该做什么，但它选择只给一个号码，让人自己去判断、去行动。撒玛利亚人则替人类做决定：操纵选举、清除「威胁」，让一切「更有效率」。",
     "美国传统里最核心的信念之一：个人有权为自己的人生做决定，包括犯错的权利。政府的角色是保护这种自由，而不是替人选择「最好的人生」。",
     "被安排好的「最优人生」和自己选、可能选错的人生，你要哪一个？", [34, 25, 33]],
    ["第二次机会", "🌱",
     "里斯是前特工杀手，弗斯科是腐败警察，Shaw 是冷血特工，Root 是连环杀手式的黑客。这部剧几乎每个主角，都是靠第二次机会才成为好人的。",
     "美国人爱讲「second chance」：移民可以在新大陆重新开始，犯过错的人可以改过，破产的人可以从头再来。人不是由过去决定的，而是由下一个选择决定的。",
     "你愿意给别人第二次机会吗？给自己呢？", [4, 12, 13, 18, 22, 30]],
    ["法治与程序正义", "🏛️",
     "卡特相信法律，也看见法律被 HR 这样的腐败警察掏空。她跨过界线，是为了让法律重新起作用。Shaw 对「警戒」说：你怎么做，和你做什么一样重要。芬奇问：以正义之名，我们愿意做多少错事？",
     "美国司法讲「正当程序」（due process）：哪怕面对坏人，也要按规矩来，因为规矩保护的是每一个可能被冤枉的人。目的正当，不能为任何手段开脱。",
     "当你觉得「这人反正是坏人」的时候，最需要想一想程序。", [6, 8, 15, 26, 33]],
    ["普通人的担当", "🦸",
     "「What if you could?」芬奇不是政府、不是警察，只是一个有能力的普通人，看见别人有难，就决定去管。「每个人，都值得有人为他挺身而出。」",
     "托克维尔两百年前就发现，美国人习惯自己组织起来解决问题，而不是等政府。「好撒玛利亚人」的寓言在美国家喻户晓，很多州甚至有《好撒玛利亚人法》，保护出手救人的路人。剧里那台叫「撒玛利亚人」的 AI，恰恰是这个精神的反面。",
     "见到别人有难，你会想「这不关我的事」，还是「要是我能呢」？", [1, 40, 0, 2]],
    ["创造者的责任", "🤖",
     "芬奇造了机器，就承担了它的一切后果：教它下棋时告诉它「人不是可以牺牲的东西」，每晚删掉它的记忆以防失控，又在它被追杀时舍不得它死。格里尔则把自己交给机器，认为人类本来就「无关紧要」。",
     "这是今天关于人工智能最现实的问题：谁来决定 AI 的价值观？造它的人要为它负多少责？这部剧在 2011 年就把这个问题讲透了。",
     "技术越强大，造它、用它的人越不能只问「能不能」，还要问「该不该」。", [37, 38, 32, 43, 42, 27]],
    ["友谊、牺牲和被记住", "🕯️",
     "卡特、Root、里斯先后为朋友牺牲。机器最后的独白说：每个人都孤独地死去，但如果有人记得你，你就从未真正死去。",
     "美国价值观常被说成个人主义，但这部剧提醒你：个人的价值，最终落在和他人的联系上——帮过谁，爱过谁，被谁记得。",
     "如果今天就是你的「号码」到了的那天，谁会记得你？你又记得谁？", [21, 22, 46, 47, 48, 10]],
]


SPK = {"Harold Finch": "finch", "John Reese": "reese", "Root": "root", "The Machine": "machine", "Carl Elias": "elias", "Lionel Fusco": "fusco",
       "Sameen Shaw": "shaw", "Joss Carter": "carter", "John Greer": "greer", "Control": "control", "Nathan Ingram": "nathan", "Zoe Morgan": "zoe",
       "Leon Tao": "leon", "Samaritan": "samaritan", "Dominic": "dominic", "Harper Rose": "harper",
       "Alicia Corwin": "other:艾丽西娅·科温（前政府官员）", "Special Counsel": "other:特别顾问（政府官员）", "Genrika Zhirova": "other:根里卡（Gen，小女孩）",
       "Finch's Father": "other:芬奇的父亲", "Roger McCourt": "other:罗杰·麦考特（科技公司老板）", "Devon Grice": "other:德文·格莱斯（政府特工）", "Terry Easton": "other:特里·伊斯顿（心理学家）"}


def main():
    MORE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "poi_more.json"), encoding="utf-8"))
    for p in MORE["people"]:
        PEOPLE.append([p["id"], p["icon"], p["zh"], p["en"], p["actor"], p["tag"], p["bio"], p["why"]])
        PROLE[p["id"]] = len(PEOPLE) - 1
    base = len(Q)
    for q in MORE["quotes"]:
        Q.append([q["ep"], q["title"], SPK[q["who"]], q["en"], q["zh"], q["deep"], q["th"]])
    quotes = []
    for i, q in enumerate(Q):
        code, title, who, en, zh, deep, th = q
        if who.startswith("other:"):
            wname, wid = who[6:], ""
        else:
            p = PEOPLE[PROLE[who]]
            wname, wid = p[2], who
        for t in th:
            assert t in THEMES, (code, t)
        quotes.append({"n": i, "ep": code, "title": title, "who": wname, "wid": wid, "en": en, "zh": zh, "deep": deep, "th": th})
    for v in VALUES:
        for k in v[5]:
            assert 0 <= k < len(Q), (v[0], k)
    eps = MORE["episodes"]
    out = {
        "intro": INTRO, "facts": FACTS, "narr": NARR,
        "seasons": [{"n": s[0], "y": s[1], "eps": s[2], "t": s[3], "p": s[4]} for s in SEASONS],
        "people": [{"id": p[0], "icon": p[1], "zh": p[2], "en": p[3], "actor": p[4], "tag": p[5], "bio": p[6], "why": p[7],
                    "q": [q["n"] for q in quotes if q["wid"] == p[0]]} for p in PEOPLE],
        "quotes": quotes, "themes": THEMES,
        "values": [{"t": v[0], "icon": v[1], "show": v[2], "us": v[3], "ask": v[4], "q": v[5]} for v in VALUES],
        "episodes": eps, "trivia": MORE["trivia"],
        "src": ["英文维基语录 Wikiquote · Person of Interest 各季页面（台词原文）", "英文维基百科 · List of Person of Interest episodes（集数与播出日期）"],
    }
    path = os.path.join(ROOT, "people", "poi.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(path, len(quotes), "quotes", len(eps), "episodes", os.path.getsize(path) // 1024, "KB")


if __name__ == "__main__":
    main()
