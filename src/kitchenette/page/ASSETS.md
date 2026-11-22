# What the kitchen page ships, and where it comes from

[中文在下面](#厨房页随包带的东西和来源)

This file travels with the built page (`/page/ASSETS.md`).

## Pictures

All pictures are the authors' own material. They were made for this kitchen with ChatGPT's image generation under the authors' own subscription, then cut out, cleaned and packed by script; nothing here was taken from a third party. They are licensed with the rest of the repository's content (see `LICENSING.md` and `LICENSE-CONTENT` at the repository root).

| Files (under `assets/`) | Count | What |
|---|---|---|
| `__docs/play/img/base_{day,dusk,night}.webp` | 3 | The empty kitchen in three lights (day / dusk / night): fridge, two wall shelves, cork board, a small window with a sill, the counter with the sink and the drying rack. Every position on the page is measured on it. The same files as the online demo in `docs/play/`. |
| `__docs/play/img/{day,dusk,night}_{fl1,fl2,jars,dish}_<n>.webp` | 102 | The pieces put back onto it in each light, cut out to the thing itself: six kinds of flowers on the sill, each fresh / droopy / wilted; the three jars, each empty / fruit / pickles; the drying rack empty / a few / full; the sink empty / a few / piled up / foam. |
| `kitchen/fridge/<ingredient>_{fresh,meh,bad}.png` | 99 | The 33 built-in ingredients, each in three states of freshness. |
| `kitchen/fridge/snack_*.png` | 8 | The five snacks on the default shelf; coffee has one picture per flavour. |
| `kitchen/fridge/staple_{oil,soy,salt,rice}.png` | 4 | The four staples. |
| `kitchen/fridge/dish_{bowl,plate,cup}.png`, `…_burnt.png` | 6 | What a dish is served in, and the same burnt. |
| `kitchen/fridge/coupon.png`, `kitchen/fridge/buy.png` | 2 | The grocery coupon (the page prints the words on it) and the "buy him groceries" tote on the fridge door. |
| `kitchen/ring.png` | 1 | The red pen circle around a chosen thing. Drawn by code (one hand-written curve), not generated. |

The receipt, the menu strips and the notes on the cork board are paper: the page draws them, there is no picture file.

An ingredient kind you add yourself has no picture in this package. It shows the first character of its name until the server has drawn one (only when an art provider is configured; see `docs/HOOKS.md`).

### The cook's chores (a different license)

| Files (under `assets/`) | Count | What |
|---|---|---|
| `__assets/clawd/{toque,scarf}/{vendor,machine}_*.{webp,png}`, `__assets/clawd/{toque,scarf}/base.png` | 24 | The little cook in his two outfits buying from the vendor and loading the dishwasher (9 animated clips each, 2 still last frames each), and his still standing pose, played in the vendor and plates tabs. (Washing up by hand plays on the washing card in the chat, not here.) Copies of the same files in `assets/clawd/` at the repository root. |
| `__assets/clawd/dishes/<kind>_cells.png` | 14 | The fourteen small pixel dishes the cook holds up on the settled card (stir-fry, soup, noodles, rice bowl, fried rice, fried egg, fish, meat, steamer, bake, salad, dessert, drink, plain bowl), one pixel per cell, drawn by tsuru0805 on the cook's grid (they do not depict Clawd; same license). The dish book shows one where a page has no picture of its own: in colour for a dish made, as a flat grey silhouette for one only collected. Copies of the same files in `assets/clawd/dishes/`. |

These are not the authors' own material in the sense above: the cook is Clawd, a character created by Anthropic for Claude Code, drawn with the engine of [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) (animation and engine by Luin Luinaris, postie concept and pixel corrections by Charlie Luinaris); the outfits and moves were added for this project. They are licensed **CC BY-NC-SA 4.0**, unofficial fan work, not affiliated with or endorsed by Anthropic. Credits and what was changed: `assets/clawd/ATTRIBUTION.md` at the repository root.

## Fonts

| Where | Font | License | What ships |
|---|---|---|---|
| All Chinese and running text | **Noto Serif SC**, weights 400 and 300 (© 2017-2024 Adobe; the same design is published as Source Han Serif) | SIL Open Font License 1.1, `fonts/OFL-NotoSerifSC.txt` | `fonts/NotoSerifSC-{Regular,Light}.{common,rare}.woff2`: about 1.5 MB per weight, split so that a browser fetches the `rare` part only when a character outside the 3755 most common ones appears. |
| Numbers (satiety, counts, amounts, dates on notes) | **Bodoni Moda**, weight 400, in the 11 pt, 28 pt and 96 pt optical sizes (© 2020 The Bodoni Moda Project Authors) | SIL Open Font License 1.1, `fonts/OFL-BodoniModa.txt` | `fonts/BodoniModa{11pt,28pt,96pt}-Regular.woff2`, Basic Latin and Latin-1 only, about 16 KB each. |

A copy of Noto Serif SC / Source Han Serif SC installed on the device is used first, and then nothing is downloaded for that weight. The families are declared in `fonts.css`; `web/page/scripts/subset_fonts.py` cuts the files.

---

# 厨房页随包带的东西和来源

这个文件跟着构建好的页面一起走（`/page/ASSETS.md`）。

## 图

所有图都是作者自己的素材：为这间厨房用 ChatGPT 的出图功能（作者自己的订阅）画的，再用脚本抠图、清边、打包；没有任何一张取自第三方。许可随仓库的内容部分（见仓库根目录的 `LICENSING.md` 和 `LICENSE-CONTENT`）。

| 文件（`assets/` 下） | 张数 | 是什么 |
|---|---|---|
| `__docs/play/img/base_{day,dusk,night}.webp` | 3 | 空厨房的三档光（白天 / 傍晚 / 夜里）：冰箱、墙上两层隔板、软木板、带窗台的小窗、台面上的水槽和沥水架。页面上所有位置都是对着它量的。和 `docs/play/` 在线试玩用的是同一批文件。 |
| `__docs/play/img/{day,dusk,night}_{fl1,fl2,jars,dish}_<n>.webp` | 102 | 每档光下贴回去的小块，只抠东西本身：窗台上的六种花，各有刚买 / 有点蔫 / 谢了；三只罐子，各有空 / 泡着水果 / 泡着腌菜；沥水架空 / 几只 / 摆满；水槽空 / 几只 / 堆高 / 在刷（泡沫）。 |
| `kitchen/fridge/<食材>_{fresh,meh,bad}.png` | 99 | 自带的 33 样食材，每样三种新鲜度。 |
| `kitchen/fridge/snack_*.png` | 8 | 默认零食架上的五款；咖啡每种口味一张。 |
| `kitchen/fridge/staple_{oil,soy,salt,rice}.png` | 4 | 四样常备。 |
| `kitchen/fridge/dish_{bowl,plate,cup}.png`、`…_burnt.png` | 6 | 盛菜的碗、盘、杯，以及糊了的样子。 |
| `kitchen/fridge/coupon.png`、`kitchen/fridge/buy.png` | 2 | 买菜券（上面的字是页面印的）和冰箱门上「给他买菜」的布袋。 |
| `kitchen/ring.png` | 1 | 圈住选中那样的红笔圈。是代码画的（手写的一条曲线），不是出图。 |

用餐小票、菜单短册、软木板上的纸条是纸，由页面自己画，没有图片文件。

你自己添的食材种类，包里没有图：在服务端画出来之前，先显示名字的头一个字（要接了画图函数才会画，见 `docs/HOOKS.md`）。

### 小厨师的家务（许可不同）

| 文件（`assets/` 下） | 个数 | 是什么 |
|---|---|---|
| `__assets/clawd/{toque,scarf}/{vendor,machine}_*.{webp,png}`、`__assets/clawd/{toque,scarf}/base.png` | 24 | 小厨师穿两套衣服跟小贩买东西、往洗碗机放盘子（每套 9 段动图、2 张末帧），以及他站好的静止姿势，在小贩、盘子两页里放。（自己刷盘子在聊天里的刷盘子卡上放，不在这里。）和仓库根目录 `assets/clawd/` 里是同一批文件。 |
| `__assets/clawd/dishes/<类别>_cells.png` | 14 | 结算卡上小厨师举着的十四类像素小菜（炒菜、汤、面、盖饭、炒饭、煎蛋、鱼、肉、蒸笼、烤物、沙拉、甜品、饮料、普通一碗），一格一像素，由 tsuru0805 在小厨师的格子上画（画的不是 Clawd，许可相同）。图鉴里没有自己那张图的菜页用它顶上：做过的上色，只收藏没做的是一色灰的剪影。和仓库根目录 `assets/clawd/dishes/` 里是同一批文件。 |

它们不属于上面说的「作者自己的素材」：小厨师是 Clawd——Anthropic 为 Claude Code 创作的角色，用 [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) 的引擎画成（动画与引擎：Luin Luinaris；信差设定与像素修订：Charlie Luinaris），衣服和动作是本项目加的。按 **CC BY-NC-SA 4.0** 提供，非官方同人作品，与 Anthropic 没有隶属关系，没有得到其背书。署名和改了什么见仓库根目录的 `assets/clawd/ATTRIBUTION.md`。

## 字体

| 用在哪 | 字体 | 许可 | 随包带的 |
|---|---|---|---|
| 所有中文和正文 | **思源宋体（Noto Serif SC）** 400 和 300 两个字重（© 2017-2024 Adobe；同一套字也以 Source Han Serif 的名字发布） | SIL Open Font License 1.1，全文在 `fonts/OFL-NotoSerifSC.txt` | `fonts/NotoSerifSC-{Regular,Light}.{common,rare}.woff2`：每个字重约 1.5 MB，切成两份，只有出现 3755 个最常用字以外的字时，浏览器才去取 `rare` 那份。 |
| 数字（饱食度、个数、回多少体力、纸条上的日期） | **Bodoni Moda** 400，11 pt、28 pt、96 pt 三个光学尺寸（© 2020 The Bodoni Moda Project Authors） | SIL Open Font License 1.1，全文在 `fonts/OFL-BodoniModa.txt` | `fonts/BodoniModa{11pt,28pt,96pt}-Regular.woff2`，只留基本拉丁和 Latin-1，每个约 16 KB。 |

设备上装了思源宋体（Noto Serif SC / Source Han Serif SC）就先用设备上的，那个字重就什么都不下载。字体族在 `fonts.css` 里声明；切字体文件的脚本是 `web/page/scripts/subset_fonts.py`。
