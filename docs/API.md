# REST reference

Base path `/api`. JSON in, JSON out. When `server.token` is set every endpoint
except `/api/health` needs `Authorization: Bearer <token>`.

A role is named with `who` (query string for GET, body field otherwise);
`viewer` is accepted as an alias. Left out, it is `roles.default`. Times are
epoch seconds unless noted. Error responses are `{"detail": …}`. The detail
is a sentence in Chinese written for the person using the page, and can be
shown as is ("没有这一行。", "这道菜已经吃掉了。", "口令不对,或者没带口令。"); for
potions, and for a snack past its daily cap, it is an object whose `message`
is that sentence. The one exception
is a request whose shape is wrong (a missing field, a wrong type): that is
answered with FastAPI's standard 422 list, meant for the developer.

## Kitchen

### `GET /api/kitchen?who=<role>`

```json
{"now": 1794467400.0,
 "timezone": "Asia/Shanghai",   // server.timezone as configured; "" = the server machine's own
 "cooking": [<pot>, …],
 "recent":  [<pot>, …]}        // served or cancelled, newest first, up to 50
```

### `GET /api/kitchen?session_id=<id>`

```json
{"now": 1794467400.0, "timezone": "Asia/Shanghai", "session": <pot> | null}
```

A pot:

| Field | |
|---|---|
| `id` | Pot id (the `session_id` on the cooking card). |
| `dish`, `note` | As given when the pot was opened. |
| `duration_seconds`, `started_at` | Cooking is real time: due at `started_at + duration_seconds`. |
| `status` | `cooking`, `served`, `cancelled`, or `ruined` (a spoiled egg went in). |
| `served_at`, `cancelled_at` | Set when that happened, else null. |
| `remaining_seconds` | Seconds left while cooking, else 0. |
| `outcome` | `great`, `ok`, `burnt`, `spoiled` once served; `ruined`; null while cooking. |
| `ingredients` | `[{"name", "qty", "freshness"}]`: what went in. |
| `method` | `stirfry`, `fry`, `deepfry`, `boil`, `steam`, `bake`, `mix`: picks the cooking animation. |

Also present: `who`, `eaten_at`, `menu_row_id`, `menu_added_at`, `woke_at`,
`worm_state`, `wormed_at`, `created_at`.

Pots are opened, cancelled and tossed by the role through its tools, not here.

### `GET /api/kitchen/can_eat?who=&meal=`

`{"ok": bool, "why": "pot" | "raw" | "cooking" | "none", "text": "<refusal>"}`.
Answers for what is not on the menu.

## Fridge

| | |
|---|---|
| `GET /api/fridge?who=` | `{now, who, items, staples, coupons: {count, max}, log, satiety: {value, updated_at, enabled}, dizzy, text}`. `items` are batches: `{batch_id, item_id, name, category, qty, bought_at, by, expires_at, freshness, wormed, art?}`, most urgent first. `text` is the fridge paragraph as the role reads it. |
| `GET /api/fridge/catalog` | Everything buyable: `{id, name, category, category_label, pack_qty, shelf_days, raw_edible, custom, art?}`. |
| `POST /api/fridge/buy` `{who, items: [id…]}` | The human buys (no coupon). `{ok, added, text}`. Tells the role (`fridge.bought`). |
| `POST /api/fridge/coupon` `{who}` | The human hands out a coupon. `{ok, count, text}`; 409 at the cap. Tells the role (`fridge.coupon`). |
| `POST /api/coupons/earn` `{who, source, key}` | The role earned a coupon for `source` (a word like "日记"). `key` makes it once-only. `{ok, granted, text, reason}`: `reason` is `""` when granted, `"duplicate"` when this key was already used, `"full"` when the role is at the cap (`text` is empty in both cases), `"failed"` when it could not be written. |

### Ingredient kinds added by the human

