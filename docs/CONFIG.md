# Settings

Settings are read from, in order of increasing priority:

1. built-in defaults;
2. a TOML file: `./kitchenette.toml`, or `--config FILE`, or the path in `KITCHENETTE_CONFIG`;
3. environment variables `KITCHENETTE_<SECTION>_<KEY>` (tables and lists as JSON).

`kitchenette check` prints the result, written the same way as the file
(`[fridge]` then `coupon_max = 3`), so anything it shows can be pasted into
your `kitchenette.toml`.

Mistakes are caught when the settings are read, by `kitchenette serve` and by
`kitchenette check` alike: an unknown section or key, a value of the wrong
kind (text where a number goes, `"no"` where `true`/`false` goes), a number
out of range, a time zone name that does not exist, a section written twice.
The answer is two lines, one in English and one in Chinese, naming the file,
the setting and what belongs there. A `KITCHENETTE_` environment variable
that is not a setting (a misspelt name) does not stop anything, but is pointed
out in one line together with the name it most resembles.

Two rules of the TOML format that trip people up: each `[section]` heading
may appear only once (put all of a section's lines under it), and text goes
in double quotes while numbers and `true`/`false` do not.

**Tables are merged, not replaced.** Where a setting is a table of
`key = value` lines (shelf life by category, the rest and work tables, the
gains), what you write is added to the built-in table entry by entry. Writing
only `leafy = 4` changes leafy greens and leaves the other categories alone.

Every number the rules use is in this one place. The tables below show the
defaults.

## `[server]`

| Key | Default | Meaning |
|---|---|---|
| `host` | `"127.0.0.1"` | Address to listen on. |
| `port` | `8765` | |
| `token` | `""` | Bearer token for `/api` and `/mcp`. Empty = no check. |
| `db_path` | `"kitchenette.db"` | The SQLite file. |
| `timezone` | `""` | IANA zone name. Empty = this machine's local time. Decides clock times in receipts, the snack day and the worm hour. |
| `timezone_label` | `""` | Written before reset times, e.g. `"JST "` gives "JST 04:00 重置". |
| `scan_interval_seconds` | `60` | How often pots are served, worms grow and notes are pushed. |
| `dev_clock` | `false` | Enables `POST /api/dev/clock` to fast-forward time. For demos only: it moves the clock of the whole server, so every role in the database jumps ahead. Never on a kitchen in use. |
| `cors_origins` | `[]` | Addresses of pages on other sites that may read `/api` from a browser, e.g. `["https://chat.example.com"]`. Needed when the cooking card sits on a page that is not served by this server. Empty = no other site may. |

## `[roles]`

| Key | Default | Meaning |
|---|---|---|
| `default` | `"companion"` | The role used when a tool call or request names none. |
| `allowed` | `[]` | Empty: any id is a role. Otherwise only these ids are accepted. |

A role is created by using it. Each has its own fridge, coupons, menu, snack
counts, satiety and stamina.

## `[words]`

| Key | Default | Meaning |
|---|---|---|
| `human_name` | `"用户"` | How sentences refer to the human: "【厨房·非用户发言】", "用户给你买了菜…". |
| `human_pronoun` | `"她"` | Pronoun for the human where one is used: "她给你挂的菜单". |
| `app_name` | `"App"` | What sentences call the place the human acts from: "(用户在 App 设的)". |

## `[inline]`

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `"auto"` | Whether the role acts by writing bracket lines (`[吃 菜名]`) that your chat program sends to `POST /api/inline`. `"auto"`: the kitchen's sentences name the matching tool until a reply has really been sent to `/api/inline`, then switch over by themselves to telling it to write the lines. `true`: always tell it to write them. `false`: always name the tool, and `/api/inline` is refused. See [CONNECT.md](CONNECT.md). |

## `[fridge]`

| Key | Default | Meaning |
|---|---|---|
| `coupon_max` | `3` | Coupons a role can hold. The human's hand-outs obey it too. |
| `buy_max_items` | `5` | Kinds one coupon buys. |
| `human_buy_max_items` | `30` | Most kinds the human can buy in one go from the page. A guard against a slipped tap, not a rule. |
| `clear_bad_after_days` | `3.0` | Spoiled food disappears this long after spoiling. |
| `burn_chance_meh` | `0.20` | Chance that a pot with stale ingredients burns. |
| `category_days` | leafy 2, meat 3, dairy 5, root 7, fruit 7, veg 5, staple_food 5 | Shelf life by category, in days. Merged: write only the ones you change. |
| `shelf_days` | (empty) | Shelf life of single items, by id or by name, winning over the category: `egg = 10`, `"番茄" = 9` (a Chinese key needs the quotes). |
| `staples` | 米 油 盐 酱油 | Always in stock, never counted. This is the list shown on the page. |
| `staple_aliases` | 米 大米 米饭 油 食用油 盐 酱油 生抽 老抽 糖 醋 水 | Names the role may write that all mean "a staple": skipped when buying or cooking instead of being refused as unknown. |
| `raw_edible` | strawberry apple milk cheese cucumber tomato | Edible straight from the fridge. |
| `hidden_freshness` | egg | The role sees only the purchase date of these, never their freshness. |
| `ingredients` | 33 items | The catalog. Replace it wholesale with `[[fridge.ingredients]]` tables: `id`, `name`, `category`, `pack_qty` (pieces per purchase), optional `shelf_days`, `aliases`. |

Freshness: under half the shelf life is fresh, up to the full shelf life is
stale, past it is spoiled.

## `[satiety]`

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `true` | The switch. Off: no satiety line, no hunger, meals do not fill. |
| `max` | `100` | The top of the scale. Satiety never goes above it. |
| `init` | `60` | Where a new role starts (0-100). |
| `decay_per_hour` | `9` | |
| `hungry_below` | `30` | Under this the role is told once, and the per-turn line appears. |
| `dizzy_hours` | `2.5` | How long a spoiled dish leaves the role dizzy. |
| `gain` | great 45, ok 40, her 40, burnt 15, spoiled 0, raw 15, raw_meh 12 | Satiety per meal by how it turned out (`her` = a dish the human put up; `raw` = straight from the fridge). |
| `snack_gain` | high 12, mid 8, low 5 | Satiety per snack by tier. |

## `[kitchen]`

| Key | Default | Meaning |
|---|---|---|
| `minutes_min` / `minutes_max` | `1` / `1440` | Allowed cooking time. |
| `worm_enabled` | `true` | Whether leftovers and spoiled fruit grow worms. |
| `worm_day_hour` | `4` | A dish left on the table grows worms once it has passed this local hour… |
| `worm_min_age_hours` | `6.0` | …and has been sitting at least this long. |
| `menu_giveup_seconds` | `600` | If a served dish cannot be put on the menu for this long, the role is told so. |
| `menu_retry_max_seconds` | `86400` | After this long the kitchen stops trying to put that dish on the menu. |

Example: `examples/worms-and-quiet.toml`.

## `[snacks]`

| Key | Default | Meaning |
|---|---|---|
| `day_boundary_hour` | `4` | Daily counts reset at this local hour. |
| `cap_min` / `cap_max` | `0` / `20` | Range the human may set a daily cap to. 0 = not served today. |
| `catalog` | coffee (4 flavours), jelly, pudding, chocolate, cookie | `id`, `name`, `tier`, `gain` (stamina per serving), `default_cap`, optional `variants`, `aliases`. |

## `[stamina]`

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `true` | The switch. Off: no stamina anywhere; potions cannot be used. |
| `init` | `0.7` | Where a new role starts (0-1). |
| `tau_hours` | `2.5` | How quickly stamina drifts toward the current hour's level. |
| `schedule` | `"night-owl"` | The daily rhythm: the name of a built-in one (`"night-owl"`, `"early-bird"`, `"no-sleep"`) or 24 values of your own, one per local hour. See below. |
| `cost_base` | `0.02` | A round containing any work costs this… |
| `cost_per_kind` | `0.04` | …plus this per distinct kind of work… |
| `cost_cap` | `0.20` | …up to this. |
| `recharge_cap` | `0.25` | The most one round (or one snack) can restore. |
| `rest` | eat 0.10, take_bath 0.08, music_play 0.06, read_pages 0.06 | Tool name → stamina restored. |
| `work` | the four `kitchen_*` tools → `"kitchen"` | Tool name → kind of work. |
| `outcome_delta` | great +0.02, ok 0, burnt −0.07, spoiled −0.15, raw −0.05, raw_meh −0.05 | Added on top of the meal itself, by how the dish turned out. |
| `auto_account` | `true` | Settle this server's own tool calls as they happen. |
| `auto_round_seconds` | `120` | Calls this close together count as one round. |
| `sleep_debt` | `false` | Let reported sleep scale the schedule. See [HOOKS.md](HOOKS.md). |

### The daily schedule

There is no built-in idea of when a companion sleeps. The schedule is the
level stamina drifts toward at each hour of the day. Pick one by name:

```toml
[stamina]
schedule = "early-bird"
```

| Name | Shape |
|---|---|
| `"night-owl"` | Up until 02:00, recovering 02:00-09:00. The default. |
| `"early-bird"` | Sleepy after 21:00, recovering 00:00-09:00, sharpest in the morning. |
| `"no-sleep"` | The same level (0.80) all day: no sleeping habit at all. |

Or write your own: 24 numbers between 0 and 1, for hours 0 to 23.

```toml
[stamina]
schedule = [0.6, 0.55, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.9, 0.85, 0.85,
            0.85, 0.85, 0.75, 0.75, 0.75, 0.75, 0.7, 0.7, 0.7, 0.65, 0.65, 0.65]
```

`examples/schedules/` shows what writing one looks like, with a comment per
stretch of the day: the three named ones spelled out, and `blank.toml` with
one line per hour to fill in. The `schedule` line goes under the one
`[stamina]` heading your file already has; a second `[stamina]` is an error.

### Rest and work

Talking costs nothing. What costs or restores stamina is which tools the role
used, and you decide which is which. Names match exactly or as the tail of
`server__tool`. A tool in neither table is free. Example with comments:
`examples/rest-and-work.toml`.

```toml
[stamina.rest]
eat = 0.10
take_bath = 0.08

[stamina.work]
send_email = "errand"
web_search = "research"
```

What you write is added to the built-in tables. To take a built-in entry out,
set it to `0` in the rest table or `""` in the work table.

### Switches

`examples/switches.toml` turns both stamina and satiety off. With one off, how
a dish turns out only moves the other. With both off the kitchen is purely
for fun: buy, cook, wait, eat, and leftovers still grow worms.

## `[coupons]`

| Key | Default | Meaning |
|---|---|---|
| `earn` | (empty) | Tool name → the word for what was made. A successful call earns one coupon. Empty: no tool earns one. |
| `earn_hint` | `""` | The clause shown when the role is out of coupons, followed by "就得一张。" Empty = say nothing. |

Out of the box nothing earns a coupon: the kitchen cannot know which tools
your companion has, and telling it "write a diary entry to get one" when it
has no way to write one would be a dead end. Until you fill this in, coupons
come from the human, who can always hand one out from the page.

`examples/coupons.toml` is one household's setup to copy and change: finishing
a diary entry, a book excerpt or a travelogue earns a coupon each.

```toml
[coupons]
earn_hint = "写成一篇日记"

[coupons.earn]
write_diary = "日记"
```

Coupons are granted when you report rounds (`POST /api/rounds/settle`) or
directly with `POST /api/coupons/earn`.

## `[notify]`

| Key | Default | Meaning |
|---|---|---|
| `mode` | `"queue"` | `queue`, `webhook`, `both` or `none`. |
| `webhook_url` | `""` | Where notes are POSTed in `webhook` / `both` mode. |
| `webhook_token` | `""` | Sent as a bearer token with each POST. |
| `quiet_hours` | `[]` | Local-time windows such as `"02:00-06:30"` during which pushes are held. Empty = never held. |
| `respect_sleep` | `false` | Also hold pushes while the role is reported asleep. |

## `[art]`

| Key | Default | Meaning |
|---|---|---|
| `provider` | `""` | `"module:function"` that draws pictures for ingredient kinds added from the page. Empty = text cards. |
| `dir` | `"art"` | Where drawn pictures are stored. |

---

# 中文：设置

设置从三个地方读，后面的盖住前面的：

1. 内置的默认值；
2. 一个 TOML 文件：当前文件夹下的 `kitchenette.toml`，或启动时 `--config 文件`，或环境变量 `KITCHENETTE_CONFIG` 指的那个文件；
3. 环境变量 `KITCHENETTE_<段名>_<键名>`（表格和列表用 JSON 写）。

`kitchenette check` 会打印最终生效的每一项，写法和文件里一样（先 `[fridge]`，再 `coupon_max = 3`），所以它打印出来的任何一行都可以直接抄进你的 `kitchenette.toml`。

填错了会在读设置的时候就拦下，`kitchenette serve` 和 `kitchenette check` 都一样：段名或键名不认识、值的种类不对（该填数字的地方填了字、该填 `true` / `false` 的地方填了 `"no"`）、数字超出范围、时区名不存在、同一个段写了两次。报错只有两行，中英各一句，写明哪个文件、哪一项、应该填什么。环境变量名写错（以 `KITCHENETTE_` 开头、但不是任何一项设置）不会拦住启动，但会打一行提醒，并告诉你最像的是哪一个。

**表格是合并，不是替换。** 有些设置是一张表（一行一个 `键 = 值`，比如每一类能放几天、休息表、干活表、吃一顿涨多少）。你写的会逐项并进内置的表里：只写一行 `leafy = 4`，改的就只有叶菜，其他类别不动。

**怎么填**：TOML 文件按「段」分块。方括号里是段名，下面一行一项，等号左边是键名，右边是值。文字要加英文双引号，数字和 `true` / `false` 不加。只写你想改的，没写的保持默认。例如：

两条最容易踩的规矩：**每个 `[段名]` 只能出现一次**，同一段的内容都写在它下面（照着文档往文件里再贴一段 `[stamina]`，而文件里已经有一个 `[stamina]` 了，就会报错——把新的那几行并到已有的那一段里）；键名如果是中文，要加英文双引号，如 `"番茄" = 9`。

```toml
[fridge]
coupon_max = 5

[words]
human_name = "阿青"
```

规则用到的每一个数字都在这一个地方。下面各表里的「默认」就是不写时的值。

## `[server]` 服务本身

| 键 | 默认 | 是什么 |
|---|---|---|
| `host` | `"127.0.0.1"` | 在哪个地址上提供服务。默认只有本机能连；要让别的电脑连，填 `"0.0.0.0"` 并设 token。 |
| `port` | `8765` | 端口号。被别的程序占了就换一个。 |
| `token` | `""` | 访问口令。留空表示不检查；填了之后，页面和模型访问时都要带上它。对外开放时一定要填。 |
| `db_path` | `"kitchenette.db"` | 数据存在哪个文件里。 |
| `timezone` | `""` | 时区，写成 `"Asia/Shanghai"` 这种名字。留空就用这台电脑的时区。回执里的钟点、零食每天几点清零、剩菜几点算「过夜」都看它。 |
| `timezone_label` | `""` | 写在清零时间前面的字。填 `"北京时间 "` 就会显示「北京时间 04:00 重置」。留空不显示。 |
| `scan_interval_seconds` | `60` | 每隔多少秒检查一次：有没有锅到点、剩菜长没长虫、有没有话要推出去。 |
| `dev_clock` | `false` | 打开后可以让时间快进，只给演示和试玩用：它拨的是整台服务的钟，库里所有角色会一起往前跳。正在用的厨房千万别开。 |
| `cors_origins` | `[]` | 允许哪些别的网站上的页面从浏览器里读 `/api`，写成 `["https://chat.example.com"]` 这样的地址列表。做饭卡放在不是这个服务自己提供的页面上时要填，不填浏览器会拦住。留空表示别的网站都不行。 |

## `[roles]` 角色

| 键 | 默认 | 是什么 |
|---|---|---|
| `default` | `"companion"` | 没说是谁的时候算谁。只有一个小机的话，把他的名字填这里，以后就不用每次都说。 |
| `allowed` | `[]` | 留空：任何名字都可以是一个角色，用到就自动有了。填了名单（如 `["mika", "noah"]`）：只认名单里的。 |

每个角色有自己的冰箱、买菜券、菜单、零食计数、饱食度和体力，互相看不到。

## `[words]` 称呼

| 键 | 默认 | 是什么 |
|---|---|---|
| `human_name` | `"用户"` | 厨房说话时怎么称呼你。填 `"阿青"`，句子就是「【厨房·非阿青发言】」「阿青给你买了菜…」。 |
| `human_pronoun` | `"她"` | 提到你时用的代词，比如「她给你挂的菜单」。按你的情况改成「他」或别的。 |
| `app_name` | `"App"` | 句子里怎么称呼你操作的那个地方，比如「(用户在 App 设的)」。你用的是网页就可以填 `"厨房页"`。 |

## `[inline]` 方括号标签

| 键 | 默认 | 是什么 |
|---|---|---|
| `enabled` | `"auto"` | 他是不是靠在回复里单独写一行 `[吃 菜名]` 这样的方括号标签来做事（需要你的聊天程序把回复送到 `/api/inline`）。可以填三种值：`"auto"`＝自动，先让提示语指向对应的工具，等真的有回复送进 `/api/inline` 之后自己改成教他写标签；`true`＝一直教他写标签；`false`＝一直指向工具，`/api/inline` 拒绝请求。详见 [CONNECT.md](CONNECT.md)。 |

## `[fridge]` 冰箱

| 键 | 默认 | 是什么 |
|---|---|---|
| `coupon_max` | `3` | 买菜券最多攒几张。你发的券也受这个上限管。 |
| `buy_max_items` | `5` | 一张券一次最多买几样。 |
| `human_buy_max_items` | `30` | 你在页面上一次最多能给他买几样。只是防手滑，不是规则。 |
| `clear_bad_after_days` | `3.0` | 东西坏了之后再过几天会自动消失。 |
| `burn_chance_meh` | `0.20` | 用了不太新鲜的食材时，这一锅糊掉的可能性。`0.20` 就是五次里大约一次。 |
| `category_days` | 叶菜 2、肉和海鲜 3、蛋奶豆 5、根茎 7、水果 7、其他蔬菜 5、主食 5 | 每一类能放几天。只写你要改的那几类就行。键名见下面的「类别的键名」。 |
| `shelf_days` | 空 | 单独指定某一样能放几天，比类别的设置优先。左边写它的 id 或名字：`egg = 10`、`"番茄" = 9`（中文名字要加英文双引号）。 |
| `staples` | 米、油、盐、酱油 | 常备品：一直都有，不用买，不会坏。页面上显示的就是这几样。 |
| `staple_aliases` | 米、大米、米饭、油、食用油、盐、酱油、生抽、老抽、糖、醋、水 | 他可能写出来的、都算「常备品」的叫法。买菜或下锅时写到这些会被直接跳过，不会被当成「不认得」而拒绝。 |
| `raw_edible` | 草莓、苹果、牛奶、奶酪、黄瓜、番茄 | 不用开锅、能从冰箱直接拿出来吃的。 |
| `hidden_freshness` | 鸡蛋 | 这几样他看不出新不新鲜，只看得到是哪天买的。 |
| `ingredients` | 33 样 | 能买的东西的清单。想整份换掉，用一组 `[[fridge.ingredients]]` 来写：`id`（英文代号）、`name`（名字）、`category`（哪一类）、`pack_qty`（买一次是几个），还可以写 `shelf_days`（单独指定能放几天）和 `aliases`（别名）。 |

新鲜度怎么算：放了不到「能放天数」的一半是新鲜，没超过是不太新鲜，超过就是坏了。

**类别的键名**（写 `[fridge.category_days]` 时左边要用这些英文代号；在页面上添食材时，填代号或中文名都认）：

| 键名 | 是哪一类 |
|---|---|
| `leafy` | 叶菜 |
| `veg` | 蔬菜 |
| `root` | 根茎 |
| `dairy` | 蛋奶豆 |
| `meat` | 肉和海鲜 |
| `staple_food` | 主食 |
| `fruit` | 水果 |

```toml
[fridge.category_days]
leafy = 3              # 只改叶菜，其他类别不变

[fridge.shelf_days]
egg = 10               # 只改鸡蛋这一样
"番茄" = 9
```

## `[satiety]` 饱食度

| 键 | 默认 | 是什么 |
|---|---|---|
| `enabled` | `true` | 开关。关掉后：不显示饱食度、不会饿、吃了也不涨。 |
| `max` | `100` | 饱食度的满格是多少。再怎么吃也不会超过它。 |
| `init` | `60` | 新角色一开始的饱食度（0 到 100）。 |
| `decay_per_hour` | `9` | 每小时掉多少。 |
| `hungry_below` | `30` | 低于这个数算「饿了」：提醒他一次，状态行里也会有一句。 |
| `dizzy_hours` | `2.5` | 吃了坏掉的菜之后晕几个小时。 |
| `gain` | 很好 45、普通 40、你挂的菜 40、糊了 15、坏了 0、直接吃 15、直接吃但不太新鲜 12 | 吃一顿涨多少，按这道菜做得怎么样分。对应的键名是 `great`、`ok`、`her`、`burnt`、`spoiled`、`raw`、`raw_meh`。 |
| `snack_gain` | 高档 12、中档 8、低档 5 | 吃一份零食涨多少，按档次分。键名 `high`、`mid`、`low`。 |

## `[kitchen]` 做饭与剩菜

| 键 | 默认 | 是什么 |
|---|---|---|
| `minutes_min` / `minutes_max` | `1` / `1440` | 一锅最短、最长能做多少分钟。 |
| `worm_enabled` | `true` | 剩菜和坏掉的水果会不会长虫。不想要这个玩法就填 `false`。 |
| `worm_day_hour` | `4` | 桌上的菜过了每天的这个钟点（0 到 23）…… |
| `worm_min_age_hours` | `6.0` | ……并且已经放了至少这么多小时，就会长虫。两个条件要同时满足。 |
| `menu_giveup_seconds` | `600` | 出锅后如果这么久都没能挂上菜单，就如实告诉他「菜单这次没挂上」。一般不用动。 |
| `menu_retry_max_seconds` | `86400` | 出锅后超过这么久（默认一天）还没挂上，厨房就不再试了。一般不用动。 |

例子：`examples/worms-and-quiet.toml`。

## `[snacks]` 零食架

| 键 | 默认 | 是什么 |
|---|---|---|
| `day_boundary_hour` | `4` | 每天几点把「今天吃了几份」清零。 |
| `cap_min` / `cap_max` | `0` / `20` | 你在页面上调每日上限时，能调的范围。调成 0 就是今天不供应。 |
| `catalog` | 咖啡（四种口味）、果冻、布丁、巧克力、曲奇 | 零食清单。每样有 `id`、`name`、`tier`（档次）、`gain`（一份回多少体力）、`default_cap`（默认每天几份），还可以有 `variants`（口味）和 `aliases`（别名）。 |

## `[stamina]` 体力

| 键 | 默认 | 是什么 |
|---|---|---|
| `enabled` | `true` | 开关。关掉后到处都没有体力，药剂也用不了。 |
| `init` | `0.7` | 新角色一开始的体力（0 到 1，1 是满）。 |
| `tau_hours` | `2.5` | 体力向「这个钟点该有的水平」靠拢得多快。数字越小靠得越快。 |
| `schedule` | `"night-owl"` | 作息：填一个预设的名字（`"night-owl"` 夜猫、`"early-bird"` 早睡早起、`"no-sleep"` 不睡觉），或者自己写 24 个数（0 点到 23 点每小时一个）。见下面。 |
| `cost_base` | `0.02` | 一轮里只要干了活，先扣这么多…… |
| `cost_per_kind` | `0.04` | ……每多一种活再扣这么多…… |
| `cost_cap` | `0.20` | ……一轮最多扣这么多。 |
| `recharge_cap` | `0.25` | 一轮（或一份零食）最多回这么多。 |
| `rest` | 吃饭 0.10、洗澡 0.08、听歌 0.06、读书 0.06 | 「休息表」：哪些工具算休息、各回多少。见下面。 |
| `work` | 厨房的四个工具都算「kitchen」这一种活 | 「干活表」：哪些工具算干活、算哪一种。见下面。 |
| `outcome_delta` | 很好 +0.02、普通 0、糊了 −0.07、坏了 −0.15、直接吃 −0.05 | 吃厨房做的菜时，在「吃饭」本身之外，按做得怎么样再加或再扣。 |
| `auto_account` | `true` | 厨房自己的工具，调用时当场记体力账。一般保持开着。 |
| `auto_round_seconds` | `120` | 这么多秒之内连着调的几次工具算同一轮，不重复扣。 |
| `sleep_debt` | `false` | 缺觉会不会拉低体力。默认不会；要接见 [HOOKS.md](HOOKS.md)。 |

### 作息表

厨房不替你决定他几点睡。作息说的是「每个钟点，体力会慢慢靠向多少」。最省事的是直接填一个预设名：

```toml
[stamina]
schedule = "early-bird"
```

| 预设名 | 样子 |
|---|---|
| `"night-owl"` | 夜猫：熬到两点，两点到九点恢复。这是默认值。 |
| `"early-bird"` | 早睡早起：晚上九点后犯困，零点到九点恢复，早上最精神。 |
| `"no-sleep"` | 不睡觉：全天同一个水平（0.80），没有作息。 |

也可以自己写：24 个 0 到 1 之间的数，依次是 0 点到 23 点。他睡觉或休息的钟点填高一点（比如 0.95），通常很累的钟点填低一点（比如 0.55）。

```toml
[stamina]
schedule = [0.6, 0.55, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.9, 0.85, 0.85,
            0.85, 0.85, 0.75, 0.75, 0.75, 0.75, 0.7, 0.7, 0.7, 0.65, 0.65, 0.65]
```

`examples/schedules/` 里是「自己写一份」的样子，按时段带着注释：三个预设各写开了一份，另有一份 `blank.toml` 每小时一行等你填。注意 `schedule` 这一行要写进你文件里**已有的那一个** `[stamina]` 段下面；再写第二个 `[stamina]` 会报错。

### 休息表和干活表

聊天不花体力。花体力还是回体力，看的是他这一轮用了哪些工具，哪个算哪种由你定。表里左边写工具名（和你的模型调用时的名字一样；如果名字是 `服务名__工具名` 这种，只写后半段也认）。两张表里都没有的工具，不扣也不回。带注释的例子：`examples/rest-and-work.toml`。

```toml
[stamina.rest]          # 休息表：工具名 = 回多少体力
eat = 0.10
take_bath = 0.08

[stamina.work]          # 干活表：工具名 = "哪一种活"（名字随你起，同一种一轮只扣一次）
send_email = "跑腿"
web_search = "查资料"
```

你写的会逐项并进内置的表里。想去掉内置的某一项：休息表里把它填成 `0`，干活表里把它填成 `""`。

### 两个开关

`examples/switches.toml` 把体力和饱食度都关了。只关一个时，菜做得好不好只影响还开着的那一个。两个都关，厨房就纯粹是玩：买菜、做饭、等、吃，剩菜照样会长虫。

## `[coupons]` 做什么能换买菜券

| 键 | 默认 | 是什么 |
|---|---|---|
| `earn` | 空 | 左边是工具名，右边是「做出来的是什么」（会写进厨房记录里，如「写了一篇日记,得一张买菜券」）。这个工具成功调用一次，就得一张券。留空＝没有任何工具能换券。 |
| `earn_hint` | `""` | 他没券的时候，提示里怎么说「怎样能得券」（后面会接「就得一张。」）。要和上面那张表说的是同一回事；留空就不提。 |

开箱时什么都换不了券：厨房不知道你的小机有哪些工具；他明明没有写日记的工具，却被告知「写成一篇日记就得一张」，那是一条走不通的路。在你填这一段之前，券只能由你发——你随时可以在页面上发。

`examples/coupons.toml` 是一户人家的配法，可以照着改：写完一篇日记、一篇书摘或一篇游记，各得一张券。最小的写法是：

```toml
[coupons]
earn_hint = "写成一篇日记"

[coupons.earn]
write_diary = "日记"
```

券是在你上报一轮（`POST /api/rounds/settle`）时发的，也可以直接调 `POST /api/coupons/earn` 发。

## `[notify]` 怎么通知他

| 键 | 默认 | 是什么 |
|---|---|---|
| `mode` | `"queue"` | `"queue"`：话排着队等他来取。`"webhook"`：一有事就发到你指定的网址。`"both"`：两样都做。`"none"`：不通知。 |
| `webhook_url` | `""` | 选了 `webhook` 或 `both` 时，发到哪个网址。 |
| `webhook_token` | `""` | 发的时候带上的口令（可不填）。 |
| `quiet_hours` | `[]` | 「别吵」的时段，如 `["02:00-06:30"]`，可以写好几段，可以跨过零点。时段内的通知会等到时段结束再发。留空表示随时都发——没有睡觉习惯的小机就留空。 |
| `respect_sleep` | `false` | 他被报告为「睡着」时也先不发，等醒了再发。需要你另外告诉厨房他睡没睡，见 [HOOKS.md](HOOKS.md)。 |

## `[art]` 给新添的食材画小图

| 键 | 默认 | 是什么 |
|---|---|---|
| `provider` | `""` | 留空：你在页面上新添的食材只显示名字（字卡）。想要小图，这里填一个画图函数的位置，写成 `"模块:函数"`，见 [HOOKS.md](HOOKS.md)。 |
| `dir` | `"art"` | 画好的图存在哪个文件夹。 |
