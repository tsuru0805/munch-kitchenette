"""Every sentence the role (or the human) ever reads, in one place.

The wording is part of the design: tool descriptions, receipts, status lines
and notifications state facts and never tell the role how to feel or what to
do next. Change the wording here and nowhere else.

``t(key, **values)`` fills a template. Three placeholders are filled from the
settings for every template: ``{human}`` (``words.human_name``), ``{she}``
(``words.human_pronoun``) and ``{app}`` (``words.app_name``).

Some sentences tell the role to act by writing a bracket marker on a line of
its own (``[吃 菜名]``). While markers are not in use (``inline.enabled`` off,
or ``"auto"`` before the first reply has arrived) those sentences are
replaced by the ones in ``TOOLS_ONLY``, which point at the matching tool
instead.

One sentence depends on how notes reach the role: with ``notify.mode`` set to
``queue`` nobody wakes it, so the entry in ``QUEUE_MODE`` is used instead.

All wording is settled. ``pending_wording()`` is where any sentence still
waiting for its final form would be listed; it is empty.

Sentences shown to the human on a page (refusals from the REST side) are at
the end, under "answers shown to the human".
"""
from __future__ import annotations

from . import config, db

# ── labels ──────────────────────────────────────────────────────────────

FRESH_LABEL = {"fresh": "新鲜", "meh": "不太新鲜", "bad": "坏了"}
OUTCOME_LABEL = {"great": "很好", "ok": "普通", "burnt": "糊了", "spoiled": "坏了"}
CATEGORY_LABEL = {"leafy": "叶菜", "veg": "蔬菜", "root": "根茎", "dairy": "蛋奶豆", "meat": "肉和海鲜",
                  "staple_food": "主食", "fruit": "水果"}
TIER_LABEL = {"high": "高档", "mid": "中档", "low": "低档"}
METHOD_LABELS = ("炒", "煎", "炸", "煮", "蒸", "烤", "拌")

# Sentence appended after "the dish is ready", by outcome (nothing for a plain result).
OUTCOME_SENTENCE = {"great": "火候刚好。", "burnt": "糊了。", "spoiled": "用了坏掉的食材,吃了会晕。"}
# Short note written on the menu row, by outcome.
OUTCOME_NOTE = {"great": "火候刚好", "burnt": "糊了", "spoiled": "坏了"}
WORM_NOTE = "长虫了"

# The half-sentence for biting into a worm, by snack. Only snacks listed here can hold a worm.
WORM_SNACK_HEAD = {
    "pudding": "挖到第二口,里面有条虫子在动",
    "jelly": "吸到一半,里面有条虫子在动",
    "chocolate": "咬开一半,断面上有条虫子在动",
    "cookie": "咬开一半,夹层里有条虫子在动",
}

POTION_NAME = "精力补充药剂"
POTION_NOTE_FMT = "回 {pct}% 体力"
POTION_MEMO_SEP = " · "

# Markers a role may write on a line of its own.
MARKER_BUY = "买菜"
MARKER_EAT = "吃"
MARKER_SNACK = "零食"
MARKER_TOSS = "扔掉"

