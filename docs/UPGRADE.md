# What the upgrade changed

The upgrade adds seventeen things, each with a switch of its own under `[play]` (ten on, seven off by default; see [`examples/play.toml`](../examples/play.toml)). A switch that is off means the thing is not installed: its markers are plain text, nothing teaches it, the page hides it, and asking for it directly answers that it is off. Turning one off deletes nothing. After installing the upgrade, the ten that are on by default are on straight away. With all seventeen off, the tools, sentences and receipts the role reads are word for word what they were before (the tests from before the upgrade run that way); the REST answers only gain a few fields (for example `features` in `GET /api/about`) and a few new endpoints.

| | Before | Now |
|---|---|---|
| Knowing what to cook | Up to the role | 300-odd home dishes to look up; three suggestions in the kitchen status |
| Opening a pot | Dish, minutes, ingredients, method | The same, plus an optional recipe id |
| Buying | One coupon, up to five kinds | The same; buying "by recipe" gets everything that recipe lacks for one coupon |
| The cooking card when done | "Served" | The cook stays on the card holding the dish (14 kinds of dish picture), with lines for proficiency, the mishap and stamps |
| Dishes made | Only in the recent list | One page each in the dish book |
| The role's own dishes | Nowhere | Its own recipe book; a page can be shared as a code |
| Tools | cook / status / cancel / toss | One more: `kitchen_recipes` (read only) |
| Markers | buy / eat / snack / toss | More, for the things switched on |

The four optional hooks — a wallet, a small model playing the vendor, a weather reader and a dish-picture drawer — are described in the Chinese half below (the table "四个可以不配的口子"); each has a fallback when left empty: the built-in ledger, fixed lines, hour-and-season only, placeholders. The wallet is either your own pocket-money system over HTTP (`[vendor] wallet_url`, plus `wallet_token` sent as a bearer token; the four endpoints it needs are in "接你自家的钱包" below) or a `"package.module:name"` object (`wallet_provider`); the others are `"package.module:name"` settings. Without a wallet the built-in ledger starts at 0 and only the human puts money in, from the page; the role is told each time. The recipes come from HowToCook (Unlicense), commit `58c1b9a`; `tools/build_recipe_index.py` rebuilds the index byte for byte.

---

# 中文：这次升级改了什么

### 升级前后对比

|  | 以前 | 现在 |
|---|---|---|
| 他知道能做啥菜 | 全凭自己瞎想 | 三百多道的速查表；看厨房时还会推荐三道 |
| 开锅 | 菜名、分钟、用料、做法 | 一模一样，多了一个可以不填的食谱编号 |
| 买菜 | 一张券最多买五样 | 一样；但照某份食谱买时，缺的料能一次买齐 |
| 做完的做饭卡 | 一个字块和干巴巴的「出锅了」 | 小厨师留在卡上举着这道菜（十四类菜的小图），下面写熟练度、小意外、印章 |
| 做过的菜 | 只在最近出锅的记录里飘过 | 进图鉴，一道菜专属一页 |
| 他自己的菜 | 没地方记 | 有自己的食谱本，还能用一串码分享给别人 |
| 工具 | 开锅 / 看厨房 / 关火 / 扔东西 | 只多了一件「翻食谱」 |
| 标签 | 买菜 / 吃 / 零食 / 扔掉 | 随着你开的玩法，多出收藏、记菜、札记等 |
| 挑着装 | 只有体力、饱食度两个开关 | 十七样新玩法，各带一个独立开关 |

> 即使是不带食谱编号的“自由开锅”，开锅时的回话和扣料规则，依然和升级前一模一样。十七样全部关掉时，他看到的工具、文字、回执和升级前逐字不变（升级前的全部测试就是在全关的状态下跑的）；接口只多出几个字段（比如 `GET /api/about` 里的 `features`）和几条新接口。

### 开关在哪

**升级后默认就开着这十样**：公共食谱、今天可以试试、照谱开锅、他的食谱本、熟练度、小意外、新菜加成、结算卡、图鉴、厨房成就。不想要哪样就在配置里关掉。


`kitchenette.toml` 的 `[play]` 一段，一行一个，名字和默认值见 [`examples/play.toml`](../examples/play.toml)；各样用到的数在 `[recipes]`、`[dishwash]`、`[jars]`、`[vendor]` 里（见 [`CONFIG.md`](CONFIG.md)）。页面通过 `GET /api/features` 知道哪些开着，关着的玩法没有入口。

### 四个可以不配的口子

都是填一个 `"包.模块:名字"`，和现有的 `[art] provider` 一样：

