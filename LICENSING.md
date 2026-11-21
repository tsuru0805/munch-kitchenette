# 许可说明 · Licensing

Copyright (c) 2026 tsuru0805 (晚晚).

本仓内容按下面四层授权。同一个文件只属于其中一层。
The contents of this repository are licensed in four layers. Each file belongs to exactly one.

| 层 · Layer | 范围 · Scope | 许可 · License |
|---|---|---|
| 软件 · Software | `src/`、`tests/`、`examples/`、`tools/` 里的代码与配置（`src/kitchenette/data/` 的食谱索引除外），`pyproject.toml`，`web/` 里的源码、构建产物与例子页，包括厨房页的源码 `web/page/` 与构建好的页面 `src/kitchenette/page/`（其中的图、字体和第三方代码除外，见下面几行） | [PolyForm Noncommercial 1.0.0](LICENSE) |
| 文档与自有素材 · Docs and our own material | `README.md`、`README.en.md`、`docs/` 里的文字（`docs/animation/` 的动图除外）；厨房页的食玩图 `web/page/assets/kitchen/` 与 `src/kitchenette/page/assets/`（其中 `assets/__assets/clawd/` 除外，它在 Clawd 那一层）；`docs/page/` 的页面截图（`docs/page/card-settled.png` 除外，它在 Clawd 那一层）；试玩页 `docs/play/` 的页面与画面 | [CC BY-NC 4.0](LICENSE-CONTENT) |
| Clawd 的图 · Clawd artwork | `assets/clawd/` 的全部图片、`docs/animation/` 的全部动图、`docs/page/card-settled.png`、`clawd-engine-additions/outfits/`、构建好的厨房页里带的小厨师家务动画 `src/kitchenette/page/assets/__assets/clawd/`（`assets/clawd/` 的副本） | **CC BY-NC-SA 4.0**，不随本仓改授权，见 [`assets/clawd/ATTRIBUTION.md`](assets/clawd/ATTRIBUTION.md) |
| 第三方 · Third party | 公共食谱的索引 `src/kitchenette/data/`（整理自 HowToCook，Unlicense，公有领域）；`clawd-engine-additions/states/` 与 `clawd-engine-additions/tools/`（MIT，接在上游引擎的代码上）；字体 `web/fonts/`、`web/page/public/fonts/`、`src/kitchenette/page/fonts/`（SIL OFL 1.1）；打进厨房页脚本里的第三方代码（清单与许可全文见 `src/kitchenette/page/THIRD-PARTY.txt`）；依赖包 | 各自原许可，逐项见 [NOTICE](NOTICE) |

- 个人、爱好、学习、研究等非商业用途可以使用、修改、再分发（再分发须附上许可全文或链接，以及 NOTICE 里以 `Required Notice:` 开头的行）。
  Personal, hobby, study and research use is fine: use it, change it, pass it on (keep the license text or a link to it, and the `Required Notice:` lines from NOTICE).
- **商业用途不在授权范围内**，需要另行书面授权——联系 [tsuru0805](https://github.com/tsuru0805)。
  **Commercial use is not covered** and needs a separate written license — contact [tsuru0805](https://github.com/tsuru0805).

## Clawd 单列 · Clawd is separate

小厨师是 Clawd。Clawd 是 Anthropic 为 Claude Code 创作的角色；这个仓是非官方同人作品，与 Anthropic 没有隶属关系，没有得到其赞助或背书。
The little cook is Clawd, a character created by Anthropic for Claude Code. This repository is an unofficial fan work; it is not made by, affiliated with, sponsored by or endorsed by Anthropic.

- 小厨师的图改编自 [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes)（动画 Luin Luinaris，衣服 Charlie Luinaris），按上游要求保持 **CC BY-NC-SA 4.0**：非商用、署名、改了要说明、改编件用同一许可分享。
  The cook's images are adapted from [clawds-new-clothes](https://github.com/CharlieLuinaris/clawds-new-clothes) (animation by Luin Luinaris, outfits by Charlie Luinaris) and stay under **CC BY-NC-SA 4.0**: non-commercial, with attribution, saying what you changed, and sharing adaptations under the same license.
- 这里的任何许可都**不授予**与 Clawd 角色、以及「Clawd」「Claude」「Claude Code」「Anthropic」这些名称和标识相关的权利。不做周边、不上架表情商店、不做任何暗示与 Anthropic 有官方关系的事。
  No license here grants any right in the Clawd character or in the names and marks "Clawd", "Claude", "Claude Code" and "Anthropic". No merchandise, no sticker-store listings, nothing that implies an official connection with Anthropic.
- Anthropic 或上游作者要求修改或撤下的，照办。
  If Anthropic or the upstream authors ask for something to be changed or removed, it will be.
- 想换成自己的小人：见 [`docs/ANIMATION.md`](docs/ANIMATION.md)，换掉之后上面这一节就与你的小人无关了。
  To use your own cook instead, see [`docs/ANIMATION.md`](docs/ANIMATION.md); once you have, this section no longer applies to your sprites.
