"""Every sentence the upgrade added (recipes, dish book, achievements, plates, jars, vendors), in one place.

Same rules as :mod:`kitchenette.texts`: facts, no advice, no feelings assigned. ``{human}`` and
``{she}`` are filled from ``[words]`` like everywhere else. ``tp(key, **values)`` fills one.

The tables at the end (mishaps, achievements, the vendors and what they sell, flowers) are data
that you may edit: add a mishap, change what the sweet-potato man sells, rename a flower.
The tunable numbers are settings (``[recipes]``, ``[dishwash]``, ``[jars]``, ``[vendor]``).
"""
from __future__ import annotations

import hashlib

from . import config

# ── fixed numbers that are part of the rules ───────────────────────────
TIER_NAMES = ("生疏", "拿手", "招牌")
JAR_COUNT = 3
JAR_DAYS_FRUIT = 3
JAR_DAYS_SOUR_FRUIT = 2
JAR_DAYS_VEG = 1
JAR_DAYS_EGG = 1
JAR_DAYS_OTHER = 2                 # anything else from the fridge: meat, tofu, staples, what the vendors bring…
SOUR_FRUITS = ("柠檬", "青梅", "梅子", "山楂", "百香果")
JAR_PORTIONS_MIN, JAR_PORTIONS_MAX = 3, 5
JAR_SEASONINGS_MAX = 6
# Seasonings: any word goes in (they count as always at hand, nothing is taken from the fridge). A word is
# sorted by the characters in it, only to name what comes out, to pick the jar's look and to spot the odd
# combinations below; no seasoning is ever refused.
JAR_HONEY_KEYS = ("蜜",)
JAR_SWEET_KEYS = ("糖", "蜜")
JAR_SALT_KEYS = ("盐",)
JAR_SALTY_KEYS = ("盐", "酱油", "生抽", "老抽", "鱼露", "豉油", "味噌", "蚝油")
JAR_SOUR_KEYS = ("醋",)
JAR_SUFFIX = "(罐)"
NIGHT_HOURS = (22, 23, 0, 1, 2, 3)
WEATHER_COLD_C = 8.0
WEATHER_HOT_C = 28.0
BROWSE_MAX_LINES = 12
TAG_NAME_MAX = 20
TAG_ITEMS_MAX = 10
TAG_NOTE_MAX = 60
MENU_MAX_DISHES = 6
CODE_MAX_CHARS = 1600
METHOD_CN = {"stirfry": "炒", "fry": "煎", "deepfry": "炸", "boil": "煮", "steam": "蒸", "bake": "烤", "mix": "拌"}

