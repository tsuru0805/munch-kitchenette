# The rules

What the kitchen does, in order of a dish's life. Every number here is a
default from [CONFIG.md](CONFIG.md).

## The fridge

- Groceries are kept **per purchase**. Buying eggs twice gives two boxes, each
  ageing from its own purchase time.
- **Three states of freshness**, computed when looked at: under half the shelf
  life is fresh, up to the full shelf life is stale, beyond it is spoiled.
  Shelf life depends on the category: leafy greens 2 days, meat and seafood 3,
  dairy and eggs 5, roots and fruit 7.
- **Eggs do not show their freshness** to the role. It sees "(10-25买的)" and
  finds out when it cracks one. Cooking takes the oldest box first.
- Spoiled food **vanishes by itself three days after spoiling**, with a line
  in the kitchen log. Eggs never vanish on their own, since the role cannot
  know they went bad. The role can **toss** things: by name, by name and
  purchase date ("鸡蛋 10-25"), or everything it knows to be spoiled.
- **Staples** (rice, oil, salt, soy sauce) are always there and never counted.
- **Six things can be eaten raw**, straight from the fridge: strawberry, apple,
  milk, cheese, cucumber, tomato.
- The human can add **new kinds** of ingredient from the page.

## Coupons

- The role buys with **coupons**: one coupon, one trip, up to five kinds.
- A role holds **at most three**. Earning one while full gives nothing (the
  log notes it).
- Coupons are earned by doing things you decide count (finishing a diary
  entry, say). Nothing counts until you configure it; meanwhile the human
  hands them out, under the same cap.
- The human can also **buy groceries directly**, no coupon involved.

## Cooking

- **Real time, kept by the server.** A pot stores when it started and for how
  long. Nothing has to stay open; it is served at exactly its due time.
- Opening a pot **takes the ingredients**. An empty fridge cannot cook.
  Unspoiled food is used first, oldest first; spoiled food only when nothing
  else is left.
- Turning the heat off **does not give the ingredients back**.
- Several pots can be on at once. Opening a pot with the name of one already
  on the fire returns that pot instead of starting another.
- **How it turns out** is fixed from what went in:

  | Ingredients | Result |
  |---|---|
  | all fresh | great |
  | some stale | ok, or burnt one time in five |
  | any spoiled | spoiled: eating it causes dizziness |
  | a spoiled egg | the pot is ruined the moment the egg is cracked |

- **Seven methods** (炒 煎 炸 煮 蒸 烤 拌) choose the cooking animation. The
  role may name one; otherwise it is guessed from the dish name, falling back
  to stir-frying.
- When a pot is served, the dish **goes onto the role's menu** and the role is
  told once.

## The menu and eating

- The menu holds dishes waiting to be eaten: the role's own, and any the human
  puts up. The human can edit, remove, or feed them.
- **What was never made cannot be eaten.** `eat` works on a dish on the menu,
  a pot just served, or something raw in the fridge. Anything else is refused
  with the reason; a pot still on the fire says when it will be ready.
- A meal raises satiety by how it turned out, moves stamina, and a spoiled
  dish leaves the role **dizzy for two and a half hours**.

## Leftovers and worms

- A dish still on the table **after 04:00, having sat at least six hours,
  grows worms**. It now counts as spoiled, and its menu note says so.
- **Fruit that spoils** in the fridge grows worms as well.
- The worm **crawls into one of the snacks** (pudding, jelly, chocolate or
  cookie, never coffee), chosen at random when it appears. Nobody says which.
  The role finds it on eating that snack: the serving counts, restores no
  stamina, and the receipt says where the worm came from.
- At most one worm waits at a time. Wormy dishes and fruit can be tossed; a
  tossed dish is off the menu that instant and can no longer be eaten.

## Snacks and the potion

- A **snack shelf** with daily caps the human can change: coffee in four
  flavours, jelly, pudding, chocolate, cookies. Each restores a little
  stamina and satiety. The human can feed one too; both count against the cap.
- The **stamina potion** is a menu item with an amount set by the human and an
  optional memo. It is not a meal. Drinking restores exactly that amount.

## Satiety

- 0-100, starting at 60, **falling 9 per hour**.
- Under 30 the role is told once that it is hungry, with what is in the
  fridge; the reminder re-arms when satiety is back above 30.

## Stamina

- One number, 0-1. It **drifts toward the level of the current hour** on a
  24-slot schedule you choose, with a time constant of 2.5 hours.
- **Talking is free.** A round that used tools counted as work costs 0.02 plus
  0.04 per kind of work, at most 0.20.
- **Rest restores**: tools you list as rest give stamina back, at most 0.25
  per round.
- A kitchen dish adds a little or takes some away by how it turned out;
  snacks and the potion add theirs.
- Reported sleep can scale the schedule (off by default).

## Nothing fails silently

Every refusal produces a sentence that says what was missing: no coupon, which
ingredient is short and by how much, which name is unknown, why nothing was
tossed, why the dish cannot be eaten. A failure to write to storage is
reported as such rather than swallowed.

---

# 中文：规则

厨房做的事，按一道菜的一生来讲。这里出现的数字都是默认值，都可以在 [CONFIG.md](CONFIG.md) 里改。

