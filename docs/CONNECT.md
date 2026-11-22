# Connecting your companion

There are three things to wire up. Only the first is required.

1. **Tools**: how the model acts in the kitchen.
2. **Notes**: how it learns that something happened while it was not looking.
3. **Status lines**: optional facts to carry into each turn.

## 1. Tools (MCP)

Point any MCP-capable client at `http://127.0.0.1:8765/mcp` (Streamable
HTTP). If `server.token` is set, send `Authorization: Bearer <token>`.

| Tool | What it does |
|---|---|
| `kitchen_cook` | Open a pot: dish name, minutes (real time), ingredients from the fridge, optional method. |
| `kitchen_status` | What is on the fire, what was served lately, the fridge, coupons. |
| `kitchen_cancel` | Turn the heat off under a pot. Ingredients are not returned. |
| `kitchen_toss` | Throw something out, effective immediately. |
| `kitchen_buy` | Buy up to five kinds with one coupon. |
| `eat` | Eat a meal: something on the menu, a pot just served, or raw from the fridge. |
| `read_menu` | The menu, the snack shelf and the fridge in one read. |
| `snack_eat` | One serving from the snack shelf. |
| `kitchen_notes` | Take the notes waiting for the role (see below). |

### In a specific client

Only what was checked against each client's own current documentation is
written here; follow the links for the details.