TEXTS: dict[str, str] = {
    # ── teaching (only for what is switched on, and only while markers are in use) ──
    "teach_recipe_book": ("[收藏 菜名或编号] 单独成行,把公共食谱里的一道收进你的食谱本。"
                          "[记菜 菜名 用料… 做法 分钟] 单独成行,把你自己的菜记成一页;后面加「改自 编号」就是改编。"
                          "竖线后面可以再跟一句你想说的话,如 [记菜 溏心蛋盖饭 鸡蛋 米饭 煮 10 | 第一次自己想的]。"),
    "teach_recipe_book_no_public": ("[记菜 菜名 用料… 做法 分钟] 单独成行,把你自己的菜记成一页。"
                                    "竖线后面可以再跟一句你想说的话。"),
    "teach_recipe_cook": ("[买菜 照 编号] 单独成行,按这份食谱把冰箱里缺的料一次买齐,用一张买菜券,不受 {max} 样限制。"
                          "一样都不缺就不扣券。"),
    "teach_tasting_notes": "[札记 编号 一句话] 单独成行,给这一页留一行:这次改了什么、结果怎样、下次想试什么。",
    "teach_orders": "{human}点的菜会出现在看厨房的那段里。[接单 菜名] 单独成行,告诉{she}你打算做;想换个做法,就在后面写上。",
    "teach_menus": "[配一桌 编号 编号 编号 | 一句话] 单独成行,把几道配成一顿。",
    "teach_recipe_codes": "[出码 编号] 单独成行,把你食谱本里的一页变成一串码,可以发给别人。",
    "teach_dishwash": "[刷盘子] 单独成行,开始刷水槽里的盘子。真实计时,一只一小段。",
    "teach_seal_jars": ("[封罐 食材 调料 | 纸条] 单独成行,把冰箱里的东西封进窗台的罐子。调料写什么都行,几样用「、」隔开;"
                        "想给泡出来的东西起名,在调料后面写「= 名字」,如 [封罐 鸡蛋 酱油、糖、小米辣 = 麻药鸡蛋 | 等周五开]。"
                        "纸条和名字都可以不写。等一到三天,到日子自己开,成品进零食架,用 [零食 名字] 取。"),
    "teach_vendor": ("楼下有小贩的时候:[问小贩 你想问的话] 单独成行,跟他说话;[买 东西 数量] 单独成行,"
                     "用你的零花钱买。他的回话下一轮才看得到。"
                     "[送花 一句话] 单独成行,把买来的花送给{human},附一句话。"
                     "[想要花 花名] 单独成行,想要卖花的带一种新的花,会递给{human},{she}同意了才会有。"),

    # ── the one new tool ──
    "tool_browse": ("翻食谱。可以看今天推荐什么、某样食材能做什么、按分类翻、看你自己的食谱本,"
                    "或者看你拿到的厨房成就。回的是一行一条的速查:菜名、用料、做法、大概几分钟。只读。"),
    "tool_browse_q": "找什么:菜名、食材名(如「鸡翅」)或分类名(如「汤」);看推荐、看本子、看成就时不用写。",
    "browse_today": "今天推荐", "browse_find": "按菜名或食材找", "browse_category": "按分类翻",
    "browse_mine": "我的本子", "browse_achievements": "我拿到的成就",
    "tool_cook_recipe": "食谱编号(可省):照哪一份食谱做。不写就是自己发挥。",

    # ── the kitchen status ──
    "rec_head_ready": "今天可以试试(冰箱里的料够):",
    "rec_head_only_one": "今天料够的只有这一道:",
    "rec_head_near": "还差一点就能做:",
    "rec_none": "冰箱里的料今天凑不出食谱上的菜。",
    "rec_down": "推荐暂时看不到,照常可以自己开锅。",
    "rec_line": "· {name}({rid}) — {items} · {method} · 约 {minutes} 分钟",
    "rec_line_near": "· {name}({rid}) — 还缺 {missing}",
    "rec_not_sold": "{name}(超市没有卖)",
    "rec_dislike": "这几样{human}不让推:{items}。",
    "weather_rain": "外面在下雨。", "weather_cold": "今天降温了。", "weather_hot": "今天很热。", "weather_night": "已经很晚了。",
    "order_line": "{human}点了:{name}({rid})。",
    "order_line_short": "{human}点了:{name}({rid}),还缺 {missing}。",
    "order_line_planned": "{human}点的{name}({rid}),你说了打算做。",
    "jars_head": "窗台罐子:",
    "jar_line": "· {what}(还剩 {left}){note}",
    "jar_line_empty": "· 空着一只",
    "jar_note": " — 纸条:「{note}」",
    "sink_line": "水槽里有 {n} 只盘子。",
    "sink_washing": "正在刷盘子:还剩 {n} 只,大概 {left}。",
    "staples_none": "(常备就够)",

    # ── cooking and serving ──
    "cook_no_recipe": "没开成:没有这个食谱编号。用翻食谱查一下。",
    "cook_recipe_short": "照「{name}」还缺:{missing}。",
    "cook_changed": "这次和「{name}」的做法不一样(少了 {missing}),记成改了做法。想留着可以用 [记菜 …] 存成自己的一页。",
    "cook_changed_tools": "这次和「{name}」的做法不一样(少了 {missing}),记成改了做法。",
    "cook_menu": "「{name}」是一桌菜单,要一道一道开锅。",
    "feature_off": "这个玩法没开。",
    "egg_saved": "打第{nth}个鸡蛋的时候先打在小碗里看了一眼:坏的。扔掉了,换了一个。{box} 买的那盒还剩 {left} 个。",
    "egg_saved_many": "打鸡蛋的时候先打在小碗里看了一眼:有 {n} 个是坏的。扔掉了,换了好的。{box} 买的那盒还剩 {left} 个。",
    "egg_no_spare": "打鸡蛋的时候先打在小碗里看了一眼:坏的。扔掉了,冰箱里没有别的蛋,这一锅没开成,别的料没动。",
    "log_egg_tossed": "打开了 {n} 个坏鸡蛋扔了,换了好的",
    "log_egg_tossed_none": "打开了 {n} 个坏鸡蛋扔了,没有别的蛋,没开锅",
    "tier_up": "「{name}」做成 {n} 次了,现在是{tier}。",
    "new_dish_bonus": "第一次吃到照谱做成的「{name}」,体力多回了一点。",
    "card_smooth": "一路顺利",
    "stamp_first": "第一次做", "stamp_follow": "照谱做成", "stamp_changed": "改了做法",

    # ── marker receipts ──
    "fav_ok": "收进食谱本了:{name}({rid})。",
    "fav_dup": "已经在你的食谱本里了:{name}({rid})。",
    "fav_none": "没收成:食谱里没有这一道。用翻食谱查一下。",
    "fav_need_public": "没收成:公共食谱没开。",
    "rec_ok": "记下了:{name}({rid})。",
    "rec_bad": "没记成:要写上菜名、用料、做法和分钟,如 [记菜 溏心蛋盖饭 鸡蛋 米饭 煮 10]。",
    "rec_unknown": "没记成:{names} 不是冰箱里会有的东西。",
    "rec_no_items": "没记成:用料里要有冰箱里的东西(米油盐酱油不算)。",
    "rec_bad_from": "没记成:「改自」后面的编号没找到。",
    "rec_too_long": "没记成:太长了(菜名最多 {name_max} 字,用料最多 {items_max} 样,那句话最多 {note_max} 字)。",
    "note_ok": "记下了。",
    "note_none": "没记成:没有这个编号。",
    "note_bad": "没记成:要写编号和一句话,如 [札记 p-1a2b 下次少放点盐]。",
    "order_accept": "告诉{human}了:打算做{name}。",
    "order_note_saved": "告诉{human}了:打算做{name},想换个做法——{note}。",
    "order_none": "没接成:{human}没有点「{name}」。",
    "order_no_recipe": "没有这个食谱编号。",
    "menu_ok": "配好了:{n} 道。",
    "menu_ok_short": "配好了:{n} 道。合起来还缺 {missing}。",
    "menu_bad": "没配成:要写两道以上的编号,最多 {max} 道。",
    "menu_missing": "没配成:这几个编号没找到:{ids}。",
    "menu_gone": "这一页已不在",
    "code_ok": "这一页的码:{code}",
    "code_ok_page": "这一页的码做好了(太长,回执放不下):{name}。{human}在食谱本里能复制。",
    "code_none": "没出成:你的食谱本里没有这一页。",
    "code_bad": "这串码认不出来。",
    "buy_ok": "照「{name}」买好了:{items},放进冰箱了。用掉一张买菜券(还剩 {left} 张)。",
    "buy_ok_partial": "照「{name}」买好了:{items},放进冰箱了。用掉一张买菜券(还剩 {left} 张)。{not_sold} 超市没有卖。",
    "buy_log": "照「{name}」买了{items}",
    "buy_nothing": "照「{name}」一样都不缺,没用券。",
    "buy_not_sold": "照「{name}」缺的 {not_sold} 超市没有卖,没用券。",
    "buy_no_recipe": "没买成:没有这个食谱编号。用翻食谱查一下。",
    "tag_too_long": "没成:这一行太长了。",
    "store_failed": "没成({marker}的账本写不进去)。",

    # ── browsing ──
    "browse_line": "· {name}({rid}) — {items} · {method} · 约 {minutes} 分钟",
    "browse_mine_line": "· [{kind}] {name}({rid}) — {items} · {method} · 约 {minutes} 分钟{note}",
    "browse_mine_menu": "· [{kind}] {name}({rid}){note}",
    "browse_empty": "没找到。可以换个菜名或食材再找。",
    "browse_mine_empty": "你的食谱本还是空的。",
    "browse_more": "还有 {n} 道没列出来,换个更具体的词找。",
    "browse_categories": "分类:{cats}。",
    "browse_need_q": "要写找什么(菜名、食材或分类)。",
    "browse_unavailable": "食谱暂时翻不开。",
    "kind_fav": "收藏", "kind_adapt": "改编", "kind_own": "自创", "kind_menu": "一桌", "kind_code": "别人的码",
    "ach_line": "· {name}({md} 拿到)— {why}",
    "ach_none": "还没有拿到厨房成就。",

    # ── plates ──
    "wash_start": "开始刷了:{n} 只盘子,大概 {minutes} 分钟。",
    "wash_already": "正在刷:还剩 {n} 只,大概 {left}。",
    "wash_empty": "水槽里没有盘子。",
    "wash_self_off": "现在盘子都进洗碗机,不用刷。",
    "wash_done": "{n} 只盘子刷完了。",
    "wash_done_broken": "{n} 只盘子刷完了。{broke}",
    "wash_stopped": "刷了 {done} 只,剩下的进洗碗机了。",
    "wash_minutes": "{m} 分钟", "wash_hours": "{h} 小时 {m} 分",

    # ── jars ──
    "jar_sealed": "封上了:{what}。{ready}好。{note}",
    "jar_sealed_note": "纸条:「{note}」",
    "jar_sealed_named": "{what}(开出来叫{name})",
    "jar_full": "没封成:三只罐子都用着,最早的一只{when}空出来。",
    "jar_full_later": "过几天",
    "jar_no_item": "没封成:冰箱里没有{name}。",
    "jar_bad_format": "没封成:写成 [封罐 食材 调料 | 纸条] 这样,如 [封罐 鸡蛋 酱油、糖 = 麻药鸡蛋 | 纸条]。",
    "jar_unknown": "没封成:{name}不是冰箱里会有的东西。",
    "jar_opened": "窗台上的{goods}泡好了,收进零食架了({n} 份)。",
    "jar_failed": "窗台上那罐{name}开出来是坏的(封进去的时候就坏了),整罐扔了,罐子洗干净空出来了。",
    "jar_failed_odd": "窗台上那罐{what}开出来味道不对,整罐扔了,罐子洗干净空出来了。",
    "jar_take": "{verb}了一份{goods}。封罐时的纸条:「{note}」",
    "jar_take_no_note": "{verb}了一份{goods}。",
    "jar_fed": "{human}喂了你一份{goods}。",
    "jar_fed_note": "封罐时的纸条:「{note}」",
    "jar_cap": "今天罐子里泡的已经吃了 {n} 份,到上限了。",
    "jar_none": "没吃成:零食架上没有{name}。",
    "jar_log": "把{name}封进了窗台的罐子",
    "jar_today": "今天", "jar_tomorrow": "明天", "jar_after": "后天", "jar_date": "{m} 月 {d} 日",
    "jar_morning": "早上", "jar_noon": "中午", "jar_afternoon": "下午", "jar_evening": "晚上",
    "jar_days_hours": "{d} 天 {h} 小时", "jar_days": "{d} 天", "jar_hours": "{h} 小时", "jar_under_hour": "不到 1 小时",

    # ── vendors ──
    "vendor_call": "想买可以叫住{pron}。",
    "vendor_status": "楼下有{who},大概还待 {mins} 分钟。",
    "vendor_flower": "窗台上插着一束{name}({md} 买的{state})。",
    "flower_droopy": ",有点蔫了", "flower_wilted": ",已经谢了",
    "talk_receipt": "{prices}\n小贩说:「{line}」",
    "talk_price": "{name} {price} 一{unit}({stock})",
    "talk_left": "还有 {n} {unit}", "talk_soldout": "卖完了",
    "talk_too_many": "没问成:这一趟已经问了 {n} 句,{pron}忙着招呼别人了。",
    "talk_gone": "没问成:楼下现在没有小贩。",
    "talk_empty": "没问成:要写想问的话,写成 [问小贩 你想问的话]。",
    "talk_first": "这位邻居第一次来你这儿买东西。",
    "talk_regular": "这位邻居是熟客,上次在你这儿买的是{last}。",
    "talk_goods": "车上现在有:{names}。",
    "talk_goods_none": "车上的东西卖完了。",
    "talk_turn": "楼上的邻居对你说:{line}",
    "vbuy_ok": "买了 {qty} {unit}{name},花了 {total}。零花钱还剩 {balance}。",
    "vbuy_ok_nobal": "买了 {qty} {unit}{name},花了 {total}。",
    "vbuy_ate": "当场吃掉了。",
    "vbuy_fridge": "放进冰箱了(小贩专供,超市没有卖)。",
    "vbuy_flower": "插在窗台的花瓶里了。",
    "vbuy_flower_replaced": "原来那束{old}收起来了。",
    "vbuy_note": "{pron}附了一张纸条:{note}",
    "vbuy_deal": "\n小贩说:「{line}」",
    "vbuy_broke": "没买成:零花钱不够(要 {total},有 {balance})。",
    "vbuy_order_cap": "没买成:一次最多花 {cap},这一单要 {total}。",
    "vbuy_day_cap": "没买成:今天在小贩这儿已经花了 {spent},再买这单就超过 {cap} 了。",
    "vbuy_soldout": "没买成:{name}卖完了。",
    "vbuy_short": "没买成:{name}只剩 {left} {unit}了。",
    "vbuy_none": "没买成:楼下现在没有小贩。",
    "vbuy_unknown": "没买成:{who}没有「{name}」。车上有:{names}。",
    "vbuy_ambiguous": "没买成:「{name}」有好几样:{names},写清楚要哪个。",
    "vbuy_bad_qty": "没买成:数量要写成 1 到 {max} 之间的数,写成 [买 东西 数量]。",
    "vbuy_empty": "没买成:要写买什么,写成 [买 东西 数量]。",
    "vbuy_wallet_off": "没买成:零花钱的账本现在连不上,这一单没扣钱。",
    "vbuy_pending": "钱的事还在确认,确认好了会告诉你。",
    "vbuy_failed": "没买成:这一单没扣成钱。",
    "vbuy_conflict": "这个单号已经用过,内容对不上。",
    "vbuy_store_failed": "没买成(小贩的账本写不进去),没扣钱。",
    "vendor_refund": "刚才那单{name}没成,{total} 退回来了。",
    "pocket_given": "{human}给了你 {amount} 零花钱,现在有 {balance}。",
    "vendor_treat": "{human}在楼下给你买了 {qty} {unit}{name}。",
    "treat_fridge": "放进冰箱了。", "treat_flower": "插在窗台的花瓶里了。", "treat_ate": "已经替你吃上了。",
    "treat_too_many": "一次最多请 {n} 份。",
    "vendor_snack_hint": "{name}是楼下小贩卖的,不在常驻零食里;要买写 [买 {name}]。",
    "vendor_log_snack": "在楼下小贩那儿吃了{name}×{qty}",
    "vendor_log_bought": "从楼下小贩那儿买了{name}×{qty}",
    "vendor_log_gift": "{text}",
    "gift_ok": "花送给{human}了,你的话压在窗台那瓶{name}下面。",
    "gift_none": "没送成:窗台上没有花。",
    "gift_wilted": "没送成:窗台上那束{name}已经谢了。",
    "gift_done": "没送成:窗台上那束{name}已经送过了。",
    "gift_empty": "没送成:要附一句话,写成 [送花 一句话]。",
    "want_ok": "想要「{name}」的事递给{human}了,{she}同意了卖花的才会带。",
    "want_known": "「{name}」卖花的本来就会带(按季节)。",
    "want_dup": "「{name}」已经递过了,在等{human}看。",
    "want_bad": "没递成:花名写成两到八个字,写成 [想要花 名字]。",
    "want_yes": "{human}同意了你想要的「{name}」,画好以后卖花的就会带。",
    "want_no": "{human}没有同意画「{name}」。",
}


