# The cook's source files

[中文在下面](#小厨师的源文件)

The images in [`assets/clawd/`](../assets/clawd/) are drawn by code: the engine of [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) by Luin Luinaris and Charlie Luinaris, plus the files in this folder. This folder holds only what was added on top of the engine. Nothing of the upstream engine is copied here, and no upstream file was changed.

> **Unofficial fan work.** Everything these files draw is Clawd, a character created by Anthropic for Claude Code. All rights in the character and in the names "Clawd", "Claude", "Claude Code" and "Anthropic" belong to Anthropic, PBC. Not affiliated with, sponsored by or endorsed by Anthropic. Keep what you make with them non-commercial.

## What is here

| | | License (see each file's SPDX header) |
|---|---|---|
| `outfits/chef-toque.cjs` | Tall chef's hat, white double-breasted jacket, red neckerchief. | CC BY-NC-SA 4.0 |
| `outfits/chef-scarf.cjs` | Blue polka-dot headscarf, cream apron with a pink heart pocket. | CC BY-NC-SA 4.0 |
| `outfits/vendor-straw.cjs` | The street vendor: a wide straw hat, a short indigo jacket, a white towel round the neck, a coin pouch. | CC BY-NC-SA 4.0 |
| `states/_kitchen.cjs` | The props: pots, pans, stove, oven, steamer, board, knife, steam, smoke. | MIT |
| `states/_cooksets.cjs` | The seven methods' sets, and the six moves every method shares (`wipe`, `look`, `hot`, `taste`, `serve`, `fail`) built on one skeleton. | MIT |
| `states/cook-wash.cjs`, `states/cook-chop.cjs` | Washing hands, chopping. | MIT |
| `states/cook-<method>-main.cjs` × 7 | Each method's main action, drawn by hand. | MIT |
| `states/cook-<method>-<part>.cjs` × 42 | One line each: they ask `_cooksets.cjs` for their move. | MIT |
| `tools/export_cook_clips.py`, `tools/dump_frames.cjs` | Export the sprite pack from an engine that has these files in it. | MIT |
| `states/settle/settle-<pose>.cjs` × 5 | The settled stills: holding the dish (great / ok / burnt / spoiled), and the spilt pot (ruined). Kept in a folder of their own so that a normal export never sees them. | MIT |
| `tools/export_settle.py`, `tools/dump_settle.cjs` | Export the settled stills (`settle_<pose>.png` and `settle_<pose>_front.png` per outfit) and the plate positions. | MIT |
| `states/chores/` (13 moves + `_dishkit.cjs`) | The chores the kitchen page plays: washing up by hand step by step and dropping a plate (`dish-*`), the dishwasher (`machine-*`); `_dishkit.cjs` draws the sink, rack and dishwasher. Kept in a folder of their own, like the settled stills. | MIT |
| `tools/export_chores.py`, `tools/dump_chores.cjs` | Export the chore clips (`<segment>.webp`, plus `_last.png` for `dish_break`, `machine_done`). | MIT |
| `states/vendor/` (14 moves + `_stall.cjs`) | The street vendor at his cart, which the kitchen page plays: the vendor (`peddler-*`: pushing the cart in, calling with a hand bell, waiting, pushing it away, greeting a buyer, taking the coins, handing something over, watching the cook eat, waving goodbye) and a cook buying from him (`buyer-*`: walking over, paying, taking it, eating a bite, walking back out). Each file is the poses of one Clawd; `_stall.cjs` draws the cart in its two looks (the tanghulu seller's straw bundle, everyone else's crate of paper bags), the things in their hands and small marks, and says where each Clawd stands in each of the eleven scenes. | MIT |
| `tools/export_vendor.py`, `tools/dump_vendor.cjs` | Render both Clawds of a scene with the engine, place them and the cart on one scene, and export the vendor clips (`vendor_<part>.webp` and `vendor_th_<part>.webp`, `_last.png` for `leave`, `give`, `eat`, and a `still.png`). | MIT |
| `tools/check_vendor.cjs` | Runs the engine's own per-move check (`state-check.cjs`, the one `check-art.cjs` uses) over every vendor move, in each outfit it is worn in. | MIT |

The split follows upstream's own: move files are code (MIT), outfit designs are artwork (CC BY-NC-SA 4.0). Either way, what they render depicts Clawd and is CC BY-NC-SA 4.0, like every image upstream's engine produces. License texts are in [`LICENSES/`](LICENSES/); upstream's MIT license with its scope note is [`LICENSES/UPSTREAM-LICENSE`](LICENSES/UPSTREAM-LICENSE).

## Putting them back and exporting again

You need Node 20.9 or later, Python 3 with Pillow (`pip install pillow`), and git.

```sh
git clone https://github.com/CharlieLuinaris/clawds-new-clothes.git
cd clawds-new-clothes
git checkout 76e7572b42859205f44d2e46ae61f76947efae64    # the commit this pack was made with

cp /path/to/munch-kitchenette/clawd-engine-additions/outfits/*.cjs outfits/
cp /path/to/munch-kitchenette/clawd-engine-additions/states/*.cjs states/

python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_cook_clips.py . /tmp/cook-pack
```

`/tmp/cook-pack` then holds `toque/`, `scarf/` and `manifest.json`: the same 132 images as `assets/clawd/`, pixel for pixel and frame delay for frame delay. To export only some moves, name them after the output folder (`... /tmp/cook-pack cook-boil-main cook-boil-serve`).

The settled stills are exported the same way, from the same engine:

```sh
mkdir -p states/settle
cp /path/to/munch-kitchenette/clawd-engine-additions/states/settle/*.cjs states/settle/
python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_settle.py . /tmp/settle-pack
```

`/tmp/settle-pack` then holds the eighteen `settle_*` images of `assets/clawd/toque/` and `assets/clawd/scarf/`, pixel for pixel, and `settle.json` with the plate positions that `web/src/settle.ts` uses. The dish pictures in `assets/clawd/dishes/` are drawn by `tools/draw_dish_icons.py` at the root of this repository.

The chores are exported the same way:

```sh
mkdir -p states/chores
cp /path/to/munch-kitchenette/clawd-engine-additions/states/chores/*.cjs states/chores/
python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_chores.py . /tmp/chores-pack
```

`/tmp/chores-pack` then holds the thirty `dish_*` and `machine_*` files of `assets/clawd/toque/` and `assets/clawd/scarf/`, pixel for pixel and frame delay for frame delay; run `npm run manifest` in `web/` after copying them in.

The vendor's scenes need the vendor's outfit (copied with the other outfits above) and their own folder:

```sh
mkdir -p states/vendor
cp /path/to/munch-kitchenette/clawd-engine-additions/states/vendor/*.cjs states/vendor/
python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_vendor.py . /tmp/vendor-pack
```

`/tmp/vendor-pack` then holds the sixty `vendor_*` files of `assets/clawd/toque/` and `assets/clawd/scarf/` (thirty each), pixel for pixel; run `npm run manifest` in `web/` and `node scripts/gen-chores.mjs` in `web/page/` after copying them in. To check the vendor's moves the upstream way: `node /path/to/munch-kitchenette/clawd-engine-additions/tools/check_vendor.cjs .` (exit code 0 = no problems; the moves that play once end on another pose on purpose, so their loop seam is listed as a note).

The engine files are picked up by name: a file in `states/` becomes a move with that id, a file in `outfits/` becomes an outfit with that name; files starting with `_` are helpers. To look at one move the upstream way (this one needs `npm ci` first):

```sh
npm ci
node export.cjs --state cook-boil-main --preview --outfit chef-toque     # images land in states/preview/
```

How to draw moves and outfits of your own is explained in upstream's `states/README.md` and `outfits/README.md`.

## Good to know

- The moves are drawn to be worn with one of the two chef outfits. Without an outfit, the postie's satchel is still on him and gets in the way.
- These files were made for this project, not prepared as a contribution to upstream. Upstream's whole-set check (`node check-art.cjs --outfit chef-scarf`) reports the 14 serve / fail moves as "motion loop seam" (they are one-shot clips that end on a different pose on purpose) and two frames of each `wipe` move as covered eyes (his hand passes over them). With `chef-toque` it also reports a few of upstream's own moves whose props touch the tall hat. None of this affects the exported pack.
- If you change a move, keep its first frame as it is: every clip starts from the same pose so that the card can switch between them without a jump.
- The chores are drawn with their props around him (the sink, the dishwasher), so their first frames are not the bare standing pose; the kitchen page plays them in their own panel and does not need them to match the card's clips.
- The vendor's scenes have two Clawds and a cart, more than one 300 px engine canvas holds. Each Clawd is still an ordinary move of its own (45 frames, file name = id, poses only, rendered by the engine in its outfit); `dump_vendor.cjs` places them on a wider scene and draws the cart and props from `_stall.cjs` there. A scene is scaled ×1.4 rather than ×2 so that it fits the page's chore window; the cells are a little smaller than in the other chores. The vendor faces left when he pushes his cart: his side-on frames are drawn facing right and mirrored when placed (`tool.facing`).
- In the vendor's scenes, `arrive` ends on the pose `call` and `wait` start from, `walkin` on the one `pay` starts from, `give` on the one `eat` starts from, and `walkout` on the vendor alone at his cart again, so the page can play them one after another without a jump.

---

# 小厨师的源文件

[`assets/clawd/`](../assets/clawd/) 里的图是代码画出来的：用的是 Luin Luinaris 与 Charlie Luinaris 的 [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) 引擎，加上本目录里的文件。本目录只放在引擎之上新增的东西，不含上游引擎的任何文件，也没有改动上游的任何文件。

> **非官方同人作品。** 这些文件画出来的都是 Clawd——Anthropic 为 Claude Code 创作的角色。角色形象以及「Clawd」「Claude」「Claude Code」「Anthropic」这些名称，一切权利归 Anthropic, PBC。与 Anthropic 没有隶属关系，没有得到其赞助或背书。用它们做出来的东西请只用于非商业用途。

## 这里有什么

| | | 许可（以各文件开头的 SPDX 为准） |
|---|---|---|
| `outfits/chef-toque.cjs` | 高筒厨师帽、白色双排扣厨师服、红领巾。 | CC BY-NC-SA 4.0 |
| `outfits/chef-scarf.cjs` | 蓝底白点头巾、带粉色爱心口袋的米色大围裙。 | CC BY-NC-SA 4.0 |
| `outfits/vendor-straw.cjs` | 流动小贩「草帽货郎」：宽檐草帽、靛蓝短褂、脖子上一条白毛巾、腰间钱袋。 | CC BY-NC-SA 4.0 |
| `states/_kitchen.cjs` | 道具：锅、平底锅、灶、烤箱、蒸笼、案板、菜刀、热气、烟。 | MIT |
| `states/_cooksets.cjs` | 七种做法各自的一套家伙，以及每种做法共有的六支动作（`wipe`、`look`、`hot`、`taste`、`serve`、`fail`），按同一个骨架出。 | MIT |
| `states/cook-wash.cjs`、`states/cook-chop.cjs` | 洗手、切菜。 | MIT |
| `states/cook-<做法>-main.cjs` × 7 | 每种做法的主动作，手画。 | MIT |
| `states/cook-<做法>-<段>.cjs` × 42 | 每个文件一行：向 `_cooksets.cjs` 要自己那一支。 | MIT |
| `tools/export_cook_clips.py`、`tools/dump_frames.cjs` | 从装好这些文件的引擎里导出整套素材。 | MIT |
| `states/settle/settle-<姿势>.cjs` × 5 | 结算定格：举着菜（很好 / 普通 / 糊了 / 坏了），以及打翻的锅（毁了）。放在单独的子目录里，平常导出不会碰到。 | MIT |
| `tools/export_settle.py`、`tools/dump_settle.cjs` | 导出结算定格（每套衣服的 `settle_<姿势>.png` 和 `settle_<姿势>_front.png`）与盘位。 | MIT |
| `states/chores/`（13 支动作 + `_dishkit.cjs`） | 厨房页上放的家务：一步一步刷盘子和摔碎一只（`dish-*`）、洗碗机（`machine-*`）；`_dishkit.cjs` 画水槽、沥水架和洗碗机。和结算定格一样放在单独的子目录里。 | MIT |
| `tools/export_chores.py`、`tools/dump_chores.cjs` | 导出家务动画（`<段>.webp`，`dish_break`、`machine_done` 另有 `_last.png`）。 | MIT |
| `states/vendor/`（14 支动作 + `_stall.cjs`） | 厨房页上放的流动小贩：小贩（`peddler-*`：推车进场、摇铃吆喝、等客、推车离开、迎客、收钱、递货、看买方吃、挥手送客）和跟他买东西的小厨师（`buyer-*`：走过去、付钱、接过来、吃一口、走回去）。每个文件只管一只 Clawd 的姿势；`_stall.cjs` 画车（两种摆设：卖糖葫芦的草把子、其余小贩的纸袋箱）、手里的东西和小符号，并写明十一段场景里每只站在哪。 | MIT |
| `tools/export_vendor.py`、`tools/dump_vendor.cjs` | 用引擎分别渲染一段场景里的两只 Clawd，和车一起贴到同一张场景上，导出小贩动画（`vendor_<段>.webp` 与 `vendor_th_<段>.webp`，`leave`、`give`、`eat` 另有 `_last.png`，以及一张 `still.png`）。 | MIT |
| `tools/check_vendor.cjs` | 用引擎自带的单支体检（`state-check.cjs`，`check-art.cjs` 用的那份）把小贩的每支动作按它穿的衣服查一遍。 | MIT |

这样分是照上游自己的分法：动作文件算代码（MIT），衣服的设计算美术（CC BY-NC-SA 4.0）。不管哪一种，画出来的图都是 Clawd，按 CC BY-NC-SA 4.0 提供，和上游引擎导出的每一张图一样。许可全文在 [`LICENSES/`](LICENSES/)；上游的 MIT 许可及其适用范围说明是 [`LICENSES/UPSTREAM-LICENSE`](LICENSES/UPSTREAM-LICENSE)。

## 放回引擎，重新导出

需要 Node 20.9 以上、Python 3 和 Pillow（`pip install pillow`）、git。

```sh
git clone https://github.com/CharlieLuinaris/clawds-new-clothes.git
cd clawds-new-clothes
git checkout 76e7572b42859205f44d2e46ae61f76947efae64    # 这套素材用的那个 commit

cp /path/to/munch-kitchenette/clawd-engine-additions/outfits/*.cjs outfits/
cp /path/to/munch-kitchenette/clawd-engine-additions/states/*.cjs states/

python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_cook_clips.py . /tmp/cook-pack
```

`/tmp/cook-pack` 里是 `toque/`、`scarf/` 和 `manifest.json`：和 `assets/clawd/` 相同的 132 张图，像素和每帧延时都一致。只想导出其中几支，把动作 id 写在输出目录后面（`... /tmp/cook-pack cook-boil-main cook-boil-serve`）。

结算定格从同一个引擎导出：

```sh
mkdir -p states/settle
cp /path/to/munch-kitchenette/clawd-engine-additions/states/settle/*.cjs states/settle/
python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_settle.py . /tmp/settle-pack
```

`/tmp/settle-pack` 里是 `assets/clawd/toque/` 与 `assets/clawd/scarf/` 里那十八张 `settle_*` 图（像素一致），以及 `web/src/settle.ts` 用的盘位 `settle.json`。`assets/clawd/dishes/` 里菜的小图由仓库根目录的 `tools/draw_dish_icons.py` 画出。

家务动画也一样导出：

```sh
mkdir -p states/chores
cp /path/to/munch-kitchenette/clawd-engine-additions/states/chores/*.cjs states/chores/
python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_chores.py . /tmp/chores-pack
```

`/tmp/chores-pack` 里是 `assets/clawd/toque/` 与 `assets/clawd/scarf/` 里那三十个 `dish_*`、`machine_*` 文件，像素和每帧延时都一致；拷进去以后在 `web/` 里跑一次 `npm run manifest`。

小贩的场景要用到小贩的衣服（上面已经和别的衣服一起拷过去了），再放进它自己的子目录：

```sh
mkdir -p states/vendor
cp /path/to/munch-kitchenette/clawd-engine-additions/states/vendor/*.cjs states/vendor/
python3 /path/to/munch-kitchenette/clawd-engine-additions/tools/export_vendor.py . /tmp/vendor-pack
```

`/tmp/vendor-pack` 里是 `assets/clawd/toque/` 与 `assets/clawd/scarf/` 里那六十个 `vendor_*` 文件（各三十个），像素一致；拷进去以后在 `web/` 里跑一次 `npm run manifest`，在 `web/page/` 里跑一次 `node scripts/gen-chores.mjs`。按上游的方式体检小贩的动作：`node /path/to/munch-kitchenette/clawd-engine-additions/tools/check_vendor.cjs .`（退出码 0 = 没问题；只放一遍的段故意停在另一个姿势上，它们的循环接缝只列成提醒）。

引擎按文件名认东西：`states/` 里的文件就是一支同名的动作，`outfits/` 里的文件就是一套同名的衣服，`_` 开头的是辅助文件。想按上游的方式单看一支（要先 `npm ci`）：

```sh
npm ci
node export.cjs --state cook-boil-main --preview --outfit chef-toque     # 图存在 states/preview/
```

怎么画自己的动作和衣服，看上游的 `states/README.md` 与 `outfits/README.md`。

## 几件要知道的事

- 这些动作是配着两套厨师服画的。不穿衣服时，信差的皮包还背在身上，会挡住。
- 这些文件是为本项目做的，没有按「提交给上游」的标准整理。上游的整套检查（`node check-art.cjs --outfit chef-scarf`）会把 14 支端上来 / 糊了报成「motion loop seam」（它们是只播一次的段，故意停在另一个姿势上），把每支 `wipe` 里的两帧报成眼睛被盖住（手从眼前擦过）；穿 `chef-toque` 时还会报上游自己的几支动作，因为道具碰到了高帽子。这些都不影响导出的素材。
- 改某一支动作时，第一帧不要动：每一段都从同一个姿势开始，做饭卡换段才不会跳。
- 家务动画带着身边的家伙一起画（水槽、洗碗机），第一帧不是光站着的姿势；它们在厨房页自己那一格里放，不需要和做饭卡的段接得上。
- 小贩的场景里有两只 Clawd 和一辆车，一张 300 像素的引擎画布放不下。每只 Clawd 仍是一支普通的动作（45 帧、文件名就是 id、只管姿势、由引擎穿上自己的衣服渲染）；`dump_vendor.cjs` 把它们贴到一张更宽的场景上，车和道具按 `_stall.cjs` 画在同一张上。场景放大 1.4 倍而不是 2 倍，才装得进厨房页那一格；格子比别的家务小一点。推车时小贩朝左：侧身的帧画成朝右，贴上去时左右翻过来（`tool.facing`）。
- 小贩的场景里，`arrive` 的最后一帧就是 `call`、`wait` 开头的姿势，`walkin` 的接 `pay`，`give` 的接 `eat`，`walkout` 结束时又是小贩一个人守摊，厨房页接着放不会跳。
