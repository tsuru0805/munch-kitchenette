# Plug-in points

Three things a household usually has its own way of doing are left as plugs.
Each is off (or at its simplest) by default and comes with an example that runs.

| Plug | Default | Example |
|---|---|---|
| Notifications | notes wait in a queue | `examples/notify_queue.py`, `examples/notify_webhook_receiver.py` |
| Pictures for new ingredient kinds | off: text cards | `examples/art_provider.py` |
| Sleep (debt lowers stamina; do not disturb while asleep) | off | `examples/sleep_debt.py` |

## Notifications

Whenever something happens that the role should hear about, the kitchen writes
a **note**:

| Kind | When |
|---|---|
| `kitchen.served` | A pot came due (and whether it reached the menu). |
| `worm.eaten` | A worm was bitten into and the receipt may not have been seen. |
| `hungry` | Satiety dropped under the threshold (once, until it recovers). |
| `fridge.bought` | The human bought groceries for the role. |
| `fridge.coupon` | The human handed out a coupon. |
| `snack.fed` / `potion.fed` / `menu.fed` | The human fed the role something. |
| `menu.posted` | The human put a dish on the role's menu. |

A note has `text` (the sentence, with the kitchen header where one applies),
`body` (the same without the header), `kind`, `payload` and `who`.