def tp(key: str, **values) -> str:
    cfg = config.get()
    return TEXTS[key].format(human=cfg.words_human_name, she=cfg.words_human_pronoun, app=cfg.words_app_name,
                             **values)


# ── mishaps: one sentence, never changes how the dish turns out ─────────
MISHAP_VERSION = 1
MISHAPS: dict[str, tuple[str, ...]] = {
    "stirfry": ("炒的时候油溅到手背上,烫了一下。", "颠锅颠出去两块,捡回来了。", "锅铲磕到锅沿,声音大得自己吓一跳。",
                "葱花撒到锅外面去了一半。", "火开大了,手忙脚乱了几秒。"),
    "fry": ("翻面翻早了,粘了一小块在锅上。", "油星子蹦到袖口上了。", "想单手翻面,没成,用了铲子。",
            "锅盖上的水滴进油里,噼啪了一阵。"),
    "deepfry": ("东西没沥干就下锅,油炸了一下,往后跳了一步。", "捞的时候漏勺歪了,掉回去一个。",
                "第一个下锅太早,油还没热,捞出来重炸。", "站得离锅太远,下料全靠扔。"),
    "boil": ("开盖的时候被蒸汽扑了一脸。", "水开溢出来一点,赶紧关小了火。", "尝咸淡的时候烫到舌头。",
             "汤勺滑进锅里,捞了半天。"),
    "steam": ("揭蒸笼的时候手指被烫了一下,捏了捏耳垂。", "蒸锅的水差点烧干,补了半碗。",
              "忘了垫布,盘子烫得端不住,换了两次手。"),
    "bake": ("拿烤盘忘了戴手套,手刚碰上就缩回来了。", "定时器响的时候正走神,晚了半分钟。",
             "开烤箱门凑太近,被热气扑了一脸。", "锡纸铺反了,拿出来重铺。"),
    "mix": ("拌的时候用力大了,溅了一点到台面上。", "醋倒多了一点,又补了点别的找平。", "筷子掉了一根,换了一双。"),
    "general": ("切菜的时候切到手,口子不大,贴了个创可贴。", "洋葱切得眼泪直流。", "鸡蛋壳掉进碗里一小片,捞了半天。",
                "盐罐子拿成了糖罐子,闻了一下才发现。", "围裙带子松了,做到一半重新系。", "菜板滑了一下,垫了块湿布。",
                "找不到锅盖,最后在水槽边上找到了。", "洗菜的时候水开太大,溅了一身。", "调料瓶盖没拧紧,一倒掉下来了。",
                "打了个喷嚏,赶紧转过头去。", "袖子没挽好,沾到了酱汁。", "菜刀有点钝,切得很吃力。",
                "抽油烟机忘了开,做到一半才想起来。"),
}

