# The cook on the card

[中文在下面](#卡上的小厨师)

When your companion starts a pot, a card appears in the chat and counts down in real time. A small cook stands on the card's top edge and actually cooks: washes his hands, chops, works the pan, tastes, and brings the dish out when the time is up. Or burns it.

| A pot that turns out well | A pot that burns |
|---|---|
| <img src="animation/card-served.gif" width="406" alt="The card counts down, the cook tosses the pan, tastes, then holds up the plate; the card reads served"> | <img src="animation/card-burnt.gif" width="406" alt="The card counts down, the cook deep-fries, tastes, then smoke rises; the card reads burnt"> |

> **Unofficial fan work.** The cook is Clawd, a character created by Anthropic for Claude Code; all rights in the character and in the names "Clawd", "Claude", "Claude Code" and "Anthropic" belong to Anthropic, PBC. This project is not affiliated with, sponsored by or endorsed by Anthropic. The cook is drawn with the engine of [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) (animation and engine by Luin Luinaris, postie concept and pixel corrections by Charlie Luinaris); the chef outfits and cooking moves are additions made for this project. The images are CC BY-NC-SA 4.0, non-commercial only. Full credits: [`assets/clawd/ATTRIBUTION.md`](../assets/clawd/ATTRIBUTION.md).

## One pot, from start to finish

Every clip is 3 seconds long (45 frames) and starts from the same standing pose, so any clip can follow any other without a jump.

| Segment | What he does | When it plays |
|---|---|---|
| entrance | Rises from behind the card's top edge with a small bounce. | Once, when the page first sees a pot that started within the last 5 minutes. |
| `wash` <br><img src="animation/wash-toque.gif" width="135" alt="wash"> | Washes his hands in a basin and shakes them dry. | Once, for 3 seconds, right as he comes on. Skipped for dishes shorter than 3 minutes, and never replayed when the card is shown again. |
| `chop` <br><img src="animation/chop-scarf.gif" width="135" alt="chop"> | Chops a carrot on a board. | The first 20% of the cooking time, at most 5 minutes. |
| `<method>_main` | The main action of the cooking method (see the table below), looping. | From the end of the chopping until the tasting. |
| `<method>_wipe` <br><img src="animation/boil-wipe-toque.gif" width="135" alt="wipe"> | Wipes his brow. | A small action. In every 30 seconds of the main part there is one window (seconds 12 to 15). In it he does one of the three small actions, or nothing; which one depends on the pot and on which 30 seconds it is, so the same moment always shows the same thing. |
| `<method>_look` <br><img src="animation/stirfry-look-scarf.gif" width="135" alt="look"> | Looks up from the pot, blinks at you and waves. | A small action, as above. |
| `<method>_hot` <br><img src="animation/steam-hot-toque.gif" width="135" alt="hot"> <img src="animation/mix-hot-scarf.gif" width="135" alt="sneaks a bite"> | Gets a face full of steam and flinches. Mixing has no heat, so there he sneaks a bite instead. | A small action, as above. |
| `<method>_taste` <br><img src="animation/fry-taste-scarf.gif" width="135" alt="taste"> | Tastes a spoonful and adds seasoning. | The last 10% of the cooking time, at most 2 minutes. |
| (waiting) | Keeps doing the main action. | After the time is up, until the backend says how the pot turned out (at most 6 seconds; after that it counts as an ordinary pot). He never serves first and then changes his mind. |
| `<method>_serve` | Plates the dish and holds it up. | The pot turned out `great` or `ok`. The clip plays once, the last frame (`<method>_serve_last`) is held for 2 seconds, then he sinks back behind the card. |
| `<method>_fail` | Smoke; he holds up something black. | The pot turned out `burnt` or `spoiled`. Same timing, with `<method>_fail_last` as the held frame. |
| heat off | Sinks back behind the card while still doing the main action; carries nothing out. | The pot was cancelled while the card was on screen. |
| after | No cook. The card reads "served" with the outcome, or "heat off". | From then on, and for any card that is shown for the first time after its pot was already due. |
| `base` | Stands still. | Instead of the clips when the visitor asked for reduced motion, when the page is in the background, or when more than two cooks would be moving at once (the two newest cards move). |

## Seven methods, two outfits

The method comes from the backend with the pot (`stirfry`, `fry`, `deepfry`, `boil`, `steam`, `bake`, `mix`; anything else plays as `stirfry`). The outfit is picked from the pot's id, so one pot keeps one outfit from start to finish and both turn up over time: `toque` is a tall chef's hat, a white double-breasted jacket and a red neckerchief; `scarf` is a blue polka-dot headscarf and a cream apron with a pink heart pocket.

| Method | Main action | `toque` | `scarf` | Served | Burnt |
|---|---|---|---|---|---|
| `stirfry` 炒 | Tosses the pan over the flame. | <img src="animation/stirfry-main-toque.gif" width="135" alt="stirfry, toque"> | <img src="animation/stirfry-main-scarf.gif" width="135" alt="stirfry, scarf"> | <img src="animation/stirfry-serve-toque.gif" width="135" alt="stirfry served"> | <img src="animation/stirfry-fail-scarf.gif" width="135" alt="stirfry burnt"> |
| `fry` 煎 | Watches the pan spit, slides the spatula under and flips. | <img src="animation/fry-main-toque.gif" width="135" alt="fry, toque"> | <img src="animation/fry-main-scarf.gif" width="135" alt="fry, scarf"> | <img src="animation/fry-serve-toque.gif" width="135" alt="fry served"> | <img src="animation/fry-fail-scarf.gif" width="135" alt="fry burnt"> |
| `deepfry` 炸 | Lowers a piece into the oil with long chopsticks and lifts it out golden. | <img src="animation/deepfry-main-toque.gif" width="135" alt="deepfry, toque"> | <img src="animation/deepfry-main-scarf.gif" width="135" alt="deepfry, scarf"> | <img src="animation/deepfry-serve-toque.gif" width="135" alt="deepfry served"> | <img src="animation/deepfry-fail-scarf.gif" width="135" alt="deepfry burnt"> |
| `boil` 煮 | The lid rattles; he lifts it and leans into the steam. | <img src="animation/boil-main-toque.gif" width="135" alt="boil, toque"> | <img src="animation/boil-main-scarf.gif" width="135" alt="boil, scarf"> | <img src="animation/boil-serve-toque.gif" width="135" alt="boil served"> | <img src="animation/boil-fail-scarf.gif" width="135" alt="boil burnt"> |
| `steam` 蒸 | Minds a bamboo steamer and lifts the lid on three white buns. | <img src="animation/steam-main-toque.gif" width="135" alt="steam, toque"> | <img src="animation/steam-main-scarf.gif" width="135" alt="steam, scarf"> | <img src="animation/steam-serve-toque.gif" width="135" alt="steam served"> | <img src="animation/steam-fail-scarf.gif" width="135" alt="steam burnt"> |
| `bake` 烤 | Crouches at the oven window in mitts while the loaf browns. | <img src="animation/bake-main-toque.gif" width="135" alt="bake, toque"> | <img src="animation/bake-main-scarf.gif" width="135" alt="bake, scarf"> | <img src="animation/bake-serve-toque.gif" width="135" alt="bake served"> | <img src="animation/bake-fail-scarf.gif" width="135" alt="bake burnt"> |
| `mix` 拌 | No heat: tosses a big bowl with two servers. | <img src="animation/mix-main-toque.gif" width="135" alt="mix, toque"> | <img src="animation/mix-main-scarf.gif" width="135" alt="mix, scarf"> | <img src="animation/mix-serve-toque.gif" width="135" alt="mix served"> | <img src="animation/mix-fail-scarf.gif" width="135" alt="mix burnt"> |

The pictures here show one outfit per column to keep the page light; every clip exists in both outfits. To look at all of them, open [`web/examples/gallery.html`](../web/examples/gallery.html) (see [`web/README.md`](../web/README.md) for how to open the example pages).

## What keeps it steady

- **Nothing is remembered, everything is recomputed.** The segment is a function of the pot's start time, its duration, the current time and what the backend said. Scroll the card away and back, or reload the page, and he is where he should be at that moment.
- **The entrance and the hand-washing happen once.** Showing the card again does not replay them, and a pot started hours ago does not get an entrance at all.
- **A card from history never comes back to life.** If the pot was already due when the card appeared, the card shows the finished state with no cook.
- **One-shot clips end on a still image.** After a serve or fail clip has played, the card swaps it for a PNG of its last frame, so it does not depend on how a browser loops animated images.

The rules live in two small files of pure functions, [`web/src/cookPhase.ts`](../web/src/cookPhase.ts) and [`web/src/cookSegments.ts`](../web/src/cookSegments.ts), each with its tests next to it.

## Chores on the kitchen page

Three more sets of clips are not played by the card but by the kitchen page ([`PAGE.md`](PAGE.md)), in a small panel at the top of its "vendor" and "plates" pages. Nothing is drawn onto the kitchen picture. They come from the same pack, in the same two outfits, and follow the card's outfit rule: a washing wears `outfits[hash(washing id) % 2]`, an order its order id's, calling the vendor over the visit id's.

<img src="animation/chores.gif" width="660" alt="Three panels side by side: the cook buying from the vendor at the window, washing a plate step by step and dropping one, and loading the dishwasher">

| Segment | What he does | When it plays |
|---|---|---|
| `vendor_call` | Waves at the window; a hand under an awning waves back (the vendor himself is never drawn). | A vendor is downstairs and the role has no order under way; also after carrying the last one back. |
| `vendor_pay` | Hands two coins to the hand reaching in. | The role's latest order of this visit is created, being charged or paid. Not for an order the human treats him to (it costs him nothing). |
| `vendor_take` → `vendor_carry` | Takes a steaming paper bag, holds it to his chest (once; `vendor_take_last` is its last frame), then carries it back, bobbing. | The order is delivered: `take` for 3 seconds from the moment it was, then `carry` for 9 seconds. A refunded or failed order takes nothing. |
| `dish_sleeve` `dish_soap` `dish_scrub` `dish_rinse` `dish_shake` `dish_dry` `dish_stack` | Rolls up his sleeves, squeezes the soap, scrubs, rinses under the tap, shakes the water off, dries with a towel, stacks it on the rack. | While he washes up: each plate's time (`per_s`) is cut into seven equal parts in this order, each looping. The sleeves are rolled up once, at the start of the washing; from the second plate on the first part is soap too. |
| `dish_break` | The plate slips, bounces, he grabs at it and misses; it breaks on the floor and he scratches his head (once; `dish_break_last` is its last frame). | When a plate's time is up and the server reports it broken. A plate's result is only told once its time is up, so the page never knows beforehand which one will break; the clip plays for 3 seconds from that moment, its last frame for 2 more, then the next plate goes on. |
| `machine_load` → `machine_close` → `machine_start` → `machine_run` → `machine_done` | Puts the plates in, closes the door, presses the button, the machine runs, he opens it in a puff of steam (once; `machine_done_last` is its last frame). | From when a plate last went into the dishwasher: 3 + 3 + 3 seconds, the run for 8 seconds, then done, and its last frame stays. |
| still | `base`, or the `_last` frame of `vendor_take`, `dish_break`, `machine_done`. | "Reduce motion": a clip that plays once shows its last frame, any other the standing pose. |

The rules are pure functions in [`web/page/src/kitchen/choreAnim.ts`](../web/page/src/kitchen/choreAnim.ts) with tests next to them; the server gives what they need (`/api/dishes`: the washing's `breaks` and `machine_at`; `/api/vendor`: the role's orders with `updated_at`, see [`API.md`](API.md)). A pack of your own does not need them: the card's registry check reports them separately (`missingChoreKeys`), and without them the panels are simply empty.

## Using your own character

The card does not know about Clawd. It asks a registry "which file is `<outfit>/<segment>`?" and shows that file. Give the element your own registry and folder:

```html
<kitchenette-cooking-card id="pot" assets="/my-sprites/"></kitchenette-cooking-card>
<script type="module">
  document.getElementById("pot").manifest = {
    outfits: ["plain"],                       // one pot wears outfits[hash(pot id) % outfits.length]
    files: {
      "plain/base": "plain/base.png",
      "plain/wash": "plain/wash.webp",
      "plain/chop": "plain/chop.webp",
      "plain/boil_main": "plain/boil_main.webp",
      // ... one entry per segment, for every outfit
    },
  };
</script>
```

The built-in registry, [`assets/clawd/manifest.json`](../assets/clawd/manifest.json), is the model to copy. An outfit needs 66 files:

| Key | Count | File |
|---|---|---|
| `<outfit>/base` | 1 | still image: the standing pose |
| `<outfit>/wash`, `<outfit>/chop` | 2 | animated clips |
| `<outfit>/<method>_<part>` for 7 methods × `main`, `wipe`, `look`, `hot`, `taste`, `serve`, `fail` | 49 | animated clips |
| `<outfit>/<method>_serve_last`, `<outfit>/<method>_fail_last` for 7 methods | 14 | still images: the last frame of the serve / fail clip |

If you only draw some methods, point the other methods' keys at the files you have. A key that is missing altogether leaves the stage empty for that segment. If the pack's folder is not there at all, the card asks for one image, finds nothing and asks for nothing more: without sprites the card only counts down.

Image spec:

| | |
|---|---|
| Format | Animated clips: anything an `<img>` can animate with transparency (the Clawd pack uses lossless animated WebP). Stills: PNG. |
| Canvas | Square, shown at 180 × 180 CSS pixels. The Clawd pack is 720 × 720. |
| The line | The row at 560 / 720 of the height (7/9 of the way down) sits exactly on the card's top edge. Everything above it is visible; everything below is cut off, and only shows for an instant when he bounces in. Stand the character and the counter on that line, and let bodies and pot bottoms continue a little below it. |
| Length | 3 seconds per clip. The timing rules assume it. |
| First frame | The same standing pose in every clip (and equal to `base`), so changing clips does not jump. |
| Loops | `main`, `chop` and `taste` loop for as long as their part lasts and should loop seamlessly. `wash`, the three small actions, `serve` and `fail` are shown for 3 seconds only. |
| Movement | Do not bake the entrance or the exit into the clips: the card slides the whole canvas itself. |
| Last frames | `_serve_last` / `_fail_last` are the final frame of the matching clip, pixel for pixel. |

## Where things are

| | |
|---|---|
| [`assets/clawd/`](../assets/clawd/) | The sprite pack: `toque/` and `scarf/` (95 files each: the 66 the card needs, 9 settled stills, 20 chore clips and stills), `dishes/`, `manifest.json`, the attribution and the licenses. |
| [`clawd-engine-additions/`](../clawd-engine-additions/) | The outfits and moves (the chores in `states/chores/`) as source files for the clawds-new-clothes engine, and how to export the pack again. |
| [`web/`](../web/) | The card: the `<kitchenette-cooking-card>` element, its example pages and tests. |
| [`docs/animation/`](animation/) | The GIFs on this page (made from the pack by `docs/animation/tools/make_gifs.py`). |

---

# 卡上的小厨师

他开锅之后，聊天里会出现一张做饭卡，按真实时间倒数。卡的上沿站着一个小厨师，真的在做这顿饭：洗手、切菜、守着锅、尝味道，到点把菜端出来。也可能做糊。

| 做好的一锅 | 糊了的一锅 |
|---|---|
| <img src="animation/card-served.gif" width="406" alt="做饭卡在倒数，小厨师颠锅、尝味，然后把盘子端起来，卡上写出锅了"> | <img src="animation/card-burnt.gif" width="406" alt="做饭卡在倒数，小厨师炸东西、尝味，然后冒烟，卡上写糊了"> |

> **非官方同人作品。** 小厨师是 Clawd——Anthropic 为 Claude Code 创作的角色；角色形象以及「Clawd」「Claude」「Claude Code」「Anthropic」这些名称，一切权利归 Anthropic, PBC。本项目与 Anthropic 没有隶属关系，没有得到其赞助或背书。小厨师用 [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) 的引擎画成（动画与引擎：Luin Luinaris；信差设定与像素修订：Charlie Luinaris），两套厨师服和下厨动作是本项目加的。图按 CC BY-NC-SA 4.0 提供，仅限非商业使用。完整署名见 [`assets/clawd/ATTRIBUTION.md`](../assets/clawd/ATTRIBUTION.md)。

## 一锅饭从头到尾

每一段都是 3 秒（45 帧），第一帧都是同一个站好的姿势，所以任意两段接起来都不会跳。

| 段 | 他在做什么 | 什么时候播 |
|---|---|---|
| 出场 | 从卡的上沿后面弹上来，带一点回弹。 | 只一次：这个页面第一次见到这一锅，而且下锅不超过 5 分钟。 |
| `wash` 洗手 <br><img src="animation/wash-toque.gif" width="135" alt="洗手"> | 在水盆里搓手，甩两下。 | 只一次，出场时播 3 秒。不到 3 分钟的快手菜不洗；卡再次出现时不重播。 |
| `chop` 切菜 <br><img src="animation/chop-scarf.gif" width="135" alt="切菜"> | 在案板上切一根胡萝卜。 | 时长的前 20%，最长 5 分钟。 |
| `<做法>_main` 主动作 | 这种做法的主动作（见下表），循环。 | 切完菜之后，到尝味之前。 |
| `<做法>_wipe` 擦汗 <br><img src="animation/boil-wipe-toque.gif" width="135" alt="擦汗"> | 抬手擦一下额头。 | 小动作。主段里每 30 秒有一个窗口（第 12 到 15 秒），他在三个小动作里做一个，或者什么都不做；做哪个由「这一锅 + 第几个 30 秒」决定，同一时刻看到的永远是同一个。 |
| `<做法>_look` 抬头 <br><img src="animation/stirfry-look-scarf.gif" width="135" alt="抬头"> | 不看锅了，抬头眨眨眼、挥挥手。 | 小动作，同上。 |
| `<做法>_hot` 被熏到 <br><img src="animation/steam-hot-toque.gif" width="135" alt="被熏到"> <img src="animation/mix-hot-scarf.gif" width="135" alt="偷吃一口"> | 被热气扑了一脸，缩一下。拌菜不开火，这一段是偷吃一口。 | 小动作，同上。 |
| `<做法>_taste` 尝味 <br><img src="animation/fry-taste-scarf.gif" width="135" alt="尝味"> | 尝一口，加点调料。 | 时长的最后 10%，最长 2 分钟。 |
| （等结果） | 接着做主动作。 | 到点之后、后端还没说这一锅怎么样的那一小会儿（最多 6 秒，等不到就按普通的一锅算）。不会先端出来再改口。 |
| `<做法>_serve` 端上来 | 装盘，端起来给你看。 | 出锅结果是「很好」或「普通」。动图播一遍，最后一帧（`<做法>_serve_last`）停 2 秒，然后收回卡后面。 |
| `<做法>_fail` 糊了 | 冒烟，端出一盘黑的。 | 出锅结果是「糊了」或「坏了」。节奏同上，停住的那一帧是 `<做法>_fail_last`。 |
| 关火 | 保持主动作收回卡后面，不端东西出来。 | 卡在屏幕上的时候这一锅被关火了。 |
| 之后 | 没有小厨师。卡上写「出锅了」加结果，或者「关火了」。 | 从那以后都是这样；一张卡第一次出现时如果这一锅早就到点了，也直接是这样。 |
| `base` 站好 | 站着不动。 | 代替动图：访客开了「减少动态」、页面在后台、或者同一页里会同时动的小厨师超过两个时（最新的两张卡在动）。 |

## 七种做法，两套衣服

做法由后端随这一锅给出（`stirfry` 炒、`fry` 煎、`deepfry` 炸、`boil` 煮、`steam` 蒸、`bake` 烤、`mix` 拌；别的值一律按炒）。衣服按这一锅的 id 定：同一锅从头到尾不换，时间长了两套都会出现。`toque` 是高筒厨师帽、白色双排扣厨师服和红领巾；`scarf` 是蓝底白点头巾和带粉色爱心口袋的米色大围裙。

| 做法 | 主动作 | `toque` | `scarf` | 端上来 | 糊了 |
|---|---|---|---|---|---|
| `stirfry` 炒 | 在火上颠锅。 | <img src="animation/stirfry-main-toque.gif" width="135" alt="炒，toque"> | <img src="animation/stirfry-main-scarf.gif" width="135" alt="炒，scarf"> | <img src="animation/stirfry-serve-toque.gif" width="135" alt="炒，端上来"> | <img src="animation/stirfry-fail-scarf.gif" width="135" alt="炒，糊了"> |
| `fry` 煎 | 盯着锅里溅油，锅铲探到底下翻面。 | <img src="animation/fry-main-toque.gif" width="135" alt="煎，toque"> | <img src="animation/fry-main-scarf.gif" width="135" alt="煎，scarf"> | <img src="animation/fry-serve-toque.gif" width="135" alt="煎，端上来"> | <img src="animation/fry-fail-scarf.gif" width="135" alt="煎，糊了"> |
| `deepfry` 炸 | 用长筷子把一块放进油锅，炸到金黄夹出来。 | <img src="animation/deepfry-main-toque.gif" width="135" alt="炸，toque"> | <img src="animation/deepfry-main-scarf.gif" width="135" alt="炸，scarf"> | <img src="animation/deepfry-serve-toque.gif" width="135" alt="炸，端上来"> | <img src="animation/deepfry-fail-scarf.gif" width="135" alt="炸，糊了"> |
| `boil` 煮 | 锅盖被顶得一跳一跳，掀开凑过去看。 | <img src="animation/boil-main-toque.gif" width="135" alt="煮，toque"> | <img src="animation/boil-main-scarf.gif" width="135" alt="煮，scarf"> | <img src="animation/boil-serve-toque.gif" width="135" alt="煮，端上来"> | <img src="animation/boil-fail-scarf.gif" width="135" alt="煮，糊了"> |
| `steam` 蒸 | 守着蒸笼，掀开盖子露出三个白馒头。 | <img src="animation/steam-main-toque.gif" width="135" alt="蒸，toque"> | <img src="animation/steam-main-scarf.gif" width="135" alt="蒸，scarf"> | <img src="animation/steam-serve-toque.gif" width="135" alt="蒸，端上来"> | <img src="animation/steam-fail-scarf.gif" width="135" alt="蒸，糊了"> |
| `bake` 烤 | 戴着隔热手套蹲在烤箱前，看面包越烤越深。 | <img src="animation/bake-main-toque.gif" width="135" alt="烤，toque"> | <img src="animation/bake-main-scarf.gif" width="135" alt="烤，scarf"> | <img src="animation/bake-serve-toque.gif" width="135" alt="烤，端上来"> | <img src="animation/bake-fail-scarf.gif" width="135" alt="烤，糊了"> |
| `mix` 拌 | 不开火，两手各一把勺叉拌一大碗。 | <img src="animation/mix-main-toque.gif" width="135" alt="拌，toque"> | <img src="animation/mix-main-scarf.gif" width="135" alt="拌，scarf"> | <img src="animation/mix-serve-toque.gif" width="135" alt="拌，端上来"> | <img src="animation/mix-fail-scarf.gif" width="135" alt="拌，糊了"> |

这一页每一列只放了一套衣服，免得页面太重；所有分段两套衣服都有。想全看一遍，打开 [`web/examples/gallery.html`](../web/examples/gallery.html)（例子页怎么打开见 [`web/README.md`](../web/README.md#在自己电脑上看)）。

## 为什么不会乱跳

- **什么都不记，全部现算。** 播哪一段只取决于下锅时刻、时长、现在几点、后端说了什么。卡滚出屏幕再滚回来，或者刷新页面，他都直接落在这一刻该在的那一段。
- **出场和洗手只有一次。** 卡再次出现不会重播；几小时前开的锅不会再演一遍出场。
- **历史卡不会复活。** 卡出现时这一锅已经到点了，就直接显示做完的样子，没有小厨师。
- **只播一次的段落在静态图上。** 端上来 / 糊了播完之后，换成最后一帧的 PNG，不依赖浏览器怎么循环动图。

规则在两个纯函数文件里：[`web/src/cookPhase.ts`](../web/src/cookPhase.ts) 和 [`web/src/cookSegments.ts`](../web/src/cookSegments.ts)，测试就在旁边。

## 厨房页上的家务

还有三组动画不在做饭卡上放，而在厨房页（[`PAGE.md`](PAGE.md)）的「小贩」页和「盘子」页顶上的一小格里放；厨房那张画上不叠动画。它们和做饭卡同一套素材、同两套衣服，也按做饭卡的规则挑衣服：一趟刷盘子按这一趟的 id，一单按订单号，叫小贩按到访号。

<img src="animation/chores.gif" width="660" alt="三格并排:小贩窗边买东西、一步一步刷盘子并摔碎一只、往洗碗机里放盘子">

| 段 | 他在做什么 | 什么时候放 |
|---|---|---|
| `vendor_call` | 站在窗边挥手，窗外篷布下一只手朝他摆摆（不画小贩本人）。 | 小贩在楼下，他没有正在办的单；接完东西捧回来以后也回到这一段。 |
| `vendor_pay` | 把两枚硬币递给窗外伸进来的手。 | 他这一趟最新的一单刚下、在扣钱或已付。你替他买的单不花他的钱，没有这一段。 |
| `vendor_take` → `vendor_carry` | 接过一只冒热气的纸袋抱在胸前（放一遍，末帧 `vendor_take_last`），然后抱着一颠一颠往回走。 | 这一单交货了：从交货那一刻起 `take` 3 秒，再 `carry` 9 秒。退了款、没扣成的单不放接东西。 |
| `dish_sleeve` `dish_soap` `dish_scrub` `dish_rinse` `dish_shake` `dish_dry` `dish_stack` | 挽袖子、挤洗洁精、搓、在水龙头下冲、甩水、拿毛巾擦干、码到沥水架上。 | 他在刷的时候：每只盘子的时长（`per_s`）七等分，按这个顺序，每一段循环放。袖子只在这一趟开头挽一次，第二只起头一格也是挤洗洁精。 |
| `dish_break` | 盘子一滑往上一蹦，手忙脚乱没接住，摔在地上碎了，他挠挠头（放一遍，末帧 `dish_break_last`）。 | 某只盘子到点、服务端说它碎了的时候。一只盘子的结果要到它到点才告诉页面，所以页面事先不知道哪只会碎；从那一刻起放 3 秒，末帧再停 2 秒，然后接着刷下一只。 |
| `machine_load` → `machine_close` → `machine_start` → `machine_run` → `machine_done` | 把盘子放进去、关门、按按钮、洗碗机转着、洗好开门冒热气（放一遍，末帧 `machine_done_last`）。 | 从最近一只盘子进洗碗机起：3 + 3 + 3 秒，转 8 秒，然后开门，停在末帧。 |
| 静帧 | `base`，或 `vendor_take`、`dish_break`、`machine_done` 的 `_last`。 | 设备开了「减少动态效果」：放一遍的段显示末帧，其余显示站好的姿势。 |

规则是 [`web/page/src/kitchen/choreAnim.ts`](../web/page/src/kitchen/choreAnim.ts) 里的纯函数，测试就在旁边；要用到的东西由服务端给（`/api/dishes` 的 `breaks` 和 `machine_at`，`/api/vendor` 里他的单带 `updated_at`，见 [`API.md`](API.md)）。换成自己的小人时这几组可以不画：做饭卡的登记表检查把它们单列（`missingChoreKeys`），没有的话那一格就是空的。

## 换成自己的小人

做饭卡并不认识 Clawd。它只问登记表「`<衣服>/<段>` 是哪个文件」，然后显示那个文件。把自己的登记表和素材目录交给它就行：

```html
<kitchenette-cooking-card id="pot" assets="/my-sprites/"></kitchenette-cooking-card>
<script type="module">
  document.getElementById("pot").manifest = {
    outfits: ["plain"],                       // 这一锅穿 outfits[hash(这一锅的 id) % outfits.length]
    files: {
      "plain/base": "plain/base.png",
      "plain/wash": "plain/wash.webp",
      "plain/chop": "plain/chop.webp",
      "plain/boil_main": "plain/boil_main.webp",
      // ……每套衣服的每一段各一条
    },
  };
</script>
```

自带的登记表 [`assets/clawd/manifest.json`](../assets/clawd/manifest.json) 可以照着抄。一套衣服要 66 个文件：

| 键 | 个数 | 文件 |
|---|---|---|
| `<衣服>/base` | 1 | 静态图：站好的姿势 |
| `<衣服>/wash`、`<衣服>/chop` | 2 | 动图 |
| `<衣服>/<做法>_<段>`：7 种做法 × `main`、`wipe`、`look`、`hot`、`taste`、`serve`、`fail` | 49 | 动图 |
| `<衣服>/<做法>_serve_last`、`<衣服>/<做法>_fail_last`：7 种做法 | 14 | 静态图：端上来 / 糊了的最后一帧 |

只画了其中几种做法时，把别的做法的键指到已有的文件上。哪个键完全没登记，那一段台上就是空的。整个素材目录都不在时，卡先要一张图，要不到就不再要：没有素材时卡只有倒数。

素材规格：

| | |
|---|---|
| 格式 | 动图：`<img>` 能播、带透明的格式都行（Clawd 这一套用无损动态 WebP）。静态图：PNG。 |
| 画布 | 正方形，按 180 × 180 CSS 像素显示。Clawd 这一套是 720 × 720。 |
| 那条线 | 高度的 560 / 720 处（从上往下 7/9）正好压在卡的上沿。线以上看得见；线以下被裁掉，只在出场回弹的那一下露一点。角色和台面站在这条线上，身体和锅底往线下多画一截。 |
| 时长 | 每段 3 秒。计时规则按这个数算。 |
| 第一帧 | 每一段的第一帧都是同一个站好的姿势（并且等于 `base`），换段才不会跳。 |
| 循环 | `main`、`chop`、`taste` 会一直循环到这一部分结束，首尾要接得上。`wash`、三个小动作、`serve`、`fail` 只显示 3 秒。 |
| 位移 | 出场和收回不要画进动图里，卡自己会移动整张画布。 |
| 最后一帧 | `_serve_last` / `_fail_last` 就是对应动图的最后一帧，逐像素相同。 |

## 东西在哪

| | |
|---|---|
| [`assets/clawd/`](../assets/clawd/) | 素材：`toque/`、`scarf/`（各 95 个文件：做饭卡要的 66 个、结算定格 9 个、家务 20 个）、`dishes/`、`manifest.json`、署名与许可。 |
| [`clawd-engine-additions/`](../clawd-engine-additions/) | 两套衣服和全部动作（家务在 `states/chores/`）的引擎源文件，以及怎么重新导出。 |
| [`web/`](../web/) | 做饭卡：`<kitchenette-cooking-card>` 元素、例子页和测试。 |
| [`docs/animation/`](animation/) | 本页的动图（用 `docs/animation/tools/make_gifs.py` 从素材生成）。 |