**Claude Code** ([docs](https://code.claude.com/docs/en/mcp)). Add the server
as a remote HTTP server, with the token as a header if you set one:

```sh
claude mcp add --transport http kitchenette http://127.0.0.1:8765/mcp
# with a token:
claude mcp add --transport http kitchenette http://127.0.0.1:8765/mcp \
  --header "Authorization: Bearer your-token"
```

`--scope user` makes it available in all your projects (the default, `local`,
is the current project only). `claude mcp list` shows whether it connected;
inside Claude Code, `/mcp` shows the same.

**claude.ai and Claude Desktop: custom connectors**
([help article](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)).
On Pro and Max: **Customize > Connectors**, then **+ Add**, then **Add custom
connector**, and enter the server's `/mcp` address. A token goes under
**Request headers** (`Authorization: Bearer your-token`). Two things from that
article decide whether this works for you:

- the connection is made from Anthropic's servers, not from your computer, so
  the address must be reachable over the public internet.
  `http://127.0.0.1:8765` will not do; put the server behind a public HTTPS
  address (see [INSTALL.md](INSTALL.md)) and set `server.token`;
- on Team and Enterprise plans an owner adds the connector under
  **Organization settings > Connectors**.

**Anything else.** If it speaks MCP over Streamable HTTP, give it the `/mcp`
address and the bearer header. How that is entered differs per client: please
check that client's own MCP documentation.

### Who is who

Every tool takes an optional `who`. Leave it out and the role is
`roles.default`. One server can keep house for several companions: give each
its own id and they never see each other's fridge, coupons, menu or stamina.

A successful `kitchen_cook` also returns a card in `structuredContent`:

```json
{"attachments": [{"kind": "kitchen_cooking", "session_id": "…", "who": "companion",
                  "dish": "番茄炒蛋", "note": "", "duration_seconds": 600,
                  "started_at": 1794467301.27, "method": "stirfry"}]}
```

A chat page can draw a countdown from it and later ask
`GET /api/kitchen?session_id=…` whether the pot was served or cancelled.

Not using MCP? `kitchenette.tools.call(name, args, who)` is the same thing as
a Python function, and `tools.schemas()` returns the JSON schemas to hand to
your model's tool-calling API. See `examples/mcp_client.py` for a client.

### The wording

Tool descriptions and receipts are in Chinese and written as plain statements
of fact. They live in one file, `src/kitchenette/texts.py`.

**If you only connect MCP, nothing more is needed.** Nine sentences come in
two versions. One tells the role to act by writing a bracket line in its
reply ("吃完哪道，回复里单独一行写 [吃 菜名]"); the other names the tool instead
("吃完哪道，用 eat 写上菜名"). Out of the box (`inline.enabled = "auto"`) the
kitchen uses the tool version, and changes to the bracket version by itself
the first time a reply is really sent to `POST /api/inline` (see "Bracket
markers" below). So a model that can only call tools is never told to write
a line that does nothing. To pin it either way:

```toml
[inline]
enabled = true     # always speak of bracket lines
# enabled = false  # always name the tools; /api/inline is refused
```

One more sentence follows a setting. The `kitchen_cook` description ends its
line about serving with "到点会叫醒你一次" when notes are pushed (`notify.mode`
`webhook` or `both`), since then something really does wake the model. In
`queue` mode nothing wakes it, so the sentence says "到点会留一句话等你来取"
instead, and in `none` mode it is left out.

## Bracket markers: acting by writing a line (automatic by default)

Instead of calling tools, a model can act by writing a line of its own:

```
[买菜 番茄 鸡蛋]
[吃 番茄炒蛋]
[零食 拿铁]
[扔掉 坏了的]
```

Send each reply to `POST /api/inline` with a `message_id`. You get the reply
with those lines removed (for display) and one receipt per marker; pass the
receipts' `rendered` text to the model with its next turn. Sending the same
`message_id` again repeats nothing. `examples/inline_markers.py` runs it.

A receipt can carry a card, the way `kitchen_cook` does. With plates switched
on, a `[刷盘子]` that started a washing answers:

```json
{"marker": "刷盘子", "args": "", "ok": true, "text": "开始刷了:3 只盘子,大概 6 分钟。", "rendered": "…",
 "attachments": [{"kind": "kitchen_washing", "job_id": "…", "who": "companion",
                  "n": 3, "per_s": 120.0, "started_at": 1794467301.27}]}
```

A chat page can show it as the washing card (`<kitchenette-washing-card>`, see
[`web/README.md`](../web/README.md#the-washing-card)), which reads
`GET /api/dishes/jobs/<job_id>` while the washing goes on to learn which plates
broke. Every other marker, and a `[刷盘子]` that started nothing (an empty sink,
a washing already going on), has an empty `attachments`.

`inline.enabled` says whether you do this. It takes three values:

| Value | The kitchen's sentences | `/api/inline` |
|---|---|---|
| `"auto"` (default) | point at the tools until your chat program has really sent a reply to `/api/inline`; from that first reply on, they speak of the lines | works from the start |
| `true` | tell the role to write these lines | works |
| `false` | point at the tools instead (`eat`, `snack_eat`, `kitchen_buy`, `kitchen_toss`) | answers 409 |

With `"auto"` nothing misleads the model before the wiring exists, and
nothing needs changing once it does: send the first reply and the wording
follows. The kitchen remembers in its database that a reply has arrived, so
it survives restarts.

## 2. Notes: telling the role what happened

A pot comes due, the human buys groceries, a snack turns out to have a worm
in it, hunger sets in: each becomes a note, a ready-made sentence. Choose how
notes reach the model with `notify.mode`.

**`queue` (default).** Notes wait on the server. Take them right before each
turn and put them in front of the model, or let the model call
`kitchen_notes` itself:

```sh
curl -X POST localhost:8765/api/notes/take -H 'content-type: application/json' -d '{}'
# {"notes": [...], "text": "【厨房·非用户发言】你 16:19 下锅的『番茄炒蛋』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。"}
```

Each note is handed over once. `examples/notify_queue.py` is a runnable version.

**`webhook`.** The server POSTs notes to `notify.webhook_url` as they appear,
so your side can start a turn for the model: "your dish is ready" then arrives
on time even when nobody is chatting. `examples/notify_webhook_receiver.py`
is a receiver to start from. Quiet hours and "do not wake while asleep" apply
to this mode; see [HOOKS.md](HOOKS.md).

**`both`** pushes and also lets the notes be taken: whichever happens first
hands a note over, and it is not handed over a second time. **`none`** records
nothing.

A pot that comes due gets its note at that moment, not at the next scan: the
kitchen settles it whenever the role calls a tool or a page reads, so
`kitchen_status` showing a dish as served and `kitchen_notes` being empty
cannot happen together.

Things of the same kind that pile up before the role hears of them are told
in one sentence: three dishes put on the menu in a row arrive as
"…刚在菜单上挂了 3 道:『…』、『…』、『…』", not as three notes. A new note starts
once the previous one was taken or pushed.

The kinds of note: `kitchen.served`, `worm.eaten`, `hungry`, `fridge.bought`,
`fridge.coupon`, `snack.fed`, `potion.fed`, `menu.posted`, `menu.fed`.

## 3. Status lines (optional)

`GET /api/turn-lines?who=…` returns facts that stay true for a while, meant to
be shown to the model with every turn while they last:

```json
{"kitchen": "【厨房·非用户发言】你 17:20 吃了坏掉的『生菜汤』,现在有点晕乎乎的,大约 19:50 缓过来。",
 "body": "[你的身体 17:25 | 体力 0.62]"}
```

`kitchen` is null when there is nothing to say. The dizzy line is worded from
its end time, so it stays byte-identical from turn to turn (kind to prompt
caches).

## Stamina: telling the kitchen what the role did

Stamina goes down with work and up with rest. The kitchen's own tools are
settled as they are called. For everything else the model does (its other
tools), report each finished round:

```sh
curl -X POST localhost:8765/api/rounds/settle -H 'content-type: application/json' \
     -d '{"round_id": "msg_123", "tools": ["web_search", "write_diary"]}'
# {"stamina": 0.64, "receipts": [{"kind": "coupon", "ok": true, "text": "得了一张买菜券(现在 1/3)。"}], "duplicate": false}
```

`tools` lists the tools that succeeded in that round. Which of them are work,
which are rest and which earn a grocery coupon is up to you: see
[CONFIG.md](CONFIG.md). Out of the box no tool earns a coupon (the example
above assumes `write_diary` is listed under `[coupons.earn]`); until you
configure that, coupons come only from the human. `round_id` makes a repeated report harmless. Hand the
`receipts` to the model with its next turn. Not reporting rounds is fine too:
then only kitchen activity moves stamina.

## The stamina potion

A potion is a menu item the human puts up, with a number: how much stamina it
restores. It is not a meal.

**Putting one up, in one step** (use this from a page: it either does both
things or neither):

```sh
curl -X POST localhost:8765/api/potions/hang -H 'content-type: application/json' \
     -d '{"who": "companion", "pct": 30, "memo": "慢慢喝"}'
# {"ok": true, "row": {"id": "…", "dish": "精力补充药剂", "note": "回 30% 体力 · 慢慢喝", …}, "potion": {"pct": 30, …}}
```

**Or in two steps**, which is what the one step does for you:

1. put a row on the menu whose dish is exactly `精力补充药剂`:
   `POST /api/menu {"dish": "精力补充药剂", "by": "human", "for_who": "companion"}` → the row's `id`;
2. record the amount for that row:
   `POST /api/potions {"who": "companion", "menu_row_id": "<that id>", "pct": 30, "memo": "慢慢喝"}`.

A row without step 2 cannot be drunk, and step 2 is refused for a row that is
not a potion still on that role's menu.

**The role drinks it with `eat`**, giving exactly the name:
`eat {"meal": "精力补充药剂"}` (or the line `[吃 精力补充药剂]`). It sees the
amount on its menu: "· 精力补充药剂（回 30% 体力 · 慢慢喝）". The human can feed
it instead: `POST /api/potions/<row id>/feed`.

---

# 中文：把你的小机接进来

要接的东西有三样，只有第一样是必须的。

1. **工具**：他在厨房里怎么做事。
2. **带给他的话**：他不在场时发生的事，怎么让他知道。
3. **状态行**：可选，每一轮都带给他看的几句现状。

## 1. 工具（MCP）

把任何支持 MCP 的客户端指向 `http://127.0.0.1:8765/mcp`（Streamable HTTP）。设了 `server.token` 的话，要带上 `Authorization: Bearer <token>`。

| 工具 | 做什么 |
|---|---|
| `kitchen_cook` | 开一锅：菜名、分钟数（真实计时）、用冰箱里的哪几样、可选的做法。 |
| `kitchen_status` | 看厨房：火上有什么、最近出锅了什么、冰箱、买菜券。 |
| `kitchen_cancel` | 关火。下了锅的食材不退。 |
| `kitchen_toss` | 扔东西，当场生效。 |
| `kitchen_buy` | 用一张买菜券买菜，一次最多五样。 |
| `eat` | 吃：菜单上的、刚出锅的、或者冰箱里能直接吃的。 |
| `read_menu` | 一次看全：菜单、零食架、冰箱。 |
| `snack_eat` | 吃一份零食。 |
| `kitchen_notes` | 取走等着他的话（见下一节）。 |

### 在具体的客户端里怎么接

这里只写对照过各客户端官方现行文档的步骤，细节请点链接看原文。

**Claude Code**（[官方文档](https://code.claude.com/docs/en/mcp)）。把服务加成一个远程 HTTP 服务器；设了口令的话用请求头带上：

```sh
claude mcp add --transport http kitchenette http://127.0.0.1:8765/mcp
# 有口令时：
claude mcp add --transport http kitchenette http://127.0.0.1:8765/mcp \
  --header "Authorization: Bearer 你的口令"
```

加上 `--scope user` 就在你所有的项目里都能用（默认是 `local`，只在当前项目）。`claude mcp list` 能看到连上没有；在 Claude Code 里输入 `/mcp` 也能看到。

**claude.ai 网页和 Claude Desktop：自定义连接器**（[官方帮助文章](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)）。Pro 和 Max：进 **Customize > Connectors**，点 **+ Add**，再点 **Add custom connector**，填服务的 `/mcp` 地址。口令填在 **Request headers** 里（`Authorization: Bearer 你的口令`）。那篇文章里有两点决定了你能不能这样接：

- 连接是从 Anthropic 的服务器发起的，不是从你的电脑，所以地址必须能从公网访问。`http://127.0.0.1:8765` 不行；要先给服务一个公网的 HTTPS 地址（见 [INSTALL.md](INSTALL.md)），并且设好 `server.token`；
- Team 和 Enterprise 要由所有者在 **Organization settings > Connectors** 里添加。

**其他客户端。** 只要它支持用 Streamable HTTP 连 MCP，把 `/mcp` 地址和口令请求头给它就行。具体在哪里填，每个客户端不一样，请查该客户端自己的 MCP 文档。

### 谁是谁

每个工具都有一个可以不填的 `who`。不填就是设置里的默认角色（`roles.default`）。一个服务可以同时照顾好几个小机：给每人一个自己的名字，冰箱、买菜券、菜单、体力都各是各的，互相看不到。

开锅成功时，结果里还会带一张「做饭卡」（在 `structuredContent` 里）：

```json
{"attachments": [{"kind": "kitchen_cooking", "session_id": "…", "who": "companion",
                  "dish": "番茄炒蛋", "note": "", "duration_seconds": 600,
                  "started_at": 1794467301.27, "method": "stirfry"}]}
```

聊天页面可以拿它画倒计时，之后用 `GET /api/kitchen?session_id=…` 问这一锅是出锅了还是被关火了。

不用 MCP 也行：`kitchenette.tools.call(名字, 参数, 角色)` 就是同一套工具的 Python 函数，`tools.schemas()` 给出可以直接交给模型的工具定义。客户端的写法见 `examples/mcp_client.py`。

### 厨房说的话

工具说明和回执都是中文，只陈述事实，不教他该有什么感受。全部集中在一个文件里：`src/kitchenette/texts.py`。

**只接 MCP 的人不用再做什么。** 有九句话各有两个版本：一个教他「在回复里单独写一行方括号标签」来做事（「吃完哪道，回复里单独一行写 [吃 菜名]」），另一个改成指向工具（「吃完哪道，用 eat 写上菜名」）。开箱时（`inline.enabled = "auto"`）厨房用的是工具版；等真的有回复被送进 `POST /api/inline`（见下面「方括号标签」那一节），它会自己换成标签版。所以只会调工具的模型，不会被教去写一行什么都不会发生的字。想固定成某一种：

```toml
[inline]
enabled = true     # 一直教他写方括号标签
# enabled = false  # 一直指向工具；/api/inline 拒绝请求
```

还有一句话会跟着设置变。`kitchen_cook` 的说明里讲出锅的那一句，在往外推通知时（`notify.mode` 是 `webhook` 或 `both`）以「到点会叫醒你一次」收尾，因为这时确实有东西会叫他。排队模式（`queue`）下没人叫他，这半句就换成「到点会留一句话等你来取」；`none` 模式下这半句不出现。

## 方括号标签：写一行就把事办了（默认自动）

除了调工具，模型也可以在回复里单独写一行来做事：

```
[买菜 番茄 鸡蛋]
[吃 番茄炒蛋]
[零食 拿铁]
[扔掉 坏了的]
```

把每条回复连同一个 `message_id` 送给 `POST /api/inline`。你会拿回去掉这些行的回复（用来显示），以及每个方括号的一条回执；把回执里的 `rendered` 在下一轮带给模型。同一个 `message_id` 再送一次，什么都不会重复发生。`examples/inline_markers.py` 可以直接跑。

回执也可以像 `kitchen_cook` 那样带一张卡。刷盘子开着时，开始了一趟刷盘子的 `[刷盘子]` 回的是：

```json
{"marker": "刷盘子", "args": "", "ok": true, "text": "开始刷了:3 只盘子,大概 6 分钟。", "rendered": "…",
 "attachments": [{"kind": "kitchen_washing", "job_id": "…", "who": "companion",
                  "n": 3, "per_s": 120.0, "started_at": 1794467301.27}]}
```

聊天页面可以拿它显示刷盘子卡（`<kitchenette-washing-card>`，见 [`web/README.md`](../web/README.md#刷盘子卡)），卡在刷的过程中用 `GET /api/dishes/jobs/<job_id>` 读回哪只碎了。别的标签，以及什么都没开始的 `[刷盘子]`（水槽是空的、已经在刷了），`attachments` 都是空的。

`inline.enabled` 说的是「你有没有这么做」，可以填三种值：

| 填什么 | 厨房的提示语 | `/api/inline` |
|---|---|---|
| `"auto"`（默认） | 在你的聊天程序真的把一条回复送进 `/api/inline` 之前，指向工具；送进来第一条之后，就改成教他写这些行 | 一开始就能用 |
| `true` | 教他写这些行 | 能用 |
| `false` | 改成指向工具（`eat`、`snack_eat`、`kitchen_buy`、`kitchen_toss`） | 拒绝（409） |

`"auto"` 的好处：线没接好之前不会把他指到一条走不通的路上，接好之后也不用回来改设置——第一条回复送进来，提示语自己就跟着换了。「已经有回复送进来过」这件事记在库里，重启也不会忘。

## 2. 带给他的话

锅到点了、你给他买了菜、零食里吃出了虫子、开始饿了——每件事都会变成一条现成的句子。用 `notify.mode` 选这些话怎么到他那里。

**`queue`（默认）：排队等他来取。** 话留在服务里。每一轮开始前取一次，放到模型面前；或者让模型自己调 `kitchen_notes`：

```sh
curl -X POST localhost:8765/api/notes/take -H 'content-type: application/json' -d '{}'
# {"notes": [...], "text": "【厨房·非用户发言】你 16:19 下锅的『番茄炒蛋』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。"}
```

每条话只交出去一次。能直接跑的版本在 `examples/notify_queue.py`。

**`webhook`：一有事就通知你的程序。** 服务会把话 POST 到 `notify.webhook_url`，你的程序收到后可以替模型开一轮——这样就算没人在聊天，「饭好了」也能准点到。`examples/notify_webhook_receiver.py` 是一个可以照着改的接收端。「几点到几点别吵」和「睡着别吵」只对这种方式起作用，见 [HOOKS.md](HOOKS.md)。

**`both`** 既往外发、也允许来取：哪边先到，这句话就算交给他了，不会再交第二次。**`none`** 什么都不记。

锅到点的那一刻话就写好了，不用等下一次定时检查：只要他调了任何工具、或页面来读，厨房都会先把到点的锅结掉。所以不会出现「`kitchen_status` 说已经出锅了，`kitchen_notes` 却是空的」。

同一类的事在他知道之前攒了好几件，会合成一句话告诉他：连着往菜单上挂三道菜，到他那里是「…刚在菜单上挂了 3 道:『…』、『…』、『…』」，不是三条。上一条被取走或推出去之后，再来的事另起一条。

话的种类：`kitchen.served`（出锅）、`worm.eaten`（吃到虫子）、`hungry`（饿了）、`fridge.bought`（你买了菜）、`fridge.coupon`（你发了券）、`snack.fed` / `potion.fed` / `menu.fed`（你喂了他）、`menu.posted`（你往菜单上挂了菜）。

## 3. 状态行（可选）

`GET /api/turn-lines?who=…` 返回一段时间内一直成立的事实，适合在它们有效期间每一轮都给模型看：

```json
{"kitchen": "【厨房·非用户发言】你 17:20 吃了坏掉的『生菜汤』,现在有点晕乎乎的,大约 19:50 缓过来。",
 "body": "[你的身体 17:25 | 体力 0.62]"}
```

没什么可说的时候 `kitchen` 是空的。「晕乎乎」那一行是按结束时间写的，所以每一轮的文字完全相同（对提示缓存友好）。

## 体力：告诉厨房他这一轮干了什么

干活掉体力，休息回体力。厨房自己的工具，调用时当场就记了账。他做的其他事（别的工具），请在每一轮结束后报一次：

```sh
curl -X POST localhost:8765/api/rounds/settle -H 'content-type: application/json' \
     -d '{"round_id": "msg_123", "tools": ["web_search", "write_diary"]}'
# {"stamina": 0.64, "receipts": [{"kind": "coupon", "ok": true, "text": "得了一张买菜券(现在 1/3)。"}], "duplicate": false}
```

`tools` 里写这一轮成功调用过的工具名。哪些算干活、哪些算休息、哪些能换买菜券，都由你在设置里定，见 [CONFIG.md](CONFIG.md)。开箱时没有任何工具能换券（上面的例子假设你已经把 `write_diary` 写进了 `[coupons.earn]`）；没配之前，券只能由你来发。带上 `round_id`，同一轮报两次也不会重复算。返回里的 `receipts` 请在下一轮带给模型看。不报也可以：那就只有厨房里的事会动体力。

## 精力补充药剂

药剂是你挂在菜单上的一样东西，带一个数：回多少体力。它不算一顿饭。

**一步挂好**（页面请用这个：两件事要么都成，要么都不成，不会留下半截）：

```sh
curl -X POST localhost:8765/api/potions/hang -H 'content-type: application/json' \
     -d '{"who": "companion", "pct": 30, "memo": "慢慢喝"}'
# {"ok": true, "row": {"id": "…", "dish": "精力补充药剂", "note": "回 30% 体力 · 慢慢喝", …}, "potion": {"pct": 30, …}}
```

**或者分两步**（一步挂好就是替你做了这两步）：

1. 往菜单上挂一行，菜名必须正好是 `精力补充药剂`：
   `POST /api/menu {"dish": "精力补充药剂", "by": "human", "for_who": "companion"}`，记下返回的 `id`；
2. 给这一行登记回多少：
   `POST /api/potions {"who": "companion", "menu_row_id": "<上一步的 id>", "pct": 30, "memo": "慢慢喝"}`。

只做了第 1 步的那一行喝不了；第 2 步如果对着一行「不是这个角色菜单上还挂着的药剂」，会被拒绝。

**他用 `eat` 来喝**，菜名要正好是这个名字：`eat {"meal": "精力补充药剂"}`（或者写一行 `[吃 精力补充药剂]`）。他在菜单上看得到数值：「· 精力补充药剂（回 30% 体力 · 慢慢喝）」。你也可以直接喂他：`POST /api/potions/<那一行的 id>/feed`。