| | |
|---|---|
| `POST /api/fridge/kinds` `{name, category, raw_edible?, pack_qty?, shelf_days?}` | `{ok, kind}`. `category` may be the key (`staple_food`) or the label (`主食`). 400 with the reason for a bad name or value (an unknown category lists the choices), 409 for a duplicate. |
| `DELETE /api/fridge/kinds/{id}` | Stops offering it; what is already in a fridge stays usable. |
| `POST /api/fridge/kinds/{id}/redraw` | Draw the picture again (409 when no art provider is set). |
| `GET /api/fridge/art/{id}/{fresh\|meh\|bad}.png?v=` | The picture, cacheable forever per version. |

`kind.art.state` is `none` (no provider: show a text card), `pending`,
`ready` or `failed` (`art.err` says why).

## Menu

A row: `{id, dish, note, by, for_who, eaten_at, created_at, updated_at}` with
ISO times, plus `eaten_ts` / `created_ts` in epoch seconds. `eaten_at` null =
still on the table. `by` is whoever put it up; the kitchen uses the role's own
id for dishes the role cooked.

| | |
|---|---|
| `GET /api/menu?pending=1&for_who=` | Newest first. |
| `POST /api/menu` `{dish, by, for_who, note?}` | 201 with the row. When `by` is not the role itself the role is told (`menu.posted`). |
| `PATCH /api/menu/{id}` `{eaten_at?, note?, dish?, if_pending?}` | `if_pending: true` refuses (409) a row already eaten. |
| `DELETE /api/menu/{id}` | |
| `POST /api/menu/{id}/feed` | The human feeds the dish to its role: marks it eaten, settles the meal, tells the role (`menu.fed`). 409 if already eaten. |

## Snacks

| | |
|---|---|
| `GET /api/snacks?who=` | `{who, day, resets_at, energy_enabled, cap_min, cap_max, snacks: [{id, name, tier, tier_label, default_cap, cap, eaten, gain, variants}], recent}`. |
| `POST /api/snacks/eat` `{who, snack, variant?}` | The human feeds one. `{result, notified, state}`; 409 `{reason: "cap", …}` at the daily cap. Tells the role (`snack.fed`). |
| `PUT /api/snacks/caps` `{who, caps: {snack id: n}}` | Set daily caps (0 = not today). Returns the shelf. |

## Potions

A potion is a menu row named `精力补充药剂` plus an amount registered here.

| | |
|---|---|
| `GET /api/potions?who=` | `{name, note_fmt, memo_sep, memo_max, pct_min, enabled, items}`. |
| `POST /api/potions/hang` `{who, pct, memo?, by?}` | Put a potion on the menu and record its amount in one step: both happen or neither. `{ok, row, potion}`. Use this from a page. |
| `POST /api/potions` `{who, menu_row_id, pct, memo?}` | The second of the two separate steps: register the amount for a menu row you created with `POST /api/menu` (dish exactly `精力补充药剂`). Refused (400, code `bad_row`) unless that row is a potion still on this role's menu. |
| `PATCH /api/potions/{menu_row_id}` `{who, pct, memo?}` | Change it while it is still on the menu. |
| `DELETE /api/potions/{menu_row_id}` | Void it. |
| `POST /api/potions/drink` `{who, menu_row_ids}` | The role drinks one. |
| `POST /api/potions/{menu_row_id}/feed` `{who}` | The human feeds it. Tells the role (`potion.fed`). |

Errors are `{"detail": {"message", "code", "rows"}}` with 409 for `used`,
`gone`, `busy`, `unregistered`, `stamina_off`, 503 for `energy`, 400 otherwise.

## Body and turns

| | |
|---|---|
| `GET /api/stamina?who=` | `{enabled, energy, line, recent}`; `energy` is 0-1 or null when off. |
| `GET /api/turn-lines?who=` | `{kitchen, body}`: status lines for the role's next turn, each null when there is nothing to say. |
| `POST /api/rounds/settle` `{who, tools, round_id?}` | Report the tools one finished round used. `{stamina, receipts, duplicate}`. |
| `GET /api/sleep?who=` / `PUT /api/sleep` `{who, asleep?, until?, factor?}` | See [HOOKS.md](HOOKS.md). |

