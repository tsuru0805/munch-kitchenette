# What the upgrade changed

<a id="upgrade-0.2.1"></a>
### From 0.2.0 to 0.2.1

**Run these**, in the directory you cloned into:

```sh
git pull
source .venv/bin/activate          # your own environment; Windows: .venv\Scripts\activate
pip install -U .                   # installed with -e before? do it the same way again: pip install -e .
```

Then restart `kitchenette serve`: stop it (Ctrl-C in its window, or however you keep it running) and start it again. Once the new one runs, `GET /api/about` answers `"version": "0.2.1"`. Coming from a version before 0.2.0? The same commands take you straight to 0.2.1; read [the 0.2.0 section](#upgrade-steps) below too.

**Your data needs nothing from you.** The database is the one you have. On start 0.2.1 adds two columns to the notes table (and, the first time the page buys what a recipe lacks, a table for those receipts); nothing in it is deleted or changed, and starting again adds nothing more. What was made under 0.2.0 reads back the way it was made:

- A pot cooked by a public recipe keeps the version it followed. 0.2.1 corrects 171 of the 374 entries of the recipe index and ships the earlier index with it (`src/kitchenette/data/history/`), so an old pot and its settled card read the recipe as it was then; a new pot follows the corrected one.
- An ingredient bought under a name the index no longer uses (泡好的粉丝, now 粉丝, and a few more) counts as the thing it is called now.
- A page deleted from the role's book still answers for the pot that followed it.
- A public recipe collected into the role's book shows the entry as it is now, the same one cooking by it follows.
- A washing started under 0.2.0 carries on, with the plates it was going to break; settled cards, dislikes, the vendor's orders, the jars and a reply sent again to `/api/inline` read as before; notes your webhook had not taken yet are sent, once.

**What you will see change:**

- "Today you could try" lists at most three dishes: as a rule two the fridge can make now and one that is a thing short.
- The settled card is laid out anew: the cook inside the card on the left, holding the dish; the outcome, proficiency and mishap on the right, one line each under a small title.
- Washing up plays in the chat, on a washing card; the plates tab of the kitchen page keeps only the cook loading the dishwasher.
- The vendor is a new picture (a straw-hat peddler with a wooden cart), and the vendor tab plays each visit in order: the cart coming in, the cook buying, the cart going away.
- The kitchen page: dish-book pictures stand in with the fourteen pixel dishes until drawn; dislikes are added and taken off one at a time; "替他买齐" buys only what that recipe still lacks.
- Which plate breaks is drawn from private randomness when the washing starts, so nothing public tells it beforehand.
- A kitchen page already open in a browser needs one refresh.

**If you built on its interfaces:**

- The card's string `settleTier` still works when you override it (the tier on one line, as in 0.2.0); the new card uses `settleTierName`, `settleToNext` and friends ([`web/README.md`](../web/README.md)).
- `POST /api/recipes/buy_missing` is new and needs `op_id`: one per buying, the same for a retry of it ([API.md](API.md)).
- `POST /api/inline` receipts carry `attachments`: empty for most markers; a `[刷盘子]` that started a washing carries the washing card `{kind: "kitchen_washing", job_id, …}`. A chat client that ignores it works as before.
- The washing card is a new element, `<kitchenette-washing-card>`, registered by the same script as the cooking card (`web/dist/kitchenette-cooking-card.js`). To show it in your chat, serve the new script (copied it somewhere? copy it again) and wire it as [CONNECT.md](CONNECT.md) ("Bracket markers") and [`web/README.md`](../web/README.md#the-washing-card) say; it reads the new `GET /api/dishes/jobs/<id>`.
- `POST /api/jars/feed` now requires `key` (400 without it), one per feeding; the kitchen page sends it.
- Dislikes: every answer carries the list's `version`; `POST /api/prefs/dislike` and `DELETE /api/prefs/dislike/<item>` are new. `PUT /api/prefs` still replaces the whole list as in 0.2.0 (now outdated); with `version` it only does so if the list has not changed.
- `GET /api/vendor`: each order in `mine` also has `item_id` and `kind`; `ended` carries a visit that ended within the last two minutes. The settled card's `proficiency` gains `next_tier` and `tier_from`.
- A notifier of your own: return from one delivery within 5 minutes ([HOOKS.md](HOOKS.md)); two pushes at once never send the same note.

<a id="upgrade-steps"></a>
### Installed a version before 0.2.0? How that upgrade goes

**Run these**, in the directory you cloned into:

```sh
git pull
source .venv/bin/activate          # your own environment; Windows: .venv\Scripts\activate
pip install .                      # installed with -e before? do it the same way again: pip install -e .
```

Then stop the `kitchenette serve` that is running (Ctrl-C in its window, or however you keep it running) and start it again.

**What happens by itself:**

- The database is the one you have. On start the kitchen only adds the new tables and the few new columns; nothing already in it is deleted or changed.
- The ten things that are on by default are on as soon as it starts. To leave one out, set it to `false` under `[play]` in `kitchenette.toml` (names in [`examples/play.toml`](../examples/play.toml)).
- The kitchen page has the new picture. A page that was already open in a browser needs one refresh.

**What you do by hand, only if it applies to you:**

- If you copied the kitchen's rules into your model's prompt by hand, take the new ones from `GET /api/play/teaching` and paste them in. If the model reaches the kitchen through the tools in the normal way, there is nothing to do: those sentences come with the cooking tool's description.
- The vendor is off by default. To turn it on, set `vendor = true` under `[play]` and restart; then give it money: your own wallet (`[vendor] wallet_url`), or the built-in ledger — once the vendor is on, the page shows a 零花钱 (pocket money) tab to give from. See [the wallet paragraph](#wallet-en) below.

### What it adds

The upgrade adds seventeen things, each with a switch of its own under `[play]` (ten on, seven off by default; see [`examples/play.toml`](../examples/play.toml)). A switch that is off means the thing is not installed: its markers are plain text, nothing teaches it, the page hides it, and asking for it directly answers that it is off. Turning one off deletes nothing. After installing the upgrade, the ten that are on by default are on straight away. With all seventeen off, the tools, sentences and receipts the role reads are word for word what they were before (the tests from before the upgrade run that way); the REST answers only gain a few fields (for example `features` in `GET /api/about`) and a few new endpoints.

| | Before | Now |
|---|---|---|
| Knowing what to cook | Up to the role | 300-odd home dishes to look up; up to three suggestions in the kitchen status |
| Opening a pot | Dish, minutes, ingredients, method | The same, plus an optional recipe id |
| Buying | One coupon, up to five kinds | The same; buying "by recipe" gets everything that recipe lacks for one coupon |
| The cooking card when done | "Served" | It turns into a settled card: the cook inside it on the left holding the dish (14 kinds of dish picture), lines for the outcome, proficiency and the mishap on the right, and a stamp when there is one |
| Dishes made | Only in the recent list | One page each in the dish book |
| The role's own dishes | Nowhere | Its own recipe book; a page can be shared as a code |
| Tools | cook / status / cancel / toss | One more: `kitchen_recipes` (read only) |
| Markers | buy / eat / snack / toss | More, for the things switched on |

<a id="wallet-en"></a>
The four optional hooks — a wallet, a small model playing the vendor, a weather reader and a dish-picture drawer — are described in the Chinese half below (the table "四个可以不配的口子"); each has a fallback when left empty: the built-in ledger, fixed lines, hour-and-season only, the fourteen pixel dishes as placeholders. The wallet is either your own pocket-money system over HTTP (`[vendor] wallet_url`, plus `wallet_token` sent as a bearer token; the four endpoints it needs are in "接你自家的钱包" below) or a `"package.module:name"` object (`wallet_provider`); the others are `"package.module:name"` settings. Without a wallet the built-in ledger starts at 0 and only the human puts money in, from the page; the role is told each time. The recipes come from HowToCook (Unlicense), commit `58c1b9a`; `tools/build_recipe_index.py` rebuilds the index byte for byte.

---

# 中文：这次升级改了什么

<a id="upgrade-0.2.1-zh"></a>
### 从 0.2.0 升到 0.2.1

**照着敲**，在你当初 clone 下来的那个目录里：

```sh
git pull
source .venv/bin/activate          # 你自己的环境；Windows 用: .venv\Scripts\activate
pip install -U .                   # 当初用 -e 装的，就照原样再装一遍：pip install -e .
```

然后重启 `kitchenette serve`：把正在跑的停掉（在它的窗口里按 Ctrl-C，或者用你平时让它常驻的那种方式停），再启动一次。新的跑起来以后，`GET /api/about` 回的是 `"version": "0.2.1"`。还在用 0.2.0 之前的版本？同样这几行就直接到 0.2.1，下面 [0.2.0 那一节](#upgrade-steps-zh) 也看一下。

**数据不用你动。** 数据库还是原来那个。启动时 0.2.1 只给通知表加两个列（页面第一次「替他买齐」时，再建一张记回执的表）；原有的数据一条不删、一条不改，再启动多少次也不会再加东西。0.2.0 时留下的东西，读出来还是当时的样子：

- 照公共食谱做的锅，记着它照的是哪一版。0.2.1 改正了食谱索引 374 道里的 171 道，旧的索引随包带着（`src/kitchenette/data/history/`），所以旧锅和它的结算卡读到的还是当时那一版；新开的锅照改正后的做。
- 用索引现在不用的旧名字买进冰箱的料（泡好的粉丝，现在叫粉丝，还有几样），按它现在的名字算数。
- 从他食谱本里删掉的那一页，照它做过的那一锅照样查得到。
- 他收藏进食谱本的公共食谱，显示的是这道菜现在的样子，和照它开锅时用的是同一版。
- 0.2.0 时开始的刷盘子接着刷，当时定好要碎的那只照样碎；结算卡、不让推的食材、小贩的单、罐子、再送一次给 `/api/inline` 的回复都和以前一样；你的 webhook 当时没收下的通知，会补发一次，只发一次。

**看得见的变化：**

- 「今天可以试试」最多三道：一般是两道冰箱里的料够的，加一道还差一样的。
- 结算卡换了版面：小厨师在卡片里面的左边举着这道菜，右边一行一项写成色、熟练度、小意外，左边带小标题。
- 刷盘子改在聊天里的刷盘子卡上放；厨房页的盘子那一页只留小厨师往洗碗机里放盘子。
- 流动小贩换了新画（草帽货郎和一辆木头小推车），小贩那一页按顺序放每一趟：推车进来、小厨师买东西、推车离开。
- 厨房页：图鉴还没画图的菜，用十四类像素小菜里对应的一样占位；不让推的食材一样一样加、一样一样撤；「替他买齐」只买这份食谱眼下还缺的。
- 哪只盘子会碎，在开始刷的时候用私有的随机数定，外面看不出来。
- 浏览器里本来就开着的厨房页，刷新一下。

**如果你接过它的接口：**

- 卡片文字里的 `settleTier` 照样可以覆盖（覆盖了就照 0.2.0 那样把档位写成一行）；新卡用的是 `settleTierName`、`settleToNext` 等（见 [`web/README.md`](../web/README.md)）。
- 新增 `POST /api/recipes/buy_missing`，必须带 `op_id`：一次买齐一个，重试同一次就带同一个（见 [API.md](API.md)）。
- `POST /api/inline` 的回执多了 `attachments`：多数标签是空的；开始了一趟刷盘子的 `[刷盘子]` 带一张刷盘子卡 `{kind: "kitchen_washing", job_id, …}`。不认这个字段的聊天客户端照旧能用。
- 刷盘子卡是新元素 `<kitchenette-washing-card>`，和做饭卡由同一个脚本注册（`web/dist/kitchenette-cooking-card.js`）。想在聊天里显示，换上新的脚本（你复制到别处过的话，再复制一次），再照 [CONNECT.md](CONNECT.md)「方括号标签」一节和 [`web/README.md`](../web/README.md#刷盘子卡) 接上；它读的是新增的 `GET /api/dishes/jobs/<id>`。
- `POST /api/jars/feed` 现在必须带 `key`（不带回 400），喂一次一个；厨房页自己会带。
- 不让推的食材：每个回答都带这张单子的 `version`；新增 `POST /api/prefs/dislike` 和 `DELETE /api/prefs/dislike/<食材>`。`PUT /api/prefs` 照 0.2.0 那样整张替换仍然可以（已不推荐）；带上 `version` 时，单子没被改过才替换。
- `GET /api/vendor`：`mine` 里每一单多了 `item_id` 和 `kind`；多了 `ended`，是两分钟内刚走的那一趟。结算卡的 `proficiency` 多了 `next_tier` 和 `tier_from`。
- 自己写的通知发送器：一次发送请在 5 分钟内返回（见 [HOOKS.md](HOOKS.md)）；两次推送同时进行时，同一条通知不会发两遍。

<a id="upgrade-steps-zh"></a>
### 装的是 0.2.0 之前的版本，怎么升级

**照着敲**，在你当初 clone 下来的那个目录里：

```sh
git pull
source .venv/bin/activate          # 你自己的环境；Windows 用: .venv\Scripts\activate
pip install .                      # 当初用 -e 装的，就照原样再装一遍：pip install -e .
```

然后把正在跑的 `kitchenette serve` 停掉（在它的窗口里按 Ctrl-C，或者用你平时让它常驻的那种方式停），再启动一次。

**会自己发生的：**

- 数据库还是原来那个。启动时只加新的表和几个新的列，原有的数据一条不删、一条不改。
- 默认开着的十样，一启动就开着。哪样不想要，就在 `kitchenette.toml` 的 `[play]` 里把它改成 `false`（名字见 [`examples/play.toml`](../examples/play.toml)）。
- 网页厨房换成了新画面。浏览器里本来就开着的旧页面，刷新一下。

**要自己动手的（用不上的跳过）：**

- 如果你是把厨房的规则说明手动复制进小机提示词里的，从 `GET /api/play/teaching` 取新的那段，贴进去。走正常工具调用的不用管：这些话跟着开锅工具的说明一起过去。
- 流动小贩默认关着。要开，把 `[play]` 里的 `vendor` 改成 `true`，重启。他要有钱才买得了东西：接你们自家的钱包（`[vendor] wallet_url`），或者用自带的小账本——开了以后页面上会多出「零花钱」，从那里给。见下面[「接你自家的钱包」](#your-own-wallet)。

### 升级前后对比

|  | 以前 | 现在 |
|---|---|---|
| 他知道能做啥菜 | 全凭自己瞎想 | 三百多道的速查表；看厨房时还会推荐最多三道 |
| 开锅 | 菜名、分钟、用料、做法 | 一模一样，多了一个可以不填的食谱编号 |
| 买菜 | 一张券最多买五样 | 一样；但照某份食谱买时，缺的料能一次买齐 |
| 做完的做饭卡 | 一个字块和干巴巴的「出锅了」 | 换成结算卡：小厨师在卡片里面的左边举着这道菜（十四类菜的小图），右边写成色、熟练度、小意外，有印章时盖一枚 |
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
| 图鉴的图 | `[art] dish_provider` | 每页用十四类像素小菜里对应的一样占位（和结算卡上举着的是同一套） | `draw(name, ingredients, method) -> PNG 字节`。厨房每分钟的那一拍画一张，画坏了记下原因；重画是新一版，旧图留着。 |

<a id="your-own-wallet"></a>
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