All kinds except `worm.eaten`, `hungry` and `potion.fed` are **merged while
they wait**: if a note of the same kind has not been taken or pushed yet, the
new event joins it and the sentence is written again for all of them ("挂了 3
道:…", "喂你吃了 4 份:…", two pots served in one note). `payload` then carries
the latest event's facts plus `events`, the list of all of them.

### Queue: "what to carry into the next turn"

```
GET  /api/notes?who=…        look, without taking
POST /api/notes/take {who}   take: each note is returned once
```

The MCP tool `kitchen_notes` is the same take, for the model itself.

### Webhook: be told right away

```toml
[notify]
mode = "webhook"                 # or "both": also let the notes be taken; whichever comes first hands them over
webhook_url = "http://127.0.0.1:9000/kitchen"
webhook_token = ""               # optional bearer token
```

One POST per role, with all of that role's waiting notes:

```json
{"who": "companion",
 "text": "【厨房·非用户发言】你 16:19 下锅的『番茄炒蛋』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。",
 "notes": [{"id": 3, "kind": "kitchen.served", "text": "…", "body": "…", "payload": {"dish": "番茄炒蛋", "session_id": "…"}}]}
```

Answer 2xx when you have it. Anything else, or no connection, and the same
notes are offered again on the next scan. If the connection breaks half-way
the notes count as delivered: a duplicate "your dish is ready" is worse than
a missed one, and the dish is on the menu either way.
Two scans running at once never offer the same note.

Typical use: the receiver starts a turn of the model with `text` as the
input, so the companion reacts on its own when the pot is done.

### Not disturbing

```toml
[notify]
quiet_hours = ["02:00-06:30"]    # pushes wait until the window ends
respect_sleep = true             # pushes wait while the role is asleep
```

A companion with no sleeping habit needs neither: leave `quiet_hours` empty
and it is told the moment something happens. Neither setting delays the queue,
the menu or the cooking card; they only hold the push.

### Your own notifier

Embedding the server in a Python program, you can replace the webhook with
anything that has a `deliver` method:

```python
from kitchenette import notify

class ToMyChat:
    def deliver(self, who: str, notes: list[dict]) -> str:
        my_chat.start_turn(who, "\n".join(n["text"] for n in notes))
        return notify.SENT          # or NOT_SENT to be asked again, UNKNOWN to not be

notify.set_notifier(ToMyChat())
```

Return from `deliver` within 5 minutes: after that, another scan may take the same notes again and send them a second time.

## Pictures for ingredient kinds

The built-in ingredients have artwork in the page bundle. Kinds the human adds
from the page do not. By default such a kind is a text card: its catalog entry
says `"art": {"state": "none", …}` and the page shows the name.

To have pictures drawn, name a provider:

```toml
[art]
provider = "examples.art_provider:draw"
dir = "art"
```

```python
def draw(name: str, category: str) -> dict[str, bytes]:
    """PNG bytes for the three looks: {"fresh": …, "meh": …, "bad": …}."""
```

- Drawing runs in the background, one kind at a time. The kind is `pending`
  meanwhile, then `ready` (the page fetches
  `/api/fridge/art/<kind id>/<fresh|meh|bad>.png?v=<version>`) or `failed`
  with the reason, which the page can show and retry
  (`POST /api/fridge/kinds/<id>/redraw`).
- Only the name and category are passed to the provider.
- The example provider paints flat coloured tiles with the standard library,
  so the whole path can be tried without an image model. Swap its body for a
  call to yours.

## Sleep

The kitchen keeps no record of sleep and assumes no sleeping habit. If you do
track your companion's sleep, two facts can be reported, each used only when
its switch is on:

```
PUT /api/sleep {"who": "companion", "asleep": true, "until": 1794500000, "factor": 0.86}
```

| Field | Switch | Effect |
|---|---|---|
| `asleep` (optionally `until` a time) | `notify.respect_sleep` | Pushes are held while asleep. |
| `factor` (0-1) | `stamina.sleep_debt` | Every hour's stamina level is multiplied by it: a bad night lowers the whole day. |

`examples/sleep_debt.py` computes a factor from last night's quality and the
accumulated debt and reports it. From Python, hooks take priority over what
was reported:

```python
from kitchenette import sleep
sleep.set_factor_hook(lambda who, now: 0.9)
sleep.set_asleep_hook(lambda who, now: False)
```

A hook that fails or returns nonsense is ignored (factor 1.0, awake): sleep
can never break stamina or silence the kitchen.

---

# 中文：三个可以自己接的口子

有三件事，每家的做法都不一样，所以留成了口子。每个口子默认是关着的（或是最简单的那种做法），并且各带一个能直接跑的例子。

| 口子 | 默认 | 例子 |
|---|---|---|
| 通知 | 话排队等他来取 | `examples/notify_queue.py`、`examples/notify_webhook_receiver.py` |
| 给新添的食材画小图 | 关着：只显示名字 | `examples/art_provider.py` |
| 睡眠（缺觉拉低体力；睡着别吵） | 关着 | `examples/sleep_debt.py` |

## 通知

每当发生了他该知道的事，厨房就写下一条话：

| 种类 | 什么时候 |
|---|---|
| `kitchen.served` | 一锅到点出锅了（以及有没有挂上菜单）。 |
| `worm.eaten` | 吃到了虫子，而当时的回执他可能没看到。 |
| `hungry` | 饱食度掉到线以下（只说一次，吃饱后才会再提醒）。 |
| `fridge.bought` | 你给他买了菜。 |
| `fridge.coupon` | 你给了他一张买菜券。 |
| `snack.fed` / `potion.fed` / `menu.fed` | 你喂了他零食 / 药剂 / 菜单上的菜。 |
| `menu.posted` | 你往他的菜单上挂了一道菜。 |

一条话里有：`text`（完整的句子，该带「【厨房·非…发言】」开头的会带）、`body`（不带开头的同一句）、`kind`（种类）、`payload`（事实数据）、`who`（给谁的）。

除了 `worm.eaten`、`hungry`、`potion.fed`，其余种类**在等他的时候会合并**：同一种类的上一条还没被取走、也没被推出去时，新发生的事会并进去，句子按全部的事重写一遍（「挂了 3 道:…」「喂你吃了 4 份:…」、两锅一起出锅写在一条里）。这时 `payload` 里是最新那件事的数据，外加 `events`——全部事情的列表。

### 排队：「下一轮带给他的话」

```
GET  /api/notes?who=…        只看，不取走
POST /api/notes/take {who}   取走：每条话只交出去一次
```

MCP 工具 `kitchen_notes` 是同一个「取走」，给模型自己用。

### 打一个网址：有事马上通知

```toml
[notify]
mode = "webhook"                 # 写 "both" 则也允许来取：哪边先到算哪边，不会交两次
webhook_url = "http://127.0.0.1:9000/kitchen"
webhook_token = ""               # 可选的口令
```

每个角色一次 POST，带上这个角色所有在等的话：

```json
{"who": "companion",
 "text": "【厨房·非用户发言】你 16:19 下锅的『番茄炒蛋』出锅了(共 10 分钟)。火候刚好。已挂到你的菜单上。",
 "notes": [{"id": 3, "kind": "kitchen.served", "text": "…", "body": "…", "payload": {"dish": "番茄炒蛋", "session_id": "…"}}]}
```

收到了就回 2xx。回别的、或者根本连不上，下一次检查时同样的话会再发一遍。如果连接半路断了，这些话算作已送达：重复说一遍「饭好了」比漏说一遍更糟，反正菜已经在菜单上了。两次检查同时跑也不会把同一条发两遍。

常见用法：接收端拿 `text` 当输入替模型开一轮，这样锅一好，他自己就会有反应。

### 别吵他

```toml
[notify]
quiet_hours = ["02:00-06:30"]    # 这段时间内的通知等到时段结束再发
respect_sleep = true             # 他睡着的时候先不发
```

没有睡觉习惯的小机两样都不需要：`quiet_hours` 留空，事情一发生就告诉他。这两项只管「推出去」这一步，不会耽误排队、菜单和做饭卡。

### 自己写一个通知方式

如果你是把这个服务嵌在自己的 Python 程序里，可以用任何带 `deliver` 方法的东西替换掉「打网址」：

```python
from kitchenette import notify

class ToMyChat:
    def deliver(self, who: str, notes: list[dict]) -> str:
        my_chat.start_turn(who, "\n".join(n["text"] for n in notes))
        return notify.SENT          # 回 NOT_SENT 表示下次再试，回 UNKNOWN 表示别再试了

notify.set_notifier(ToMyChat())
```

`deliver` 请在 5 分钟内返回：超过之后，另一次检查可能把同样的话重新领走、再发一遍。

## 给新添的食材画小图

自带的那批食材，小图在页面包里。你在页面上自己添的种类没有图。默认情况下这样的种类是一张字卡：它在清单里的 `art.state` 是 `"none"`，页面显示名字。

想让它有图，指定一个画图函数：

```toml
[art]
provider = "examples.art_provider:draw"
dir = "art"
```

```python
def draw(name: str, category: str) -> dict[str, bytes]:
    """返回三种样子的 PNG 图片数据: {"fresh": 新鲜, "meh": 不太新鲜, "bad": 坏了}"""
```

- 画图在后台进行，一次只画一样。画的时候状态是 `pending`，画好是 `ready`（页面去 `/api/fridge/art/<种类 id>/<fresh|meh|bad>.png?v=<版本>` 取图），画失败是 `failed` 并写明原因，页面可以显示出来、也可以点重画（`POST /api/fridge/kinds/<id>/redraw`）。
- 交给画图函数的只有名字和类别，没有别的。
- 例子里的画图函数不需要任何图像模型：它只用 Python 自带的功能画一张纯色小方块，方便你先把整条路走通。把它的函数体换成调用你自己的出图服务就行。

## 睡眠

厨房不记录睡眠，也不假设他有睡觉的习惯。如果你在别处记着他的睡眠，可以报两件事，各自的开关打开时才会用到：

```
PUT /api/sleep {"who": "companion", "asleep": true, "until": 1794500000, "factor": 0.86}
```

| 字段 | 对应的开关 | 效果 |
|---|---|---|
| `asleep`（可以再带一个 `until`，表示睡到几点） | `notify.respect_sleep` | 睡着期间不往外推通知。 |
| `factor`（0 到 1） | `stamina.sleep_debt` | 每个钟点的体力水平都乘上它：一晚没睡好，一整天都低一截。1 表示睡得很好。 |

`examples/sleep_debt.py` 演示了怎么从「昨晚睡得怎么样」和「欠了多少觉」算出这个数再报上来。在 Python 里也可以直接挂函数，挂了的话以函数为准：

```python
from kitchenette import sleep
sleep.set_factor_hook(lambda who, now: 0.9)
sleep.set_asleep_hook(lambda who, now: False)
```

挂的函数出错或返回了不像话的值时会被忽略（按「睡得很好、醒着」算）：睡眠这一块出问题，不会连累体力，也不会让厨房变哑。