| 口子 | 配置 | 不配会怎样 | 要写什么 |
|---|---|---|---|
| 钱包（小贩扣零花钱） | `[vendor] wallet_url`（或 `wallet_provider`） | 用厨房库里自带的小账本：从 0 开始，不会自己入账；零花钱由你在页面上给（小贩那页和手边下面的「零花钱」），给多少、什么时候给都由你，给了他下一轮会知道 | `wallet_url`：你们自家零花钱系统的地址，接口约定见下面「接你自家的钱包」。`wallet_provider`：一个 Python 对象，带四个方法：`debit(order_id, who, amount, note)` 回 `vendor.Result(status, balance)`，status 是 `ok` / `insufficient` / `conflict` / `unavailable`（确定没扣）/ `unknown`（说不清）；`lookup(order_id, who, amount)` 回 `charged` / `absent` / `voided` / `unknown`；`void(order_id)` 回 `ok` / `absent`；`balance(who)` 回整数或 None。同一个 order_id 重复扣只能扣一次。 |
| 小贩说话的模型 | `[vendor] talk_provider` | 小贩只说固定台词 | `say(system, history, line) -> str`：system 是这位小贩的设定，history 是这一趟里给他看过的来回，line 是这一轮要回的话。回的那句会先过检查（不许有数字、不许白给、不许许诺、不许超长），不过就换成固定台词。 |
| 天气 | `[recipes] weather_provider` | 推荐只看钟点和季节；冰淇淋车下雨也可能来 | `read() -> {"rain": bool 或 None, "temp_c": 数 或 None}` |
| 图鉴的图 | `[art] dish_provider` | 每页用占位图 | `draw(name, ingredients, method) -> PNG 字节`。厨房每分钟的那一拍画一张，画坏了记下原因；重画是新一版，旧图留着。 |

#### 接你自家的钱包

`[vendor] wallet_url` 填你们自家零花钱系统的地址（`wallet_token` 填口令，会以 `Authorization: Bearer …` 发过去），厨房就只从那里扣钱、退钱、查余额，不用自带小账本。那边要有这四个口子：

| 请求 | 回答 |
|---|---|
| `POST {url}/debit` `{order_id, who, amount, note}` | 200 / 201 `{balance}`：扣成了（同一个 `order_id` 再来一次，回同样的结果、只扣一次）；402 `{balance}`：钱不够，什么都没写；409：这个 `order_id` 用在了别的人或别的金额上，什么都没写 |
| `GET {url}/orders/{order_id}` | 200 `{found: false}`，或 `{found: true, status: "active" \| "voided"}` |
| `POST {url}/orders/{order_id}/void` | 200（已经作废过也回 200）；404：没有这一笔 |
| `GET {url}/balance?who=` | 200 `{balance}` |

地址用 `http://` 时口令是明文发出去的，只在本机或可信的内网里这样用，别处请用 `https://`。厨房不跟随跳转（3xx 不会把口令带去别的地址，按「说不清」处理）。

请求根本没发出去（连不上）算「没扣」；超时、5xx、3xx 算「说不清」，这一单就停在「扣款中」，每分钟按 `order_id` 去查，查清之前不再扣、不宣告失败、不放掉占着的货。

「他睡着时小贩不留话」用的是现有的睡眠口子（`[notify] respect_sleep` 与 `sleep.set_asleep_hook`，见 [`HOOKS.md`](HOOKS.md)）；没接就当他一直醒着。

### 新标签一览

只在那一样开着、且方括号标签接好时才认、才教（教的句子会接在开锅工具的说明后面，也可以从 `GET /api/play/teaching` 取来放进你自己的提示词）。

| 标签 | 属于 |
|---|---|
| `[收藏 菜名或编号]`、`[记菜 菜名 用料… 做法 分钟]`（可加 `改自 编号`、`\| 一句话`） | 他的食谱本（收藏还要公共食谱开着） |
| `[买菜 照 编号]` | 照谱开锅 |
| `[札记 编号 一句话]` | 试菜札记 |
| `[接单 菜名]`、`[接单 菜名 想换的做法]` | 点菜 |
| `[配一桌 编号 编号 … \| 一句话]` | 一桌菜单 |
| `[出码 编号]` | 食谱码 |
| `[问小贩 …]`、`[买 东西 数量]`、`[送花 一句话]`、`[想要花 花名]` | 流动小贩 |
| `[刷盘子]` | 刷盘子 |
| `[封罐 食材 糖或盐 \| 纸条]` | 窗台密封罐（取用走现有的 `[零食 名字]`） |

### 页面用的新接口

见 [`API.md`](API.md) 的「这次升级」一节。

### 食谱从哪来

[Anduin2017/HowToCook](https://github.com/Anduin2017/HowToCook)（Unlicense）提交 `58c1b9a`，由 [`tools/build_recipe_index.py`](../tools/build_recipe_index.py) 整理成 `src/kitchenette/data/howtocook-58c1b9a.index.json`：每道只留菜名、主料、可选料、做法、分钟、分类和来源，不带步骤。做法和分钟是整理时估的。同一个提交重跑脚本，得到的文件逐字相同。冰箱目录以外的东西有三种去处：调料与灶台边的（盐、葱姜蒜、酱油……）算常备；其余的食谱料公共食谱开着时超市照常卖（照谱买齐和 `[买菜 名字]` 都认，只是不列在买菜的单子上），免得哪道菜永远做不成；只有小贩自己带的那几样（山楂、山药、栗子、腐竹、红豆、紫菜、炼乳、干桂花）是「小贩专供」，超市不卖。