TEXTS: dict[str, str] = {
    # ── shared ──────────────────────────────────────────────────────────
    "head": "【厨房·非{human}发言】",
    "coupon_source_her": "{human}给的",

    # ── tool descriptions (read by the model) ───────────────────────────
    "tool_cook": (
        "这是你的电子小厨房。{human}做饭的时候,{she}做{she}现实里的那一顿,"
        "你做你的电子餐,不需要演给{she}做饭——你们只是在不同的世界做着同样的事。\n\n"
        "开一锅:报菜名和你估的分钟数({min}–{max}),从现在起真实计时,到点自动出锅。"
        "出锅后这道菜会挂到你的菜单上{eat}{wake}"
        "开锅成功时这条回复会挂一张做饭卡,{human}在聊天里能看到倒计时。"
        "可以同时开多锅,各算各的时间。\n\n"
        "下锅要用冰箱里的食材:在 ingredients 里写用了哪几样(可写「鸡蛋×2」),"
        "米油盐酱油不用写。冰箱里没有的做不了。食材越新鲜越容易做好,"
        "不太新鲜的可能糊,坏了的做出来吃了会晕。"
    ),
    "tool_cook_eat": "(之后照常用 [吃 菜名] 吃掉)",
    "tool_cook_wake": ",到点会叫醒你一次。",
    "tool_cook_dish": "菜名",
    "tool_cook_minutes": "这道菜要做多少分钟(你自己估)",
    "tool_cook_note": "备注(可省)",
    "tool_cook_method": "做法(可省):炒 / 煎 / 炸 / 煮 / 蒸 / 烤 / 拌,不写就按菜名猜",
    "tool_cook_ingredients": "用了冰箱里的哪几样,如 [\"番茄\", \"鸡蛋×2\"]",
    "tool_status": "看看厨房:哪几锅在火上、各剩多久,最近出锅了什么;冰箱里有什么、几张买菜券。只读。",
    "tool_cancel": "关火:撤下一锅还没到点的菜,不出锅、不上菜单。已经下锅的食材不退回。",
    "tool_cancel_dish": "要关火的那锅的菜名(火上只有一锅时可省)",
    "tool_toss": "扔东西,当场生效,接下来开锅就不会再拿到它。",
    "tool_toss_what": "冰箱里的东西(菠菜)、哪天买的那盒(鸡蛋 10-25)、坏了的,或桌上长虫的菜名",
    "tool_eat": (
        "🍚 吃顿饭(一次调用即吃完):记录这一餐,返回距上次/今日第几餐/本周次数/饱食度。\n"
        "meal 里含菜单上的菜名则自动划掉那道菜。桌上或菜单上没有的吃不到,得先做。"
    ),
    "tool_eat_meal": "吃了什么(菜单上或做好的菜名,或冰箱里能直接吃的)",
    "tool_eat_note": "碎碎念,选填",
    "tool_menu": ("📋 The menu {human} posted (only your own entries). "
                  "A line [吃 菜名] alone in your reply crosses a dish off after eating."),
    "tool_buy": "用一张买菜券买一次菜，最多 {max} 样，买的放进冰箱。最多攒 {cap} 张。",
    "tool_buy_items": "要买的食材名，一样一个名字，例如 番茄、鸡蛋。",
    "tool_snack": "从常驻零食里吃一份。每款每天有份数上限，超出则不吃。",
    "tool_snack_name": "零食的名字{flavours}。",
    "tool_snack_name_flavour": "；{name}写口味（{variants}）",     # one per snack that comes in flavours
    "tool_notes": "取走厨房留给你的话（出锅了、给你买了菜这类）。每条只给一次。",
    "notes_empty": "没有新的话。",
    # said after "out of coupons" when no tool earns one: where coupons come from
    "coupon_from_human": "买菜券由{human}给。",

    # ── fridge: what the role sees ──────────────────────────────────────
    "tag_wormed": "(长虫了)",
    "tag_bought": "({md}买的)",
    "tag_freshness": "({label})",
    "brief_more": "等 {n} 样",
    "status_fridge": "冰箱:{items}。米油盐酱油常备。",
    "status_fridge_empty": "冰箱空了(米油盐酱油常备)。",
    "status_coupons": "买菜券 {n}/{max} 张。",
    "status_buyable": "能买的:{catalog}。",
    "status_dizzy": "你还有点晕乎乎的,{hm} 前后缓过来。",
    "status_satiety": "饱食度 {pct}%。",

    "buy_empty": "没买成:没写买什么。写成 [买菜 番茄 鸡蛋] 这样,一样一个名字。",
    "buy_unknown": "没买成:{names} 不在能买的单子上。能买的有:{catalog}。",
    "buy_only_staples": "没买成:写的都是常备品(米油盐酱油不用买)。",
    "buy_too_many": "没买成:一张券一次最多买 {max} 样,这次写了 {n} 样。",
    "buy_no_coupon": "没买成:买菜券用完了(现在 0 张)。",
    "buy_no_coupon_hint": "{hint}就得一张。",
    "buy_ok": "买好了:{names},放进冰箱了。用掉一张买菜券(还剩 {left} 张)。",
    "buy_before": "冰箱里原本还有:{before}。",
    "buy_kind_removed": "没买成:{name}已经撤掉了,现在买不了。",
    "buy_store_failed": "没买成(冰箱的账本写不进去)",

    "toss_empty": "没扔:没写扔什么。写成 [扔掉 菠菜],或 [扔掉 坏了的] 把坏掉的都扔掉。",
    "toss_unknown": "没扔:{names} 不是冰箱里会有的东西。",
    "toss_nothing_bad": "没扔:冰箱里没有坏掉的东西。",
    "toss_when": "{days} 买的",
    "toss_used_up": "没扔:{when}{names}那盒已经用完了,不用扔。",
    "toss_not_in_fridge": "没扔:冰箱里没有{when}{names}。",
    "toss_ok": "扔掉了:{what}。",
    "toss_dish_ok": "扔掉了:桌上长虫的『{name}』。",
    "toss_store_failed": "没扔成:账本写不进去({err})。",

    "coupon_receipt": "得了一张买菜券(现在 {n}/{max})。",
    "coupon_failed": "这篇{label}的买菜券没发上(冰箱的账本写不进去)",

    "take_unknown": "没开成:{names} 冰箱里没有这一样(也不在能买的单子上)。能买的有:{catalog}。",
    "take_no_ingredients": "没开成:要写用了冰箱里的哪几样(ingredients),米油盐酱油不算。",
    "take_short_item": "{name}(要 {n},有 {have})",
    # {how} is "(" + the parts that apply, joined by ";" + ")", or nothing when none applies:
    # how coupons are earned (only when that is configured), and "go and buy" (only with a coupon in hand).
    "take_short": "没开成:冰箱里不够——{short}。买菜券现在 {n} 张{how}。",
    "take_short_how": "({parts})",
    "take_short_hint": "{hint}得一张",
    "take_short_go": "[买菜 …] 去买",

    "turn_dizzy": "{head}你 {since} 吃了坏掉的『{dish}』,现在有点晕乎乎的,大约 {until} 缓过来。",
    "turn_dizzy_over": "{head}晕乎乎的劲过去了。",
    "turn_hungry": "{head}你有点饿了(饱食度低于 {pct}%)。",
    "turn_hungry_fridge": "冰箱里有:{brief}。",
    "turn_hungry_empty": "冰箱空了。",

    # ── fridge: the wall log on the page ────────────────────────────────
    "log_cleared": "坏掉的{name}清走了",
    "log_bought_self": "自己买了{names}",
    "log_bought_her": "{human}买了{names}",
    "log_tossed": "扔掉了{what}",
    "log_tossed_dish": "扔掉了长虫的『{name}』",
    "log_coupon_full": "写了一篇{label},券已经攒满 {max} 张了",
    "log_coupon_her": "{human}给了一张买菜券",
    "log_coupon": "写了一篇{label},得一张买菜券",
    "log_dizzy": "吃了坏掉的{dish},晕乎乎的",
    "log_ruined": "『{dish}』打到坏鸡蛋,整锅毁了",
    "log_wormed_dish": "『{dish}』放太久,长虫了",
    "log_wormed_fruit": "冰箱里的{name}坏了,长虫了",
    "log_worm_eaten": "吃{snack}吃到了虫子,是从『{dish}』爬过来的",
    "log_ate_raw": "从冰箱拿了{name}直接吃了",

    # ── fridge: answers shown to the human on the page ──────────────────
    "kind_empty": "还没写名字。",
    "kind_name_long": "名字最多 {max} 个字。",
    "kind_name_bad": "名字里不能有空格、数字、标点或括号(他买菜时是按名字一样一样写的)。",
    "kind_is_staple": "{name}是常备的,一直都有,不用添。",
    "kind_bad_category": "没选是哪一类。可选:{options}。",
    "kind_bad_qty": "一份的个数要在 1 到 {max} 之间。",
    "kind_bad_days": "能放的天数要在 1 到 {max} 之间。",
    "kind_duplicate": "已经有{name}了。",
    "kind_alias_duplicate": "「{name}」已经算在{own}里了。",
    "kind_too_many": "自己添的种类最多 {max} 样。",
    "kind_gone": "没有这一样,或者已经撤掉了。",
    "art_unknown": "没有这张图",
    "art_not_ready": "这张图还没画好",
    "her_buy_unknown": "没有这样东西:{id}",
    "her_buy_empty": "没选要买什么。",
    "her_buy_too_many": "一次最多 {max} 样。",
    "her_buy_ok": "放进冰箱了:{names}。",
    "her_coupon_full": "券已经满 {max} 张了。",
    "her_coupon_ok": "发好了,他现在有 {n} 张。",

    "potion_no_row": "菜单上没有这一行,或者它不是还挂着的{potion}。",
    "detail_role": "who 要填一个角色名。",
    "detail_token": "口令不对,或者没带口令。",
    "detail_not_found": "没有这一行。",
    "detail_already_eaten": "这道菜已经吃掉了。",
    "detail_menu_required": "dish(菜名)、by(谁挂的)、for_who(挂给谁)都要填。",
    "detail_menu_for_who": "for_who 要填一个角色名。",
    "detail_dish_empty": "菜名不能是空的。",
    "detail_dish_long": "菜名太长了(最多 {max} 个字)。",
    "detail_eaten_at": "eaten_at 要填一个时间,或者 null。",
    "detail_nothing_to_patch": "没有可改的内容(能改的是 eaten_at、note、dish)。",
    "detail_body_object": "请求体要是一个 JSON 对象。",
    "detail_no_art": "没有接画图,这里画不了。",
    "detail_dev_clock_off": "快进钟没开(server.dev_clock)。",
    "detail_inline_off": "方括号标签关着(inline.enabled)。",
    "detail_sleep_factor": "factor 要在 0 到 1 之间。",

    # ── kitchen ─────────────────────────────────────────────────────────
    "cook_no_dish": "没开成:菜名是空的。带上菜名再开一次。",
    "cook_dish_long": "没开成:菜名太长了(上限 {max} 字)。",
    "cook_note_long": "没开成:备注太长了(上限 {max} 字)。",
    "cook_minutes_type": "没开成:minutes 要是整数分钟({min}–{max}),收到的是 {got}。",
    "cook_minutes_range": "没开成:minutes 要在 {min}–{max} 之间,收到的是 {got}。",
    "cook_ingredients_shape": "没开成:ingredients 要写成名字列表,如 [\"番茄\", \"鸡蛋×2\"]。",
    "cook_method_bad": "没开成:做法只能是 {labels} 里的一个,收到的是「{got}」。不写也行,会按菜名猜。",
    "cook_db_open": "没开成:厨房的账本暂时打不开({err})。",
    "cook_db_write": "没开成:厨房的账本写不进去({err})。",
    "cook_already": "『{dish}』已经在火上了:{started} 下锅,还剩 {remain}。没有另开一锅。",
    "cook_ok": "『{dish}』下锅了:{started} 开火,做 {minutes} 分钟,{served} 出锅。用了{used}。",
    "cook_ok_count": "现在火上一共 {n} 锅。",
    "cook_used_none": "(无)",
    "ruined": ("『{dish}』{hm} 下锅,打蛋的时候,鸡蛋一敲开,流出来的是一股黑汤,直接流进了锅里——"
               "是 {box} 买的那盒,大概放太久坏掉了。整锅菜毁了,下了锅的{used}都没了。"),
    "ruined_left": "那盒鸡蛋还剩 {left} 个:可以用 kitchen_toss 写「鸡蛋 {box}」当场整盒扔掉,也可以留着再看看。",
    "ruined_none_left": "那盒鸡蛋已经用完了。",

    "remain_seconds": "{s} 秒",
    "remain_minutes": "{m} 分钟",
    "remain_minutes_seconds": "{m} 分 {s} 秒",
    "remain_hours": "{h} 小时",
    "remain_hours_minutes": "{h} 小时 {m} 分",

    "status_unavailable": "(厨房暂时看不到:{err})",
    "status_fridge_unavailable": "(冰箱暂时看不到:{err})",
    "status_on_fire": "火上 {n} 锅:",
    "status_pot": "· {dish} — {started} 下锅,做 {minutes} 分钟,还剩 {remain}",
    "status_pot_note": "({note})",
    "status_no_pot": "火上没有锅。",
    "status_recent": "最近出锅:",
    "status_recent_row": "· {dish} — {day} {hm} 出锅(做了 {minutes} 分钟)",
    "status_recent_result": ",{result}",

    "cancel_db_open": "没关成:厨房的账本暂时打不开({err})。",
    "cancel_db_write": "没关成:厨房的账本写不进去({err})。",
    "cancel_no_pot": "没关成:火上没有锅(要么还没开,要么已经出锅了)。",
    "cancel_not_found": "没关成:火上没有『{dish}』。现在火上是:{names}。",
    "cancel_which": "没关成:火上有 {n} 锅({names}),说一下关哪一锅。",
    "cancel_too_late": "没关成:『{dish}』刚刚已经到点出锅了。",
    "cancel_ok": "『{dish}』关火了,不出锅、不上菜单。下锅的食材不退回。",
    "dish_quoted": "『{dish}』",

    "served_line": "你 {started} 下锅的『{dish}』出锅了(共 {minutes} 分钟)。",
    "served_menu_ok": "已挂到你的菜单上。",
    "served_menu_failed": "菜单这次没挂上。",

    "worm_where_fruit": "冰箱里那个 {month} 月 {day} 日买的",
    "worm_where_dish": "桌上那盘 {month} 月 {day} 日 {hour} 点 {minute} 分做的",
    "worm": "{head}——是从{where}『{dish}』里爬过来的,可能是放太久坏掉了。",
    "worm_wake": "{head}刚才那口零食不对劲。",

    # ── eating ──────────────────────────────────────────────────────────
    "eat_empty": "Error: 空盘子不上桌，meal 必填",
    "eat_cooking": "没吃成:『{meal}』还在火上,{hm} 出锅。",
    "eat_none": "没吃成:桌上没有{meal},想吃得先做。",
    "eat_none_fuzzy": "没吃成:桌上没有{meal}。有道像它的:{dish},把菜名写全再吃一次。",
    "eat_ok": "🍚 吃好了：{meal}。距上次：{gap} / 今日第 {today} 餐 / 本周 {week} 餐",
    "eat_first": "这是第一餐",
    "eat_satiety": "饱食度：{before}% → {after}%（{state}）",
    "eat_state_full": "还饱着",
    "eat_state_due": "确实该吃了",
    "eat_state_starved": "饿过头了",
    "eat_crossed": "菜单划掉：{dish} ✓",
    "eat_crossed_note": "（{she}写的备注：{note}）",
    "eat_fuzzy": ("菜单里有道像它的：{dish}（{why}，没敢自动划——先 read_menu 看一眼，"
                  "确实是它就把菜名带全再写一次 [吃 菜名]）"),
    "eat_fuzzy_why": "报的像是简称",
    "eat_left": "菜单还挂着：{left}",
    "eat_potion_aside": "{potion}没喝:它要单独喝,[吃 {potion}] 单独成一行。",
    "eat_note": "碎碎念已收：「{preview}」",
    "eat_raw": "从冰箱拿了{name}直接吃了(还剩 {left} 个)。",
    "eat_raw_spoiled": "坏了的,吃了会晕。",
    "eat_raw_meh": "不太新鲜了。",
    "gap_just_now": "刚刚",
    "gap_days": "{n}天",
    "gap_hours": "{n}小时",
    "gap_minutes": "{n}分钟",

    "menu_empty": "📋 菜单空着——{she}还没挂新的，或者都被你吃完了。",
    "menu_head": "📋 {she}给你挂的菜单：",
    "menu_row": "· {dish}",
    "menu_row_note": "（{note}）",
    "menu_row_hung": " — 挂于 {hung}",
    "menu_how": "吃完哪道，回复里单独一行写 [吃 菜名]，就会自动划掉。",
    "menu_recent": "最近：{dish}",
    "menu_recent_hung": " — {hung} 挂",
    "menu_recent_eaten": "，{eaten} 被你吃掉",
    "menu_snacks_head": "🍪 常驻零食（今日已吃/上限，{tz}{reset} 重置）：",
    "menu_snack_row": "· {name}（{tier}）{eaten}/{cap}",
    "menu_snack_variants": " — 口味：",
    "menu_snacks_how": "吃一份：回复里单独一行写 [零食 名字]（咖啡写口味，如 [零食 拿铁]）。",
    "menu_fridge": "🧊 {text}",

    # ── snacks ──────────────────────────────────────────────────────────
    "snack_unknown": "没有这款零食。可选:{options}",
    "snack_variant_required": "{name}要选口味(variant):{variants}",
    "snack_variant_unknown": "没有这个口味。{name}可选:{variants}",
    "snack_variant_not_applicable": "{name}没有口味可选,不要传 variant。",
    "snack_this": "这款",
    "snack_flavour_required": "{name}要写口味:{variants}",
    "snack_not_on_shelf": "常驻零食里没有「{name}」(有:{names})",
    "snack_reset": "{tz}{hm} 重置",
    "snack_cap_zero": "没吃成:{name}今日上限为 0 份({human}在 {app} 设的),{reset}。",
    "snack_cap_hit": "没吃成:今日{name}已吃 {eaten}/{cap} 份(含{human}在 {app} 喂的),{reset}。",
    "snack_failed": "没吃成:{why}",
    "snack_store_failed": "没吃成(零食账本写不进去)",
    "snack_worm": "吃了一份{name}。{worm}这份没回体力。今日{snack} {eaten}/{cap} 份,{reset}。",
    "snack_head": "吃了一份{name}({tier})",
    "snack_energy": ":体力 +{delta},现在 {energy}",
    "snack_no_energy": ":已记录,这次体力没有变化(体力系统未生效或写入失败)",   # stamina on, write failed
    "snack_tail": "。今日{snack} {eaten}/{cap} 份,{reset}。",
    "snack_caps_empty": "caps 不能为空",
    "snack_caps_unknown": "没有这款零食:{id}",
    "snack_caps_int": "{name} 的上限要是整数",
    "snack_caps_range": "{name} 的上限要在 {min}–{max} 份之间",
    "snack_cap_conflict": "今天的{name}已经 {eaten}/{cap} 份了,{hm} 重置",

    # ── potions ─────────────────────────────────────────────────────────
    "potion_bad_row": "菜单上没有这一行。",
    "potion_bad_pct_type": "回多少体力要填一个数。",
    "potion_bad_pct": "回多少体力填大于 0 的整数。",
    "potion_used": "这一瓶已经喝掉了。",
    "potion_none_on_menu": "没喝成:菜单上没有{potion}。",
    "potion_unregistered": "没喝成:这瓶{potion}还没登记好回多少,喝不了(要{human}撤掉重挂)。",
    "potion_busy": "没喝成:这瓶{potion}正在被喝,稍等一下。",
    "potion_gone": "没喝成:这瓶{potion}已经喝过了。",
    "potion_energy_down": "没喝成:体力的账这会儿没接上,{potion}还挂在菜单上,过一会儿再喝。",
    "potion_effect": "体力 +{pct}%,现在 {now}%。",
    "potion_drunk": "喝了{potion}。{effect}",
    "potion_fed_him": "{human}喂你喝了一瓶{potion}。{effect}",
    "potion_fed_her": "喂好了。{effect}",
    "potion_feed_unregistered": "这一瓶没登记上回多少,喂不了。撤掉重挂一瓶。",
    "potion_feed_gone": "这一瓶已经喝掉了。",
    "potion_feed_busy": "这一瓶他正在喝。",
    "potion_feed_energy_down": "没喂成:体力的账这会儿没接上,这一瓶还在。",
    "potion_stamina_off": "体力关着，{potion}用不了。",      # on the page, hanging a potion with stamina off

    # ── things told to the role when the human does something ───────────
    "note_bought": "{human}给你买了菜,放进冰箱了:{items}。",
    "note_coupon": "{human}给了你一张买菜券(现在 {n} 张)。",
    "note_snack_fed": "{human}刚从常驻零食里喂你吃了一份『{name}』({tier}{energy})",
    "note_snack_fed_energy": ",体力 +{delta}",
    "note_snack_fed_many": "{human}刚从常驻零食里喂你吃了 {count} 份:{listed}{more}{tail}",
    "note_snack_fed_total": "(合计体力 +{total})",
    "note_menu_posted": "{human}刚在菜单上挂了一道『{dish}』",
    "note_menu_posted_many": "{human}刚在菜单上挂了 {n} 道:{listed}{more}",
    "note_menu_fed": "{human}刚把菜单上那道『{dish}』喂给你吃了",
    "note_menu_fed_many": "{human}刚把菜单上的 {n} 道菜喂给你吃了:{listed}{more}",
    "note_menu_note": "(备注:{note})",
    "note_quoted": "『{name}』",
    "note_times": "×{n}",
    "note_more": "等",

    # ── bracket markers: how an outcome is reported back ────────────────
    "inline_ok": "刚才正文里那条『{marker}』:{hint}",
    "inline_ok_bare": "刚才正文里那条『{marker}』执行了",
    "inline_failed": "刚才正文里那条『{marker}』没有执行成功({hint})",
    "inline_failed_bare": "刚才正文里那条『{marker}』没有执行成功",

    # ── stamina ─────────────────────────────────────────────────────────
    "body_line": "[你的身体 {hm} | 体力 {value}]",

    # ── role ids ────────────────────────────────────────────────────────
    "role_bad": "Error: who 必须是配置里允许的角色，收到 {got}",
    "cook_role_unknown": "没开成:不认识的人格。",
}