## Notes and markers

| | |
|---|---|
| `GET /api/notes?who=` | `{notes}` waiting, not taken. |
| `POST /api/notes/take` `{who}` | `{notes, text}`; marks them taken. |
| `POST /api/inline` `{who, text, message_id?, told?}` | Run bracket markers in a reply. `{receipts: [{marker, args, ok, text, rendered}], stripped}`. 409 when `inline.enabled` is `false`; with `"auto"` it works, and the first call switches the wording over. |

## Housekeeping

| | |
|---|---|
| `GET /api/health` | `{ok, version, now}`. No token needed. |
| `GET /api/roles` | `{default, roles}`: roles that exist so far. |
| `POST /api/scan` | Run the periodic scan now. |
| `POST /api/dev/clock` `{advance_seconds?, reset?}` | Only with `server.dev_clock`. Walks time forward, scanning as it goes. It moves the clock of the whole server, for every role in the database: never use it on a kitchen in use. |

---

# 中文：页面用的接口（REST）

所有地址都以 `/api` 开头，收发都是 JSON。设了 `server.token` 之后，除了 `/api/health`，每个请求都要带 `Authorization: Bearer <token>`。

角色用 `who` 指定（GET 写在地址的查询参数里，其他写在请求体里）；写成 `viewer` 也认。不写就是默认角色。时间没特别说明的都是「从 1970 年起的秒数」。出错时返回 `{"detail": …}`。`detail` 是一句写给页面使用者看的中文，可以直接显示（「没有这一行。」「这道菜已经吃掉了。」「口令不对,或者没带口令。」）；药剂的接口、以及零食吃到当日上限时，它是一个对象，其中的 `message` 是那句话。唯一的例外是请求本身的形状不对（缺字段、类型不对）：这时返回的是 FastAPI 标准的 422 列表，那是给写程序的人看的。

## 厨房

### `GET /api/kitchen?who=<角色>`

```json
{"now": 1794467400.0,
 "timezone": "Asia/Shanghai",   // 设置里的 server.timezone；空串表示用服务所在电脑的时区
 "cooking": [<一锅>, …],       // 正在火上的
 "recent":  [<一锅>, …]}       // 已出锅或已关火的，新的在前，最多 50 条
```

### `GET /api/kitchen?session_id=<锅的 id>`

```json
{"now": 1794467400.0, "timezone": "Asia/Shanghai", "session": <一锅> 或 null}
```

一锅的字段：

| 字段 | 意思 |
|---|---|
| `id` | 这一锅的 id（做饭卡上的 `session_id`）。 |
| `dish`、`note` | 菜名、备注，开锅时写的。 |
| `duration_seconds`、`started_at` | 做多久、几时开的火。真实计时：到点时刻 = `started_at + duration_seconds`。 |
| `status` | `cooking` 在火上、`served` 出锅了、`cancelled` 关火了、`ruined` 打到坏鸡蛋毁了。 |
| `served_at`、`cancelled_at` | 出锅 / 关火的时刻，没发生就是 null。 |
| `remaining_seconds` | 还剩多少秒（不在火上时是 0）。 |
| `outcome` | 出锅结果：`great` 很好、`ok` 普通、`burnt` 糊了、`spoiled` 坏了；`ruined`；还在火上是 null。 |
| `ingredients` | 用了什么：`[{"name", "qty", "freshness"}]`。 |
| `method` | 做法：`stirfry` 炒、`fry` 煎、`deepfry` 炸、`boil` 煮、`steam` 蒸、`bake` 烤、`mix` 拌。小动画按它选。 |

另外还有：`who`、`eaten_at`、`menu_row_id`、`menu_added_at`、`woke_at`、`worm_state`、`wormed_at`、`created_at`。