WASH_BREAK_LINES = ("手一滑,打碎了一只盘子。", "洗洁精太滑,一只盘子掉进水槽磕成了两半。", "盘子没码稳,倒下来碎了一只。")

# ── jars: combinations that go wrong ───────────────────────────────────
# Sealed all the same (never refused at the jar); on the day it opens, such a jar mostly comes out
# tasting wrong and is thrown away (JAR_ODD_FAIL_P of them). Small on purpose: only what is known to spoil.
# names = ingredient names, cats = fridge categories; when: "any" = whatever went with it,
# "salty_or_sour" = with something salty or sour, "only_sweet" = with nothing but sweet things.
JAR_ODD_COMBOS: tuple[dict, ...] = (
    {"names": ("牛奶", "酸奶", "奶油", "黄油"), "cats": (), "when": "salty_or_sour"},   # milk with salt, soy, vinegar: curdles
    {"names": (), "cats": ("meat",), "when": "only_sweet"},                         # raw meat, fish, prawns in sugar only
    {"names": (), "cats": ("staple_food",), "when": "any"},                         # noodles, udon, rice: go soggy and sour
)
JAR_ODD_FAIL_P = 0.8


# ── achievements: (key, name, the line that says how it was earned) ────
ACHIEVEMENTS: tuple[tuple[str, str, str], ...] = (
    ("one_method", "学会一种做法", "{method}做成了 3 锅。"),
    ("all_methods", "七种做法全会", "炒煎炸煮蒸烤拌各做成了 3 锅。"),
    ("five_of_seven", "连续七天里有五天开火", "七天里有五天出过锅。"),
    ("own_dish", "自创菜第一次做成", "照自己记的「{dish}」做成了。"),
    ("rescued", "救回一份快放坏的食材", "用不太新鲜的{item}做成了「{dish}」。"),
    ("vendor_regular", "小贩常客", "在小贩那儿买满了 10 单。"),
    ("first_burnt", "第一次糊锅", "「{dish}」糊了。"),
    ("first_worm", "第一次长虫", "「{dish}」长虫了。"),
    ("late_night", "深夜开火", "{hm} 开火做了「{dish}」。"),
    ("fifty_eggs", "蛋的五十种做法", "用鸡蛋做过 50 道不同的菜。"),
    ("hundred_plates", "刷满一百只盘子", "亲手刷干净了 100 只盘子。"),
    ("first_jar", "第一次泡成", "窗台上的{goods}泡好了。"),
)

