# What the kitchen page ships, and where it comes from

[中文在下面](#厨房页随包带的东西和来源)

This file travels with the built page (`/page/ASSETS.md`).

## Pictures

All pictures are the authors' own material. They were made for this kitchen with ChatGPT's image generation under the authors' own subscription, then cut out, cleaned and packed by script; nothing here was taken from a third party. They are licensed with the rest of the repository's content (see `LICENSING.md` and `LICENSE-CONTENT` at the repository root).

| Files (`assets/kitchen/`) | Count | What |
|---|---|---|
| `fridge/bg_kitchen.jpg` | 1 | The empty kitchen: fridge, shelves, cork board, counter. Every position on the page is measured on it. |
| `fridge/<ingredient>_{fresh,meh,bad}.png` | 99 | The 33 built-in ingredients, each in three states of freshness. |
| `fridge/snack_*.png` | 8 | The five snacks on the default shelf; coffee has one picture per flavour. |
| `fridge/staple_{oil,soy,salt,rice}.png` | 4 | The four staples. |
| `fridge/dish_{bowl,plate,cup}.png`, `…_burnt.png` | 6 | What a dish is served in, and the same burnt. |
| `fridge/coupon.png`, `fridge/buy.png` | 2 | The grocery coupon (the page prints the words on it) and the "buy him groceries" tote on the fridge door. |
| `ring.png` | 1 | The red pen circle around a chosen thing. Drawn by code (one hand-written curve), not generated. |

The receipt, the menu strips and the notes on the cork board are paper: the page draws them, there is no picture file.

An ingredient kind you add yourself has no picture in this package. It shows the first character of its name until the server has drawn one (only when an art provider is configured; see `docs/HOOKS.md`).

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

| 文件（`assets/kitchen/`） | 张数 | 是什么 |
|---|---|---|
| `fridge/bg_kitchen.jpg` | 1 | 空厨房：冰箱、搁板、软木板、台面。页面上所有位置都是对着它量的。 |
| `fridge/<食材>_{fresh,meh,bad}.png` | 99 | 自带的 33 样食材，每样三种新鲜度。 |
| `fridge/snack_*.png` | 8 | 默认零食架上的五款；咖啡每种口味一张。 |
| `fridge/staple_{oil,soy,salt,rice}.png` | 4 | 四样常备。 |
| `fridge/dish_{bowl,plate,cup}.png`、`…_burnt.png` | 6 | 盛菜的碗、盘、杯，以及糊了的样子。 |
| `fridge/coupon.png`、`fridge/buy.png` | 2 | 买菜券（上面的字是页面印的）和冰箱门上「给他买菜」的布袋。 |
| `ring.png` | 1 | 圈住选中那样的红笔圈。是代码画的（手写的一条曲线），不是出图。 |

用餐小票、菜单短册、软木板上的纸条是纸，由页面自己画，没有图片文件。

你自己添的食材种类，包里没有图：在服务端画出来之前，先显示名字的头一个字（要接了画图函数才会画，见 `docs/HOOKS.md`）。

## 字体

| 用在哪 | 字体 | 许可 | 随包带的 |
|---|---|---|---|
| 所有中文和正文 | **思源宋体（Noto Serif SC）** 400 和 300 两个字重（© 2017-2024 Adobe；同一套字也以 Source Han Serif 的名字发布） | SIL Open Font License 1.1，全文在 `fonts/OFL-NotoSerifSC.txt` | `fonts/NotoSerifSC-{Regular,Light}.{common,rare}.woff2`：每个字重约 1.5 MB，切成两份，只有出现 3755 个最常用字以外的字时，浏览器才去取 `rare` 那份。 |
| 数字（饱食度、个数、回多少体力、纸条上的日期） | **Bodoni Moda** 400，11 pt、28 pt、96 pt 三个光学尺寸（© 2020 The Bodoni Moda Project Authors） | SIL Open Font License 1.1，全文在 `fonts/OFL-BodoniModa.txt` | `fonts/BodoniModa{11pt,28pt,96pt}-Regular.woff2`，只留基本拉丁和 Latin-1，每个约 16 KB。 |

设备上装了思源宋体（Noto Serif SC / Source Han Serif SC）就先用设备上的，那个字重就什么都不下载。字体族在 `fonts.css` 里声明；切字体文件的脚本是 `web/page/scripts/subset_fonts.py`。
