# Attribution · 署名

> **Unofficial fan work.** Clawd is a character created by Anthropic for Claude Code. All rights in the Clawd character and in the names and marks "Clawd", "Claude", "Claude Code" and "Anthropic" belong to Anthropic, PBC. Nothing in this folder is made by, affiliated with, sponsored by or endorsed by Anthropic, and no license here grants any right in Anthropic's characters, names or marks.
>
> **非官方同人作品。** Clawd 是 Anthropic 为 Claude Code 创作的角色。Clawd 的角色形象，以及「Clawd」「Claude」「Claude Code」「Anthropic」这些名称与标识，一切权利归 Anthropic, PBC。本目录的内容不是 Anthropic 出品，与 Anthropic 没有隶属关系，没有得到其赞助或背书；这里的任何许可都不授予与 Anthropic 的角色、名称、标识相关的权利。

## Where the cook comes from

Every image in this folder is **adapted material**: it was rendered with the engine of

- **clawds-new-clothes** — <https://github.com/CharlieLuinaris/clawds-new-clothes>
- Copyright 2026 Charlie Luinaris
- **Luin Luinaris** (<https://github.com/luinluinaris>): the animation and the engine, from the first prototype to all 48 moves, plus the outfit layers, checks and export tools.
- **Charlie Luinaris**: the London postie concept, the pixel corrections and the four outfits; maintainer and copyright holder.
- Licenses: code **MIT**; artwork and anything that depicts Clawd **CC BY-NC-SA 4.0**, offered to the extent the authors hold rights in it; the Clawd character itself is excluded.
- Upstream commit used: `76e7572b42859205f44d2e46ae61f76947efae64` (2026-10-17, v1.1.0).

The upstream `NOTICE` is reproduced unchanged in [`UPSTREAM-NOTICE`](UPSTREAM-NOTICE), the upstream `LICENSE` (MIT, with its scope note) in [`LICENSES/UPSTREAM-LICENSE`](LICENSES/UPSTREAM-LICENSE), and the full license texts in [`LICENSES/`](LICENSES/).

## What was changed

The body, the face and the way he moves are upstream's. On top of the upstream engine, tsuru0805 added (2026-11):

- **Two outfits** that replace the postie uniform (bowler hat, waistcoat, satchel and pocket watch are taken off):
  - `toque` — a tall chef's hat, a white double-breasted jacket and a red neckerchief;
  - `scarf` — a blue polka-dot headscarf and a cream apron with a pink heart pocket.
- **51 cooking moves**, 45 frames each: washing hands, chopping, and for each of seven methods (stir-fry, pan-fry, deep-fry, boil, steam, bake, mix) seven moves (the main action, wiping the brow, looking up, caught by the steam, tasting, serving, burning it), with the pots, pans and food they need.
- **Five settled stills** (`settle_great`, `settle_ok`, `settle_burnt`, `settle_spoiled`, `settle_ruined`, each with a `_front` layer holding only the hands, except `ruined`): the cook holding the finished dish up proudly, holding it plainly, holding a burnt one out at arm's length with smoke and a sweat drop, dizzy with spiral eyes and the plate tipping, and staring at a spilt pot. On the upstream face the eyes were redrawn (closed smiling eyes, eyes looking away, spirals, small square eyes) and a blush, sparkles, a heart, smoke and a sweat drop were added, on the same pixel grid and in the same colours; the body and the outfits are untouched. Sources in `clawd-engine-additions/states/settle/`, exported by `clawd-engine-additions/tools/export_settle.py`.
- **17 chore moves**, 45 frames each, played by the kitchen page (not by the card): buying from a vendor at the window (`vendor_call` waving him over, `vendor_pay` handing over coins, `vendor_take` taking a paper bag, `vendor_carry` carrying it back), washing up by hand (`dish_sleeve`, `dish_soap`, `dish_scrub`, `dish_rinse`, `dish_shake`, `dish_dry`, `dish_stack`, and `dish_break`, a plate slipping and breaking), and the dishwasher (`machine_load`, `machine_close`, `machine_start`, `machine_run`, `machine_done`), with the sink, tap, sponge, towel, rack, window, coins, paper bag and dishwasher they need. The vendor is never drawn: only a hand and an awning outside the window. The face is upstream's, using the engine's own eye styles and blush; small marks (a "!", hearts, a sweat drop, steam) are drawn next to him on the same pixel grid. Sources in `clawd-engine-additions/states/chores/`, exported by `clawd-engine-additions/tools/export_chores.py`.
- **The dishes** in `dishes/`: fourteen small pixel pictures of kinds of dish (and a burnt version of each), drawn by tsuru0805 on the cook's grid for the settled stills (`tools/draw_dish_icons.py`). They do not depict Clawd; they are kept in this folder, under the same license, because they are only ever shown in the cook's hands.
- **The export**: each move in each outfit as an animated WebP (the engine's 300 px canvas scaled ×2 with nearest-neighbour and placed on a 720 × 720 transparent canvas so that the counter line is at y = 560; frame delays 70 / 60 / 70 ms as upstream; lossless), the last frame of every serve and fail move and of `vendor_take`, `dish_break` and `machine_done` as a PNG, and `base.png`, the first frame of upstream's `idle` move in each outfit.

- **The repository's share image** (the picture shown when the repository link is shared; it is not stored in this repository): ten small cooks with different expressions. On the upstream face only the eyes were redrawn, and a mouth, a blush and small floating marks (a heart, sparkles, a sweat drop, a puff of smoke, "z") were added, on the same pixel grid and in the same colours; the body, the outfits and the hats are untouched. It is adapted material under the same CC BY-NC-SA 4.0 and carries the credit line.

The source files for these additions are in [`../../clawd-engine-additions/`](../../clawd-engine-additions/), with instructions for putting them back into the upstream engine and exporting again.

## License of the files in this folder

The images in `toque/`, `scarf/` and `dishes/` are licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International** (<https://creativecommons.org/licenses/by-nc-sa/4.0/>), the same license as the upstream artwork they adapt; full text in [`LICENSES/CC-BY-NC-SA-4.0.txt`](LICENSES/CC-BY-NC-SA-4.0.txt). Adaptations © 2026 tsuru0805, to the extent of the changes listed above. The Clawd character is not covered by this license.

That means: you may share and adapt these images for **non-commercial** purposes, as long as you keep this attribution, say what you changed, and share your version under the same license. No merchandise, no sticker-store listings, nothing that implies an official connection with Anthropic. If Anthropic or the upstream authors ask for something to be changed or removed, it will be.

The images are provided as they are, without warranties of any kind (see Section 5 of the license).

When you share or remix, please keep this line:

> munch-kitchenette cook · adapted from clawds-new-clothes (animation by Luin Luinaris, Clawd pixel art and outfits concept by Charlie Luinaris) · chef outfits and cooking moves by tsuru0805 · CC BY-NC-SA 4.0 · unofficial Clawd fan work

## 中文

本目录下的每一张图都是**改编作品**，用下面这个仓库的引擎画出来：

- **clawds-new-clothes** — <https://github.com/CharlieLuinaris/clawds-new-clothes>，版权所有 2026 Charlie Luinaris
- **Luin Luinaris**：动画与引擎（从底稿到四十八支动作）、换装图层、检查与导出工具。
- **Charlie Luinaris**：老伦敦信差的设定、像素修订与四套衣服；项目维护者与版权人。
- 许可：代码 **MIT**；美术以及一切画出 Clawd 的产物 **CC BY-NC-SA 4.0**（在作者享有权利的范围内提供，Clawd 角色本身不在其中）。
- 取用的上游 commit：`76e7572b42859205f44d2e46ae61f76947efae64`（2026-10-17，v1.1.0）。

上游的 `NOTICE` 原样收在 [`UPSTREAM-NOTICE`](UPSTREAM-NOTICE)，上游的 `LICENSE`（MIT 及其适用范围说明）在 [`LICENSES/UPSTREAM-LICENSE`](LICENSES/UPSTREAM-LICENSE)，两份许可全文在 [`LICENSES/`](LICENSES/)。

**改了什么**（tsuru0805，2026-11，在上游引擎之上加的；身体、脸和动起来的方式都是上游的）：

- **两套衣服**，换下信差制服（礼帽、马甲、皮包、怀表都摘掉）：`toque` 高筒厨师帽 + 白色双排扣厨师服 + 红领巾；`scarf` 蓝底白点头巾 + 米色大围裙 + 粉色爱心口袋。
- **51 支下厨动作**，每支 45 帧：洗手、切菜，以及七种做法（炒、煎、炸、煮、蒸、烤、拌）各七支（主动作、擦汗、抬头看、被热气熏到、尝味、端上来、糊了），连同用到的锅碗和菜。
- **17 支家务动作**，每支 45 帧，在厨房页上放（不在做饭卡上）：窗边跟小贩买东西（`vendor_call` 叫住、`vendor_pay` 递零花钱、`vendor_take` 接过纸袋、`vendor_carry` 捧着回来），自己刷盘子（`dish_sleeve` 挽袖子、`dish_soap` 挤洗洁精、`dish_scrub` 搓、`dish_rinse` 冲、`dish_shake` 甩水、`dish_dry` 擦干、`dish_stack` 码好，以及 `dish_break` 手滑摔碎一只），洗碗机（`machine_load` 放进去、`machine_close` 关门、`machine_start` 按按钮、`machine_run` 转着、`machine_done` 洗好开门），连同用到的水槽、水龙头、海绵、毛巾、沥水架、窗、硬币、纸袋和洗碗机。不画小贩本人，窗外只有一只手和篷布。脸是上游的，表情用的是引擎自带的眼睛样式和腮红；旁边加了「!」、小心、汗滴、热气这些小符号，画在同一套像素格上。源文件在 `clawd-engine-additions/states/chores/`，由 `clawd-engine-additions/tools/export_chores.py` 导出。
- **导出**：每支动作 × 每套衣服一张动态 WebP（引擎 300 像素画布最近邻放大 2 倍，贴在 720 × 720 透明画布上，台面线在 y = 560；每帧延时沿用上游的 70 / 60 / 70 毫秒；无损），端上来和糊了、以及 `vendor_take`、`dish_break`、`machine_done` 的最后一帧各一张 PNG，以及 `base.png`（上游 `idle` 动作的第一帧穿上这两套衣服）。

- **仓库的分享图**（分享仓库链接时显示的那张图，不存放在本仓里）：十只表情各不相同的小厨师。只在上游原来的脸上重画了眼睛，加了嘴、腮红和头顶的小符号（爱心、星星、汗滴、一团烟、「z」），用的是原来的像素格和原来的颜色；身子、衣服、帽子没有动。它同样是改编件，按相同的 CC BY-NC-SA 4.0 提供，图上带着署名行。

这些新增内容的源文件在 [`../../clawd-engine-additions/`](../../clawd-engine-additions/)，里面写了怎么放回上游引擎重新导出。

**本目录文件的许可**：`toque/` 与 `scarf/` 里的图按 **CC BY-NC-SA 4.0**（署名—非商业性使用—相同方式共享）提供，与它们改编的上游美术相同；全文见 [`LICENSES/CC-BY-NC-SA-4.0.txt`](LICENSES/CC-BY-NC-SA-4.0.txt)。改编部分 © 2026 tsuru0805，仅限上面列出的改动。Clawd 角色本身不在许可范围内。

也就是说：可以在**非商业**用途下转发和再改，但要带上署名、说明改了什么、改出来的东西用同一份许可公开。不做周边，不上架贴纸商店，不用在任何暗示与 Anthropic 有官方关系的场合。Anthropic 或上游作者要求修改或撤下时，照办。

这些图按现状提供，不附带任何担保（见许可第 5 条）。

转发、再创作时请带上这一行：

> munch-kitchenette cook · adapted from clawds-new-clothes (animation by Luin Luinaris, Clawd pixel art and outfits concept by Charlie Luinaris) · chef outfits and cooking moves by tsuru0805 · CC BY-NC-SA 4.0 · unofficial Clawd fan work
