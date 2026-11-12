# The cook's source files

[中文在下面](#小厨师的源文件)

The images in [`assets/clawd/`](../assets/clawd/) are drawn by code: the engine of [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) by Luin Luinaris and Charlie Luinaris, plus the files in this folder. This folder holds only what was added on top of the engine. Nothing of the upstream engine is copied here, and no upstream file was changed.

> **Unofficial fan work.** Everything these files draw is Clawd, a character created by Anthropic for Claude Code. All rights in the character and in the names "Clawd", "Claude", "Claude Code" and "Anthropic" belong to Anthropic, PBC. Not affiliated with, sponsored by or endorsed by Anthropic. Keep what you make with them non-commercial.

## What is here

| | | License (see each file's SPDX header) |
|---|---|---|
| `outfits/chef-toque.cjs` | Tall chef's hat, white double-breasted jacket, red neckerchief. | CC BY-NC-SA 4.0 |
| `outfits/chef-scarf.cjs` | Blue polka-dot headscarf, cream apron with a pink heart pocket. | CC BY-NC-SA 4.0 |
| `states/_kitchen.cjs` | The props: pots, pans, stove, oven, steamer, board, knife, steam, smoke. | MIT |
| `states/_cooksets.cjs` | The seven methods' sets, and the six moves every method shares (`wipe`, `look`, `hot`, `taste`, `serve`, `fail`) built on one skeleton. | MIT |
| `states/cook-wash.cjs`, `states/cook-chop.cjs` | Washing hands, chopping. | MIT |
| `states/cook-<method>-main.cjs` × 7 | Each method's main action, drawn by hand. | MIT |
| `states/cook-<method>-<part>.cjs` × 42 | One line each: they ask `_cooksets.cjs` for their move. | MIT |
| `tools/export_cook_clips.py`, `tools/dump_frames.cjs` | Export the sprite pack from an engine that has these files in it. | MIT |

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

---

# 小厨师的源文件

[`assets/clawd/`](../assets/clawd/) 里的图是代码画出来的：用的是 Luin Luinaris 与 Charlie Luinaris 的 [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) 引擎，加上本目录里的文件。本目录只放在引擎之上新增的东西，不含上游引擎的任何文件，也没有改动上游的任何文件。

> **非官方同人作品。** 这些文件画出来的都是 Clawd——Anthropic 为 Claude Code 创作的角色。角色形象以及「Clawd」「Claude」「Claude Code」「Anthropic」这些名称，一切权利归 Anthropic, PBC。与 Anthropic 没有隶属关系，没有得到其赞助或背书。用它们做出来的东西请只用于非商业用途。

## 这里有什么

| | | 许可（以各文件开头的 SPDX 为准） |
|---|---|---|
| `outfits/chef-toque.cjs` | 高筒厨师帽、白色双排扣厨师服、红领巾。 | CC BY-NC-SA 4.0 |
| `outfits/chef-scarf.cjs` | 蓝底白点头巾、带粉色爱心口袋的米色大围裙。 | CC BY-NC-SA 4.0 |
| `states/_kitchen.cjs` | 道具：锅、平底锅、灶、烤箱、蒸笼、案板、菜刀、热气、烟。 | MIT |
| `states/_cooksets.cjs` | 七种做法各自的一套家伙，以及每种做法共有的六支动作（`wipe`、`look`、`hot`、`taste`、`serve`、`fail`），按同一个骨架出。 | MIT |
| `states/cook-wash.cjs`、`states/cook-chop.cjs` | 洗手、切菜。 | MIT |
| `states/cook-<做法>-main.cjs` × 7 | 每种做法的主动作，手画。 | MIT |
| `states/cook-<做法>-<段>.cjs` × 42 | 每个文件一行：向 `_cooksets.cjs` 要自己那一支。 | MIT |
| `tools/export_cook_clips.py`、`tools/dump_frames.cjs` | 从装好这些文件的引擎里导出整套素材。 | MIT |

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