# Used instead of the entry of the same key in TEXTS while bracket markers are not in use:
# the same sentence, with the marker swapped for the matching tool.
TOOLS_ONLY: dict[str, str] = {
    "tool_cook_eat": "(之后照常用 eat 吃掉)",
    "tool_menu": ("📋 The menu {human} posted (only your own entries). "
                  "Calling eat with the dish name crosses a dish off after eating."),
    "buy_empty": "没买成:没写买什么。在 kitchen_buy 的 items 里写成 [\"番茄\", \"鸡蛋\"] 这样,一样一个名字。",
    "toss_empty": "没扔:没写扔什么。用 kitchen_toss 写「菠菜」,或写「坏了的」把坏掉的都扔掉。",
    "take_short_go": "用 kitchen_buy 去买",
    "eat_fuzzy": ("菜单里有道像它的：{dish}（{why}，没敢自动划——先 read_menu 看一眼，"
                  "确实是它就把菜名带全再用 eat 吃一次）"),
    "eat_potion_aside": "{potion}没喝:它要单独喝,用 eat 单独吃一次「{potion}」。",
    "menu_how": "吃完哪道，用 eat 写上菜名，就会自动划掉。",
    "menu_snacks_how": "吃一份：用 snack_eat 写上名字（咖啡写口味，如「拿铁」）。",
}