# ── vendors ────────────────────────────────────────────────────────────
SNACK_PRICE_RANGE = (3, 8)
INGREDIENT_PRICE_RANGE = (8, 15)
TALK_MAX_PER_VISIT = 6
TALK_LINE_MAX = 60
REGULAR_EVERY = 5
STAY_MIN_S = 45 * 60
STAY_MAX_S = 90 * 60
LAST_ARRIVAL_HOUR = 21
FLOWER_DAYS = 3.0
FLOWER_DROOPY_AFTER_DAYS = 1.5
FLOWER_CLEAR_AFTER_WILT_DAYS = 1.0
FLOWER_NOTE_MAX = 60
FLOWER_PRICE_DEFAULT = 12

FLOWER_VARIETIES: tuple[dict, ...] = (
    {"id": "rose", "name": "玫瑰", "months": tuple(range(1, 13)), "price": 12},
    {"id": "sunflower", "name": "向日葵", "months": (6, 7, 8, 9), "price": 10},
    {"id": "tulip", "name": "郁金香", "months": (2, 3, 4, 5), "price": 12},
    {"id": "bellflower", "name": "桔梗", "months": (8, 9, 10, 11), "price": 10},
    {"id": "chamomile", "name": "洋甘菊", "months": (4, 5, 6, 7), "price": 10},
    {"id": "narcissus", "name": "水仙", "months": (12, 1, 2, 3), "price": 11},
)