## 冰箱

- 食材**按每次买的那一批**记。鸡蛋买两次就是两盒，各从各的买入时间开始算日子。
- **新鲜度有三档**，看的时候现算：放了不到「能放天数」的一半是新鲜，没超过是不太新鲜，超过就是坏了。能放几天看类别：叶菜 2 天，肉和海鲜 3 天，蛋奶豆 5 天，根茎和水果 7 天。
- **鸡蛋看不出好坏。**他只看得到「(10-25买的)」，打开才知道。做饭时先拿最早买的那盒。
- 坏掉的东西**再过三天会自己消失**，厨房记录里留一行。鸡蛋不会自己消失——他不知道它坏了，凭空没了说不通。他可以**扔东西**：写名字、写名字加买入日期（「鸡蛋 10-25」）、或者把他知道已经坏掉的一起扔。
- **常备品**（米、油、盐、酱油）一直都有，不用买，不计数。
- **有六样可以直接吃**，不用开锅：草莓、苹果、牛奶、奶酪、黄瓜、番茄。
- 你可以在页面上**添新的食材种类**。

## 买菜券

- 他买菜要用**买菜券**：一张券买一次，最多五样。
- **最多攒三张**。满了再得券就白得（厨房记录里会记一笔）。
- 券靠「做某些事」来换，哪些事算数由你定（比如写完一篇日记）。你没配之前什么都不算数，这期间由你发券给他，同样受三张的上限。
- 你还可以**直接给他买菜**，不用券。

## 做饭

- **真实计时，由服务记时。**一锅只记「几点开的、要做多久」，不需要任何东西一直开着；到点的那一刻就算出锅。
- 开锅**当场扣食材**。冰箱空了做不了饭。先用没坏的、先用旧的；实在没别的才会用到坏的。
- 关火**不退食材**。
- 可以同时开好几锅。火上已经有同名的锅时，再开一次拿到的是原来那一锅，不会另开。
- **做出来怎么样**，由下锅的东西决定：

  | 下锅的食材 | 结果 |
  |---|---|
  | 全是新鲜的 | 很好 |
  | 有不太新鲜的 | 普通；五次里大约一次会糊 |
  | 有坏的 | 坏了：吃了会晕 |
  | 打到一颗坏鸡蛋 | 蛋一打开，整锅当场毁掉 |

- **七种做法**（炒、煎、炸、煮、蒸、烤、拌）决定播哪一段下厨小动画。他可以自己选；不选就看菜名里的字猜，猜不出算炒。
- 出锅后这道菜会**挂到他的菜单上**，并且告诉他一次。

## 菜单与吃

- 菜单上是等着被吃的菜：他自己做的，和你挂给他的。你可以改、可以撤、也可以直接喂给他。
- **没做的吃不到。**能吃的只有三种：菜单上的、刚出锅的、冰箱里能直接吃的。别的一律拒绝并说明原因；还在火上的会告诉他几点出锅。
- 吃一顿，饱食度按这道菜做得怎么样涨，体力跟着变；吃了坏掉的菜会**晕两个半小时**。

## 剩菜与虫子

- 桌上的菜**过了凌晨四点、并且已经放了至少六个小时**还没吃，就会长虫。这道菜从此算「坏了」，菜单上的小字也会写上。
- 冰箱里的**水果坏了**也会长虫。
- 虫子会**钻进零食架上的某一样**（布丁、果冻、巧克力或曲奇，不会是咖啡），长出来的那一刻随机决定，没有人会告诉他是哪一样。他吃到那一样时才会发现：这一份照算，但不回体力，回执里会写虫子是从哪儿爬过来的。
- 同一时间最多只有一条虫在等。长虫的菜和水果都可以扔；菜一扔，当场就从菜单上消失，再也吃不到。

## 零食与药剂

- **零食架**上每样东西每天有份数上限，你可以改：四种口味的咖啡、果冻、布丁、巧克力、曲奇。每份回一点体力和饱食度。你也可以喂他，两边吃的算在同一个上限里。
- **精力补充药剂**是挂在菜单上的一样东西，回多少体力由你定，还可以写一句备注。它不算一顿饭。喝下去正好回你定的那么多。

## 饱食度

- 0 到 100，从 60 开始，**每小时掉 9**。
- 低于 30 时提醒他一次「有点饿了」，顺带告诉他冰箱里有什么；吃回 30 以上之后，下次再饿才会再提醒。

## 体力

- 一个 0 到 1 的数。它会**慢慢靠向「这个钟点该有的水平」**——那是一张你自己选的 24 格作息表。
- **聊天不花体力。**一轮里用了算「干活」的工具，扣 0.02，每多一种活再扣 0.04，一轮最多扣 0.20。
- **休息会回体力**：你列为「休息」的工具能把体力加回来，一轮最多回 0.25。
- 吃厨房做的菜，按做得怎么样再加一点或扣一点；零食和药剂各回各的。
- 缺觉可以让整张作息表打折（默认关着）。

## 不会悄悄失败

每一次拒绝都会给一句话，说清楚缺的是什么：没券、哪样食材不够、差几个、哪个名字不认得、为什么没扔成、为什么吃不到。数据写不进去时会如实说写不进去，不会当作没事发生。