开锅、关火、扔东西是他通过工具做的，这里没有对应的接口。

### `GET /api/kitchen/can_eat?who=&meal=`

`{"ok": 能不能吃, "why": "pot" | "raw" | "cooking" | "none", "text": "不能吃时给他看的那句"}`。回答的是「不在菜单上的东西能不能吃」。

## 冰箱

| 接口 | 说明 |
|---|---|
| `GET /api/fridge?who=` | 一次读全：`items`（每一批食材：`batch_id`、`item_id`、`name`、`category`、`qty` 数量、`bought_at` 买入时刻、`by` 谁买的、`expires_at` 到期时刻、`freshness` 新鲜度、`wormed` 长没长虫、自己添的种类还有 `art`），快坏的排前面；`staples` 常备品；`coupons: {count, max}` 买菜券；`log` 最近的厨房记录；`satiety` 饱食度；`dizzy` 晕不晕；`text` 他看到的冰箱那一段文字。 |
| `GET /api/fridge/catalog` | 能买的全部种类：`id`、`name`、`category`、`category_label` 类别名、`pack_qty` 一份几个、`shelf_days` 能放几天、`raw_edible` 能不能直接吃、`custom` 是不是你自己添的、`art`。 |
| `POST /api/fridge/buy` `{who, items: [id…]}` | 你给他买菜（不扣券）。返回 `{ok, added, text}`，并且会告诉他。 |
| `POST /api/fridge/coupon` `{who}` | 你给他一张券。返回 `{ok, count, text}`；已满返回 409。会告诉他。 |
| `POST /api/coupons/earn` `{who, source, key}` | 他做了某件事、该得一张券。`source` 是「做的是什么」（如 "日记"），`key` 保证同一件事只发一次。返回 `{ok, granted, text, reason}`：`reason` 发成了是空串，这个 `key` 已经发过是 `"duplicate"`，券已经满了是 `"full"`（这两种情况 `text` 是空的），没写进去是 `"failed"`。 |

### 你自己添的食材种类

| 接口 | 说明 |
|---|---|
| `POST /api/fridge/kinds` `{name, category, raw_edible?, pack_qty?, shelf_days?}` | 添一样。`category` 填代号（`staple_food`）或中文名（`主食`）都认。名字或数值不合规返回 400 并说明原因（类别不认识时会列出可选的），重名返回 409。 |
| `DELETE /api/fridge/kinds/{id}` | 撤掉：以后买不了；冰箱里已有的照常能用。 |
| `POST /api/fridge/kinds/{id}/redraw` | 小图重画一遍（没接画图函数时返回 409）。 |
| `GET /api/fridge/art/{id}/{fresh\|meh\|bad}.png?v=` | 取小图。同一个版本号的图永远不变，可以长期缓存。 |

`kind.art.state`：`none` 没接画图（显示字卡）、`pending` 在画、`ready` 画好了、`failed` 没画成（`art.err` 里有原因）。

## 菜单

一行的字段：`id`、`dish` 菜名、`note` 备注、`by` 谁挂的、`for_who` 挂给谁、`eaten_at` 吃掉的时间（null 表示还在桌上）、`created_at`、`updated_at`（这三个时间是带时区的文字），另有 `eaten_ts` / `created_ts`（秒数）。他自己做的菜，`by` 是他自己的名字。

| 接口 | 说明 |
|---|---|
| `GET /api/menu?pending=1&for_who=` | 列出菜单，新的在前。`pending=1` 只要还没吃的。 |
| `POST /api/menu` `{dish, by, for_who, note?}` | 挂一道菜，成功返回 201。挂的人不是他自己时会告诉他。 |
| `PATCH /api/menu/{id}` `{eaten_at?, note?, dish?, if_pending?}` | 改。带 `if_pending: true` 时，已经吃掉的行会被拒绝（409）。 |
| `DELETE /api/menu/{id}` | 撤菜。 |
| `POST /api/menu/{id}/feed` | 你把这道菜喂给他：划掉、算一顿、告诉他。已经吃过返回 409。 |