def vendor_id(name: str) -> str:
    """Id of an ingredient only the vendors bring (same scheme as the recipe index)."""
    return "v_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


VENDOR_ONLY_INGREDIENTS: tuple[dict, ...] = tuple({**it, "id": vendor_id(it["name"])} for it in (
    {"name": "山楂", "category": "fruit", "pack_qty": 1, "shelf_days": 7},
    {"name": "山药", "category": "root", "pack_qty": 1},
    {"name": "栗子", "category": "root", "pack_qty": 1, "aliases": ("生栗子", "板栗")},
    {"name": "腐竹", "category": "dairy", "pack_qty": 1, "shelf_days": 30},
    {"name": "红豆", "category": "staple_food", "pack_qty": 1, "shelf_days": 30},
    {"name": "紫菜", "category": "veg", "pack_qty": 1, "shelf_days": 30},
    {"name": "炼乳", "category": "dairy", "pack_qty": 1, "shelf_days": 30},
    {"name": "干桂花", "category": "veg", "pack_qty": 1, "shelf_days": 60, "aliases": ("桂花",)},
))

PERSONA_RULES = (
    "你只说小贩当场会说的一两句话,口语,不超过四十个字。"
    "不说任何数字,不报价钱,价钱贴在车上。"
    "不白给东西,不让价,不答应以后给谁留货,不赊账。只卖车上有的东西,没有的就说没有。"
    "不用引号、括号、英文,不换行。"
    "你只听得到楼上邻居对你说的话,也只回应这句话。"
)