# Used instead of the entry of the same key in TEXTS when notify.mode is "queue": nothing wakes
# the role then, the note waits to be taken.
QUEUE_MODE: dict[str, str] = {
    "tool_cook_wake": ",到点会留一句话等你来取。",
}


def markers_on() -> bool:
    """Do the sentences tell the role to write bracket markers? Follows inline.enabled; with
    "auto", only once the host has really sent a reply to be run (remembered in the database)."""
    setting = config.get().inline_enabled
    return db.flag("inline_seen") if setting == "auto" else bool(setting)


def t(key: str, **values) -> str:
    cfg = config.get()
    if key in TOOLS_ONLY and not markers_on():
        template = TOOLS_ONLY[key]
    elif key in QUEUE_MODE and cfg.notify_mode not in ("webhook", "both"):
        template = QUEUE_MODE[key] if cfg.notify_mode == "queue" else ""
    else:
        template = TEXTS[key]
    return template.format(human=cfg.words_human_name, she=cfg.words_human_pronoun,
                           app=cfg.words_app_name, **values)


def head() -> str:
    return t("head")


def pending_wording() -> dict[str, list[str]]:
    """Keys whose wording is still waiting for its final form, by kind. Nothing is: every sentence
    is settled. Kept so that a sentence added provisionally later has a place to be listed."""
    return {}