## 零食

| 接口 | 说明 |
|---|---|
| `GET /api/snacks?who=` | 零食架：每样的 `cap` 今日上限、`eaten` 今天吃了几份、`gain` 回多少体力、`variants` 口味；`resets_at` 几时清零；`recent` 今天的记录。 |
| `POST /api/snacks/eat` `{who, snack, variant?}` | 你喂他一份。到了今日上限返回 409。会告诉他。 |
| `PUT /api/snacks/caps` `{who, caps: {零食 id: 份数}}` | 改每日上限（0 = 今天不供应）。 |

## 药剂

药剂 = 菜单上一行名叫 `精力补充药剂` 的菜 + 在这里登记的「回多少体力」。

| 接口 | 说明 |
|---|---|
| `GET /api/potions?who=` | 还挂着的药剂，以及显示时用的格式。 |
| `POST /api/potions/hang` `{who, pct, memo?, by?}` | 一步挂好：往菜单上挂一瓶药剂并登记回多少，两件事要么都成要么都不成。返回 `{ok, row, potion}`。页面请用这个。 |
| `POST /api/potions` `{who, menu_row_id, pct, memo?}` | 分两步时的第二步：给你先用 `POST /api/menu` 挂上去的那一行（菜名必须正好是 `精力补充药剂`）登记回多少和备注。那一行如果不是这个角色菜单上还挂着的药剂，会被拒绝（400，`code` 是 `bad_row`）。 |
| `PATCH /api/potions/{menu_row_id}` `{who, pct, memo?}` | 还没喝之前可以改。 |
| `DELETE /api/potions/{menu_row_id}` | 作废。 |
| `POST /api/potions/drink` `{who, menu_row_ids}` | 他自己喝一瓶。 |
| `POST /api/potions/{menu_row_id}/feed` `{who}` | 你喂他喝。会告诉他。 |

出错时 `detail` 是 `{"message", "code", "rows"}`：已喝过 / 正在喝 / 没登记 / 体力没开是 409，体力没加上是 503，其他是 400。

## 身体与每一轮

| 接口 | 说明 |
|---|---|
| `GET /api/stamina?who=` | 体力：`energy` 是 0 到 1 的数，关着时是 null。 |
| `GET /api/turn-lines?who=` | 下一轮可以带给他的状态行：`kitchen`（晕 / 饿）和 `body`（体力），没什么可说时是 null。 |
| `POST /api/rounds/settle` `{who, tools, round_id?}` | 上报他这一轮用过的工具，用来算体力和发券。 |
| `GET /api/sleep?who=`、`PUT /api/sleep` `{who, asleep?, until?, factor?}` | 睡眠口子，见 [HOOKS.md](HOOKS.md)。 |

## 带给他的话与方括号

| 接口 | 说明 |
|---|---|
| `GET /api/notes?who=` | 看有哪些话在等，不取走。 |
| `POST /api/notes/take` `{who}` | 取走并标记，返回 `{notes, text}`。 |
| `POST /api/inline` `{who, text, message_id?, told?}` | 执行一条回复里的方括号标签，返回每个标签的回执和去掉方括号行之后的正文。`inline.enabled` 是 `false` 时返回 409；是 `"auto"` 时照常可用，第一次调用之后提示语就改成教他写方括号。 |

## 杂项

| 接口 | 说明 |
|---|---|
| `GET /api/health` | 活着没有。不需要 token。 |
| `GET /api/roles` | 目前有哪些角色。 |
| `POST /api/scan` | 立刻做一次定时检查。 |
| `POST /api/dev/clock` `{advance_seconds?, reset?}` | 只有打开 `server.dev_clock` 才有：让时间往前走，途中照常检查。它拨的是整台服务的钟，库里所有角色一起跳——正在用的厨房别用。 |