# Each good: kind = snack (eaten on the spot) / ingredient (into the fridge) / flower (on the sill;
# the florist picks by season). stock = how many come on one visit (fixed on arrival); satiety in
# points; energy = stamina (0.03 = 3 points); note = the recipe slip that comes with an ingredient.
VENDORS: dict[str, dict] = {
    "tanghulu": {
        "name": "糖葫芦", "who": "卖糖葫芦的", "pron": "他",
        "months": (10, 11, 12, 1, 2, 3, 4), "hours": (13, 20), "rain_ok": True,
        "arrive": "楼下有人在喊:糖葫芦——",
        "goods": (
            {"id": "hawthorn_stick", "name": "山楂糖葫芦", "kind": "snack", "unit": "串",
             "price": 5, "stock": (4, 8), "satiety": 5.0, "energy": 0.03, "aliases": ("山楂的",)},
            {"id": "strawberry_stick", "name": "草莓糖葫芦", "kind": "snack", "unit": "串",
             "price": 8, "stock": (1, 3), "satiety": 5.0, "energy": 0.03, "aliases": ("草莓的",)},
            {"id": "hawthorn", "name": "山楂", "kind": "ingredient", "ingredient": vendor_id("山楂"), "unit": "份",
             "price": 8, "stock": (2, 4), "note": "山楂 — 加冰糖熬成山楂酱,或者封罐泡两天。"},
        ),
        "persona": "你是推着车在居民楼下卖糖葫芦的大叔,手脚麻利,爱夸自己的糖壳脆。",
        "fixed": {"greet": "刚蘸的,糖壳还脆着呢。", "deal": "好嘞,拿稳了,签子尖。",
                  "soldout": "这样没了,别的还有。", "broke": "差一点儿,下回吧。"},
    },
    "sweet_potato": {
        "name": "烤红薯", "who": "卖烤红薯的", "pron": "他",
        "months": (10, 11, 12, 1, 2, 3), "hours": (14, 20), "rain_ok": True,
        "arrive": "楼下飘上来一股烤红薯的味道。",
        "goods": (
            {"id": "roast_sweet_potato", "name": "烤红薯", "kind": "snack", "unit": "个",
             "price": 6, "stock": (3, 6), "satiety": 10.0, "energy": 0.04},
            {"id": "yam", "name": "山药", "kind": "ingredient", "ingredient": vendor_id("山药"), "unit": "份",
             "price": 8, "stock": (2, 4), "note": "山药 — 切片清炒,或者蒸十五分钟蘸糖。"},
        ),
        "persona": "你是守着烤炉卖烤红薯的老爷爷,说话慢,总提醒人小心烫。",
        "fixed": {"greet": "刚出炉的,捧着暖手。", "deal": "烫,拿纸包着。",
                  "soldout": "今天的烤完了。", "broke": "钱不够呐。"},
    },
    "chestnut": {
        "name": "炒栗子", "who": "卖炒栗子的", "pron": "他",
        "months": (9, 10, 11, 12, 1, 2), "hours": (12, 20), "rain_ok": True,
        "arrive": "楼下有炒栗子的锅铲声。",
        "goods": (
            {"id": "roast_chestnut", "name": "糖炒栗子", "kind": "snack", "unit": "袋",
             "price": 7, "stock": (4, 8), "satiety": 8.0, "energy": 0.03, "aliases": ("炒栗子",)},
            {"id": "chestnut", "name": "栗子", "kind": "ingredient", "ingredient": vendor_id("栗子"), "unit": "份",
             "price": 10, "stock": (2, 3), "note": "栗子 — 和鸡腿一起炖,四十分钟。"},
        ),
        "persona": "你是翻着大铁锅炒栗子的小伙子,嗓门大,手上不停。",
        "fixed": {"greet": "现炒的,闻见香了吧。", "deal": "趁热剥,凉了粘壳。",
                  "soldout": "这锅卖完了,下锅还得等。", "broke": "还差点儿。"},
    },
    "douhua": {
        "name": "豆腐脑", "who": "卖豆腐脑的", "pron": "他",
        "months": tuple(range(1, 13)), "hours": (7, 11), "rain_ok": True,
        "arrive": "楼下有人在喊:豆腐脑——",
        "goods": (
            {"id": "sweet_douhua", "name": "甜豆腐脑", "kind": "snack", "unit": "碗",
             "price": 4, "stock": (4, 8), "satiety": 8.0, "energy": 0.02, "aliases": ("甜的",)},
            {"id": "salty_douhua", "name": "咸豆腐脑", "kind": "snack", "unit": "碗",
             "price": 4, "stock": (4, 8), "satiety": 8.0, "energy": 0.02, "aliases": ("咸的",)},
            {"id": "yuba", "name": "腐竹", "kind": "ingredient", "ingredient": vendor_id("腐竹"), "unit": "份",
             "price": 9, "stock": (2, 3), "note": "腐竹 — 泡软了炒青菜,或者放进汤里炖。"},
        ),
        "persona": "你是挑着担子卖豆腐脑的阿姨,早上出摊,甜咸都卖,从不争甜咸。",
        "fixed": {"greet": "甜的咸的都有。", "deal": "勺子在碗里,慢点喝。",
                  "soldout": "桶见底了。", "broke": "还差点儿。"},
    },
    "popcorn": {
        "name": "爆米花", "who": "爆爆米花的", "pron": "他",
        "months": tuple(range(1, 13)), "hours": (13, 20), "rain_ok": True,
        "arrive": "楼下「嘭」的一声,是爆米花。",
        "goods": (
            {"id": "caramel_popcorn", "name": "焦糖爆米花", "kind": "snack", "unit": "袋",
             "price": 5, "stock": (3, 6), "satiety": 4.0, "energy": 0.02},
            {"id": "plain_popcorn", "name": "原味爆米花", "kind": "snack", "unit": "袋",
             "price": 3, "stock": (3, 6), "satiety": 4.0, "energy": 0.02},
            {"id": "redbean", "name": "红豆", "kind": "ingredient", "ingredient": vendor_id("红豆"), "unit": "份",
             "price": 8, "stock": (2, 4), "note": "红豆 — 泡一夜,煮成红豆汤。"},
        ),
        "persona": "你是摇着老式爆米花机的大爷,开炉前总要喊一声捂耳朵。",
        "fixed": {"greet": "刚爆的,脆着呢。", "deal": "拿好,别撒了。",
                  "soldout": "这一炉没了。", "broke": "钱不够。"},
    },
    "takoyaki": {
        "name": "章鱼烧", "who": "卖章鱼烧的", "pron": "他",
        "months": tuple(range(1, 13)), "hours": (11, 20), "rain_ok": True,
        "arrive": "楼下有章鱼烧的摊子支起来了。",
        "goods": (
            {"id": "takoyaki", "name": "章鱼烧", "kind": "snack", "unit": "盒",
             "price": 8, "stock": (3, 6), "satiety": 12.0, "energy": 0.05},
            {"id": "nori", "name": "紫菜", "kind": "ingredient", "ingredient": vendor_id("紫菜"), "unit": "份",
             "price": 8, "stock": (2, 3), "note": "紫菜 — 和鸡蛋一起煮汤。"},
        ),
        "persona": "你是用小签子翻章鱼烧的摊主,说话带一点关西腔的利落。",
        "fixed": {"greet": "现烤的,等一小会儿就好。", "deal": "里面烫,咬小口。",
                  "soldout": "面糊用完了。", "broke": "差一点。"},
    },
    "icecream": {
        "name": "冰淇淋车", "who": "冰淇淋车", "pron": "他",
        "months": (5, 6, 7, 8, 9), "hours": (12, 20), "rain_ok": False,
        "arrive": "楼下响起了冰淇淋车的音乐。",
        "goods": (
            {"id": "vanilla_ice", "name": "香草冰淇淋", "kind": "snack", "unit": "个",
             "price": 5, "stock": (3, 6), "satiety": 4.0, "energy": 0.03, "aliases": ("香草的",)},
            {"id": "matcha_ice", "name": "抹茶冰淇淋", "kind": "snack", "unit": "个",
             "price": 6, "stock": (2, 5), "satiety": 4.0, "energy": 0.03, "aliases": ("抹茶的",)},
            {"id": "strawberry_ice", "name": "草莓冰淇淋", "kind": "snack", "unit": "个",
             "price": 6, "stock": (2, 5), "satiety": 4.0, "energy": 0.03},
            {"id": "condensed_milk", "name": "炼乳", "kind": "ingredient", "ingredient": vendor_id("炼乳"), "unit": "份",
             "price": 9, "stock": (1, 3), "note": "炼乳 — 蘸馒头,或者加一勺进牛奶里。"},
        ),
        "persona": "你是开冰淇淋车的姐姐,车上放着叮叮当当的音乐,催人趁没化快吃。",
        "fixed": {"greet": "想要哪个口味?", "deal": "快吃,要化了。",
                  "soldout": "这个口味没了。", "broke": "不够哦。"},
    },
    "florist": {
        "name": "卖花", "who": "卖花的", "pron": "她",
        "months": tuple(range(1, 13)), "hours": (9, 18), "rain_ok": True,
        "arrive": "楼下来了一辆卖花的小车。",
        "flowers_per_visit": (2, 3), "flower_stock": (2, 3),
        "goods": (
            {"id": "osmanthus", "name": "干桂花", "kind": "ingredient", "ingredient": vendor_id("干桂花"), "unit": "份",
             "price": 10, "stock": (1, 3), "note": "干桂花 — 和冰糖一起泡水,或者撒在甜汤上。"},
        ),
        "persona": "你是推着小花车的花店姑娘,说话轻,会顺口教人怎么养花。",
        "fixed": {"greet": "都是早上刚剪的。", "deal": "回去剪一下根,能多开两天。",
                  "soldout": "今天的花卖完了。", "broke": "钱不够。"},
    },
}

# Every fifth order from the same vendor comes with one of these, in turn (free, into the fridge).
REGULAR_GIFTS: tuple[dict, ...] = (
    {"item": "scallion", "text": "{who}多塞给你一根葱。"},
    {"item": "lemon", "text": "{who}多塞给你一个柠檬。"},
    {"item": "apple", "text": "{who}多塞给你一个苹果。"},
    {"item": "tomato", "text": "{who}多塞给你一个番茄。"},
)
