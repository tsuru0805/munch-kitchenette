# REST reference

Base path `/api`. JSON in, JSON out. When `server.token` is set every endpoint
except `/api/health` needs `Authorization: Bearer <token>`.

The kitchen page that uses these endpoints is served by the same server at
`/page/` (static files, no token; see [PAGE.md](PAGE.md)).

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
| `POST /api/menu/{id}/feed` | The human feeds the dish to its role: marks it eaten, settles the meal, tells the role (`menu.fed`). `{ok, row, outcome, text, notified}`; `notified` is false when no note was written for the role (`notify.mode = "none"`). 409 if already eaten. |
| `GET /api/meals?who=&since=` | The meals a role has had since `since` (epoch seconds), oldest first: `{now, who, since, meals: [{id, meal, note, at}]}`. Without `since`: today, from midnight in `server.timezone`. Snacks and potions are not meals. |

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
| `POST /api/inline` `{who, text, message_id?, told?}` | Run bracket markers in a reply. `{receipts: [{marker, args, ok, text, rendered, attachments}], stripped}`. `attachments` is a list of cards, empty for most markers; a `[刷盘子]` that started a washing carries the washing card `{kind: "kitchen_washing", job_id, who, n, per_s, started_at}` (see [CONNECT.md](CONNECT.md) and [`web/README.md`](../web/README.md#the-washing-card)). Sending the same `message_id` again answers the same receipts, cards included. 409 when `inline.enabled` is `false`; with `"auto"` it works, and the first call switches the wording over. |

## Housekeeping

| | |
|---|---|
| `GET /api/health` | `{ok, version, now}`. No token needed. |
| `GET /api/roles` | `{default, roles}`: roles that exist so far. |
| `GET /api/about` | What a page needs before it draws anything; read-only. `{version, now, timezone, timezone_label, roles: {default, list}, switches: {stamina, satiety, worms, dev_clock, art}, words: {human_name, human_pronoun, app_name}, limits: {coupon_max, buy_max_items, hungry_below}}`. `roles.list` is the roles that exist so far plus `roles.allowed` and the default. `switches` say which parts are on: a page hides stamina when `stamina` is false, satiety when `satiety` is false, and offers fast-forward only when `dev_clock` is true; `art` is whether an art provider is configured. |
| `POST /api/scan` | Run the periodic scan now. |
| `POST /api/dev/clock` `{advance_seconds?, reset?}` | Only with `server.dev_clock`. Walks time forward, scanning as it goes. It moves the clock of the whole server, for every role in the database: never use it on a kitchen in use. |

## The upgrade

Everything here belongs to one of the seventeen switches (`[play]`); a switched-off one answers 409
"这个玩法没开". One exception: `GET /api/dishes/jobs/<id>`, reading back one washing for a washing card
already in the chat, answers with the plates switched off too (so the card learns the washing was stopped). `who` (or `viewer`) is the role, as everywhere. `GET /api/about` also carries
`features: {key: on}`.

| | |
|---|---|
| `GET /api/features` | `{features: [{key, name, parent, default, markers, on, wanted, reason}]}` — what is on and why not. |
| `GET /api/play/teaching` | `{text}`: the sentences teaching the markers of what is on (empty while markers are not in use). |
| `GET /api/recipes?q=&limit=&who=` | Public recipes (search by name, ingredient or category). `{total, source, categories, recipes: [{id, name, main, optional, method, minutes, category_label, items_text, stopped, …}]}` |
| `GET /api/recipes/today?who=` | `{text}`: today's three picks, as the role reads them. |
| `GET /api/recipes/missing?who=&recipe=` | What the fridge lacks for that recipe, in whole packs, and whether each is sold. |
| `POST /api/recipes/buy_missing` `{who, recipe, op_id}` | The human buys what that recipe lacks (whole packs, only what the shop sells; her usual buying, no coupon). `op_id` (required): one per buying, the same for a retry of it. In one write transaction the server looks up the receipt of that `op_id` (there: answers it again with `replayed: true` and buys nothing, even if the food was used up since), works out what is missing now, buys it and keeps the receipt. A new buying works the shortage out again, so it buys nothing once the fridge has it all. The same `op_id` for another role or recipe: 409. The role's note about the groceries is written in the same transaction as the buying (both or neither) and pushed after it. A push that surely did not get out (`NOT_SENT`) is offered again by the next flush and by a retry of the same `op_id`; one whose result cannot be told (a connection broken half-way) counts as delivered and is not sent again, as [HOOKS.md](HOOKS.md) says. `{ok, added, text, missing, replayed}` (`missing` = what is still lacking). |
| `PUT /api/recipes/<id>/stop` `{stopped?, why?}` · `GET /api/recipes/stopped` | Take a recipe with a mistake out of picks and search (pots and pages stay); `stopped: false` puts it back. The list is `{recipes: [{id, name, why, at}]}`, newest first. |
| `GET /api/prefs?who=` · `POST /api/prefs/dislike` `{who, item}` · `DELETE /api/prefs/dislike/<item>?who=` | Ingredients not to recommend, one at a time (adding one already there or taking off one not there changes nothing); each answers the whole list and its version `{dislike, version}`. |
| `PUT /api/prefs` `{who, dislike: [item ids], version?}` | **Outdated** (use the one-at-a-time calls): replaces the whole list. With `version` from an earlier answer, only if the list is still that version (else 409, nothing changed); without it, whatever the list is now, so two pages can overwrite each other. |
| `GET /api/book?who=` · `DELETE /api/book/<page>?who=` | The role's pages (with tasting notes and menus when those are on). |
| `GET /api/orders?who=` · `POST /api/orders` `{who, recipe}` · `DELETE /api/orders/<id>?who=` | Ordering a dish; it moves on by itself (received → planned → cooking → done). |
| `GET /api/codes?who=&page=` · `POST /api/codes/preview` `{code}` · `POST /api/codes/import` `{who, code}` | A page as a code; previewing reads it as text only. |
| `GET /api/dex?who=` | The dish book: `{pages, silhouettes, totals, backfill, merges, achievements (all, for the human), drawing}`. Each page and silhouette carries `icon`, which of the fourteen pixel dishes stands in while there is no picture (the settled card's rules); `merges` lists `{dish, page_key}` for the unsorted dishes merged into a page. |
| `PUT /api/dex/note` `{who, page_key, text}` · `PUT /api/dex/merge` `{who, dish, page_key}` | The human's comment; merging a dish into a sorted page: `r:<id>` where `<id>` is a public recipe or a page of this role's own book (404 if there is none, or it is another role's; 409 if it was deleted or is a menu; a page is one target whatever its versions), or a `d:…` page that is not unsorted (409 for an unsorted one). Merging it onto `d:<dish>`, its own page, takes it back out. Chains left by older versions (a dish merged onto another unsorted dish that was merged on) are straightened when the book is read (under the write lock, only when there is one, never over a merge made in between) and on every merge. |
| `POST /api/dex/art/redraw` `{page_key}` · `PUT /api/dex/art/choice` `{page_key, version}` · `GET /api/dex/art?page_key=&version=` | Pictures (needs `[art] dish_provider`); every version is kept. |
| `GET /api/dishes?who=` · `PUT /api/dishes/settings` `{who, self_wash?, quota?}` | Plates: counts by state, the last washing (`job`: `id`, `state`, `started_at`, `per_s`, `n`, `ended_at`, and `breaks`, the plates of it already washed that broke, 0-based in washing order; a plate still to come is never listed), `machine_at` (when a plate last went into the dishwasher, null = never); whether the role washes, how many (null = all). The page plays the cook loading the dishwasher from `machine_at` (see [ANIMATION.md](ANIMATION.md#chores)); the washing-up itself plays on the washing card in the chat (next line). |
| `GET /api/dishes/jobs/<id>` | One washing, for the washing card: `{now, id, who, state, started_at, per_s, n, ended_at, counts: {washing, clean, broken, machine}, dishes: [{i, state, done_at}], timezone}`. `state` is `running`, `done` or `stopped`; a plate (`i` 0-based, in washing order) is `washing` until its time is up, then `clean` or `broken` (or `machine` when the washing was stopped before it), so which one will break is never told beforehand. Answered with plates switched off too (a card already in the chat then learns the washing was stopped); 404 for no such washing. |
| `GET /api/jars?who=` · `PUT /api/jars/cap` `{who, cap}` · `POST /api/jars/feed` `{who, name, key}` | The three jars, what came out of them, the daily cap; feeding one serving. `key` is required (400 without it): one per feeding, the same for a retry of it, so a retry feeds nothing more. |
| `GET /api/vendor?who=` · `GET /api/vendor/ledger?who=` | The vendor downstairs now (goods, prices, what is left), today's spending, the wallet, the sill, flower requests; the role's orders (`mine`: on the visit downstairs now, each with `item_id`, `kind`, `payer`, `state`, `created_at` and `updated_at`, which the page's vendor clips are played from). When no visit is live, `ended` may carry the visit that ended within the last two minutes (`id`, `vendor`, `leave_at`, goods without prices) with `mine` still its orders, so the page can finish showing an order and the vendor leaving; nothing can be bought from it. A live visit always comes first (then `ended` is null), and `ended` is not promised for the whole two minutes: a page must finish from what it last read if it stops coming. |
| `POST /api/vendor/treat` `{who, item_id, qty?, request_id}` | The human buys for the role (free for the role; only while the vendor is there). |
| `POST /api/vendor/flowers/<id>` `{approve}` · `POST /api/vendor/flowers/ready` `{name}` | Answering a flower request; marking an agreed kind as ready to be sold (`{changed}`: how many requests it moved on). |
| `GET /api/wallet?who=` · `POST /api/wallet/grant` `{who, amount, key, note?}` | The pocket money. Granting only with the built-in ledger (409 with your own wallet); `key` makes a retry grant nothing more; the role is told once. The ledger starts at 0 and nothing is paid in by itself. |

`GET /api/kitchen?session_id=` also returns `settlement` when the settled card is on:
`{has, outcome, link, dish, method, proficiency: {tier, n, before_tier, to_next, next_tier, tier_from} | null, mishap: {state, text} | null, stamps: [{key, text}]}`,
or `{has: false, why}` (`not_settled`, `cancelled`, `legacy`, `feature_off`).

---

# 中文：页面用的接口（REST）

所有地址都以 `/api` 开头，收发都是 JSON。设了 `server.token` 之后，除了 `/api/health`，每个请求都要带 `Authorization: Bearer <token>`。

用这些接口的厨房页由同一个服务在 `/page/` 提供（静态文件，不需要 token；见 [PAGE.md](PAGE.md)）。

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
| `POST /api/menu/{id}/feed` | 你把这道菜喂给他：划掉、算一顿、告诉他。返回 `{ok, row, outcome, text, notified}`；`notified` 为 false 表示没有给他留话（`notify.mode = "none"` 时）。已经吃过返回 409。 |
| `GET /api/meals?who=&since=` | 他从 `since`（秒数）起吃过的饭，早的在前：`{now, who, since, meals: [{id, meal, note, at}]}`。不写 `since` 就是今天（按 `server.timezone` 的零点起算）。零食和药剂不算一顿饭。 |

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
| `POST /api/inline` `{who, text, message_id?, told?}` | 执行一条回复里的方括号标签，返回每个标签的回执和去掉方括号行之后的正文。回执里的 `attachments` 是随回执带回的卡片，多数标签是空的；开始了一趟刷盘子的 `[刷盘子]` 会带一张刷盘子卡 `{kind: "kitchen_washing", job_id, who, n, per_s, started_at}`（见 [CONNECT.md](CONNECT.md) 和 [`web/README.md`](../web/README.md#刷盘子卡)）。同一个 `message_id` 再送一次，回的是同样的回执，卡片也在。`inline.enabled` 是 `false` 时返回 409；是 `"auto"` 时照常可用，第一次调用之后提示语就改成教他写方括号。 |

## 杂项

| 接口 | 说明 |
|---|---|
| `GET /api/health` | 活着没有。不需要 token。 |
| `GET /api/roles` | 目前有哪些角色。 |
| `GET /api/about` | 页面画东西之前要知道的事，只读：`{version, now, timezone, timezone_label, roles: {default, list}, switches: {stamina, satiety, worms, dev_clock, art}, words: {human_name, human_pronoun, app_name}, limits: {coupon_max, buy_max_items, hungry_below}}`。`roles.list` 是目前有的角色加上 `roles.allowed` 和默认角色。`switches` 说明哪些部分开着：`stamina` 为 false 时页面不显示体力，`satiety` 为 false 时不显示饱食度，`dev_clock` 为 true 时才出现快进；`art` 表示有没有接画图函数。 |
| `POST /api/scan` | 立刻做一次定时检查。 |
| `POST /api/dev/clock` `{advance_seconds?, reset?}` | 只有打开 `server.dev_clock` 才有：让时间往前走，途中照常检查。它拨的是整台服务的钟，库里所有角色一起跳——正在用的厨房别用。 |

## 这次升级

上面英文「The upgrade」一节逐条列了。每条都属于 `[play]` 里的某一样，那一样关着就回 409「这个玩法没开」（唯一例外：`GET /api/dishes/jobs/<id>` 给聊天里已有的刷盘子卡补读那一次刷盘子，盘子玩法关着也照样回答，好让卡知道刷盘子停了）；页面先读 `GET /api/features` 决定显示哪些入口。`GET /api/kitchen?session_id=` 在结算卡开着时多带一个 `settlement`（结算那一刻的成色、熟练度、小意外、印章，之后不变）。刷盘子卡从 `GET /api/dishes/jobs/<id>` 读回一趟刷盘子（哪只碎了、有没有被叫停、最后各几只）。
