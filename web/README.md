# The cooking card

[中文在下面](#做饭卡)

`<kitchenette-cooking-card>` shows one pot in a chat: a ticket-stub card that counts down in real time, with a small cook working on its top edge. It is a plain custom element with no framework and no runtime dependencies; one script file, one tag.

What the cook does and when is described in [`docs/ANIMATION.md`](../docs/ANIMATION.md).

## Use it

Copy three folders to your site, keeping their places relative to each other: `web/dist/`, `web/fonts/` and `assets/clawd/`. Load the script once per page:

```html
<script type="module" src="/kitchenette/web/dist/kitchenette-cooking-card.js"></script>
```

Then give the card its pot in one of two ways.

### 1. You already have the pot's data

```html
<kitchenette-cooking-card id="pot"></kitchenette-cooking-card>
<script type="module">
  document.getElementById("pot").session = {
    id: "ck_01", dish: "Tomato and egg stir-fry", note: "less salt",
    started_at: 1767225600, duration_seconds: 600, method: "stirfry", status: "cooking",
  };
</script>
```

A pot is the object the backend returns: `id`, `dish`, `note`, `duration_seconds`, `started_at` (epoch seconds), `status` (`cooking` / `served` / `cancelled`), `served_at`, `cancelled_at`, `remaining_seconds`, `outcome` (`great` / `ok` / `burnt` / `spoiled`), `ingredients`, `method`. The card needs `id`, `dish`, `started_at` and `duration_seconds`; it uses `note`, `method`, `status` and `outcome` when they are there and ignores the rest.

The card counts down by itself from `started_at` and `duration_seconds`. It makes no request at all, so it only knows what you tell it: when the pot is cancelled or served, assign `session` again with the same `id` and the new `status` and `outcome`. If you never do, the card serves the pot as an ordinary one when the time is up.

You can add `api-base` (see below) to a card that was given its data. The card then also asks the backend whether the pot was cancelled and how it turned out. If those requests fail, the countdown still runs and nothing is shown about it, but the card cannot learn that a pot was cancelled or how it turned out.

### 2. The card fetches the pot from the kitchenette backend

```html
<kitchenette-cooking-card api-base="https://kitchen.example.com" session-id="ck_01" token="a-token-for-browsers"></kitchenette-cooking-card>
```

The card reads `GET <api-base>/api/kitchen?session_id=<id>` and expects `{ "now": ..., "timezone": "...", "session": { ... } }`. It reads once when it appears, every 15 seconds while the pot is cooking (to notice a cancelled pot), and every 1.5 seconds for up to 6 seconds once the time is up (to learn the outcome). After that it only reads once more each time the page comes back to the foreground.

If the page is not served by the kitchenette server itself, the browser only lets the card read the answer when the server lists the page's address: add it to `cors_origins` under `[server]` in the backend's settings (see [`docs/CONFIG.md`](../docs/CONFIG.md)).

**When the first read fails, there is nothing to count down from.** The card stays on the page and says why in one line, and fires a `kitchenette-error` event:

| The line on the card | `detail.kind` | What to check |
|---|---|---|
| Can't load this pot: the kitchen server can't be reached. | `unreachable` | Is the server running? Is `api-base` right? |
| Can't load this pot: the browser blocked the request. This page is not on the kitchen server's list of allowed sites. | `blocked` | Add the page's address to `cors_origins`. |
| Can't load this pot: the kitchen server refused it. The token is missing or wrong. | `unauthorized` | The `token` attribute against `server.token`. |
| Can't load this pot: the kitchen server has no pot with this id. | `not_found` | The `session-id`. |
| Can't load this pot: the kitchen server answered with an error (status 500). | `server` | The server's log. |
| Can't load this pot: the kitchen server's answer was not understood. | `bad_response` | Is `api-base` pointing at something else? |

```js
card.addEventListener("kitchenette-error", (e) => {
  // e.detail = { kind: "unauthorized", status: 401, message: "the kitchen server refused the request: ... (status 401)", error }
  console.warn(e.detail.kind, e.detail.status, e.detail.message);
});
```

`status` is the HTTP status when the browser let the page see one, otherwise `null`. The card tries again when the page comes back to the foreground, or when you change `api-base` or `session-id`. The words of the line can be replaced through `strings.loadFailed`.

Once the first read has worked, later reads that fail are ignored: the countdown goes on, and the card simply does not learn about a cancelled pot or an outcome until a read works again.

### Attributes

| Attribute | |
|---|---|
| `api-base` | Base URL of the kitchenette backend. |
| `session-id` | The pot to fetch, when no `session` object is given. |
| `token` | Sent as `Authorization: Bearer <token>` with every request. It is read each time, so you can replace it. Anyone who can read the page can read an attribute; use a token meant for the browser. |
| `timezone` | The time zone the clock times on the card are written in, as an IANA name such as `Asia/Tokyo`. See "Clock times" below. |
| `assets` | Folder of the sprite pack. Default: `../../assets/clawd/` relative to the script file. |
| `fonts` | Folder of the font files. Default: `../fonts/` relative to the script file. `fonts="none"` registers no fonts at all. |
| `lang` | `en` for English words on the card; anything else (or nothing) gives the original Chinese. |
| `theme` | `dark` for the dark palette. |

### Properties

| Property | |
|---|---|
| `session` | The pot object. Assign it again with the same `id` when its `status` or `outcome` changes; a different `id` starts the card over. |
| `probe` | `async (sessionId, fresh) => ({ status, outcome })`. Where the card asks whether the pot was cancelled and how it turned out. Set it to use your own transport instead of `api-base`. |
| `clock` | `() => epoch milliseconds`. Defaults to `Date.now`. The example page uses it to run time fast. |
| `manifest` | The sprite registry, to use your own character (see [`docs/ANIMATION.md`](../docs/ANIMATION.md#using-your-own-character)). |
| `strings` | An object overriding any of the words on the card (see [`src/strings.ts`](src/strings.ts)). |
| `phase`, `segment`, `outfit` | Read-only: where the pot is right now, which clip is on, which outfit this pot wears. |

### Clock times

The card writes two clock times, when the pot went on and when it is ready ("On at 17:03 · 10 min · ready 17:13"). Which time zone they are in:

1. the backend's, when the card reads from `api-base` and the answer carries a non-empty `timezone`;
2. otherwise the card's `timezone` attribute;
3. otherwise the visitor's device.

The backend writes its own notes ("on the stove at 16:03") in the time zone it is configured with. When that differs from the visitor's device, the card and the notes would name different hours for the same moment; with `api-base` the card follows the backend by itself, and with a `session` object you can set `timezone` to the backend's zone. A name that is not a time zone is skipped. The countdown itself does not depend on any time zone.

### Without the sprite pack

The cook is optional. If `assets/clawd/` is not on your site (and no other pack is given), the card asks for one image, finds nothing, and asks for nothing more on that page: without sprites the card only counts down, the cook is simply not there. The browser console shows that one 404.

### Colours and fonts

Everything is a CSS custom property you can set on the element or any ancestor:

```css
kitchenette-cooking-card {
  --kitchenette-paper: #FEFEFD;         /* card ground */
  --kitchenette-ink: #2A3550;           /* outline, dish name, clock */
  --kitchenette-accent: #4159E8;        /* the block on the left, progress, status word */
  --kitchenette-mute: #5A6377;          /* note and the line at the bottom */
  --kitchenette-hair: rgba(42, 53, 80, 0.22);   /* the empty part of the progress line */
  --kitchenette-shadow: #394CB3;        /* the solid offset shadow */
  --kitchenette-shadow-offset: 4px;
  --kitchenette-font-serif: "Kitchenette Serif", "Songti SC", "Noto Serif SC", serif;
  --kitchenette-font-display: "Kitchenette Bodoni 28", serif;        /* the clock */
  --kitchenette-font-display-small: "Kitchenette Bodoni 11", serif;  /* the small caps under the glyph */
}
```

Fonts:

| Where | Font | What ships here |
|---|---|---|
| The clock and the small caps | **Bodoni Moda** (© 2020 The Bodoni Moda Project Authors, SIL Open Font License 1.1), the 28 pt and 11 pt optical sizes, weight 400 | Yes: `web/fonts/BodoniModa28pt-Regular.woff2` and `BodoniModa11pt-Regular.woff2`, cut down to Basic Latin, with the license in `web/fonts/OFL-BodoniModa.txt`. The element registers them as "Kitchenette Bodoni 28" and "Kitchenette Bodoni 11". |
| All other text | **Songti SC**, the Song typeface on Apple systems; where the device does not have it, **Noto Serif SC** (© 2017-2024 Adobe, SIL Open Font License 1.1; the same design is also published as Source Han Serif), weights 400 and 700 | Songti SC itself cannot be redistributed and is not here. Noto Serif SC is: four WOFF2 files in `web/fonts/`, about 3.1 MB together, with the license in `web/fonts/OFL-NotoSerifSC.txt`. The element registers them as "Kitchenette Serif". |

How the text font is chosen, and what gets downloaded:

- A font that is already on the device is used first and nothing is downloaded: the system's Songti SC (macOS has it), or an installed Noto Serif SC / Source Han Serif SC.
- Otherwise the browser downloads the bundled Noto Serif SC, and only the parts the card's text needs. Each weight is cut in two: `common` (Latin, punctuation, kana and the 3,755 most common Chinese characters; 891 KB regular, 917 KB bold) and `rare` (3,084 less common characters; 649 KB regular, 669 KB bold). A typical card fetches the two `common` files, about 1.8 MB, once; the browser caches them.
- The bundled files cover 7,967 characters. A character outside them is drawn with whatever serif the device has.

To use your own font instead, set `--kitchenette-font-serif` to it: the bundled files are only fetched when "Kitchenette Serif" is actually used, so nothing is downloaded. To drop the bundled serif but keep the system one, set `--kitchenette-font-serif: "Songti SC", serif`. To keep the card from registering any font (the numerals included), write `fonts="none"`; you can then leave `web/fonts/` out of your site.

## Try it locally

```sh
node web/scripts/serve.mjs          # serves the repository root on http://127.0.0.1:8123
node web/scripts/serve.mjs 9000     # the same on another port
```

- `http://127.0.0.1:8123/web/examples/` — sample pots, every method, both outfits, every outcome, and a clock you can run at ×10 or ×60 or skip to 8 seconds before a pot is done. Nothing on the page talks to a server.
- `http://127.0.0.1:8123/web/examples/gallery.html` — every clip in the pack.

Any static file server pointed at the repository root works as well.

## Work on it

```sh
cd web
npm install
npm test             # the timing rules, time zones and fetch failures (vitest)
npm run typecheck
npm run build        # writes dist/kitchenette-cooking-card.js
npm run manifest     # after adding or removing files in assets/clawd/
```

| | |
|---|---|
| `src/cookPhase.ts` | Which phase the pot is in: entrance, cooking, serving, leaving, done, cancelled. Pure functions. |
| `src/cookSegments.ts` | Which clip plays at this moment. Pure functions. |
| `src/element.ts` | The element: data, polling, the card, the sprite's slide and cross-fades. |
| `src/api.ts` | Reading a pot from the backend, and naming what went wrong when it cannot be read. |
| `src/manifest.ts`, `src/manifest.generated.ts` | The sprite registry. |
| `src/seats.ts`, `src/seen.ts` | At most two cooks animate at once; which pots this page has already seen. |
| `src/strings.ts`, `src/styles.ts`, `src/spring.ts` | The words, the stylesheet, the entrance bounce. |
| `src/serifRange.generated.ts`, `scripts/subset_serif.py` | Which characters are in the `rare` part of the bundled serif, and the script that cuts the four font files from Noto Serif SC. |

---

# 做饭卡

`<kitchenette-cooking-card>` 在聊天里显示一锅饭：一张票根样子的长条卡，按真实时间倒数，小厨师站在卡的上沿干活。它是一个普通的自定义元素，不依赖任何前端框架，没有运行时依赖：一个脚本文件，一个标签。

小厨师每一段在做什么、什么时候播，见 [`docs/ANIMATION.md`](../docs/ANIMATION.md#卡上的小厨师)。

## 怎么用

把三个目录拷到自己的站点上，彼此的相对位置不变：`web/dist/`、`web/fonts/`、`assets/clawd/`。每个页面引入一次脚本：

```html
<script type="module" src="/kitchenette/web/dist/kitchenette-cooking-card.js"></script>
```

然后用下面两种办法之一把这一锅交给卡。

### 一、你手里已经有这一锅的数据

```html
<kitchenette-cooking-card id="pot"></kitchenette-cooking-card>
<script type="module">
  document.getElementById("pot").session = {
    id: "ck_01", dish: "番茄炒蛋", note: "少放盐",
    started_at: 1767225600, duration_seconds: 600, method: "stirfry", status: "cooking",
  };
</script>
```

一锅饭就是后端返回的那个对象：`id`、`dish`、`note`、`duration_seconds`、`started_at`（秒）、`status`（`cooking` / `served` / `cancelled`）、`served_at`、`cancelled_at`、`remaining_seconds`、`outcome`（`great` / `ok` / `burnt` / `spoiled`）、`ingredients`、`method`。卡必须要的是 `id`、`dish`、`started_at`、`duration_seconds`；有 `note`、`method`、`status`、`outcome` 就用，其余不看。

卡自己按 `started_at` 和 `duration_seconds` 倒数，一个请求都不发，所以它只知道你告诉它的事：这一锅被关火或出锅之后，用同一个 `id` 把带着新 `status`、`outcome` 的对象再赋给 `session` 一次。一直不赋的话，到点后卡按普通的一锅端出来。

给了数据的卡也可以再写上 `api-base`（见下一节）。这时卡还会去问后端「有没有被关火、结果怎么样」。这些请求失败时，倒数照常走，卡上不显示任何提示，但卡不知道这一锅有没有被关火、结果怎么样。

### 二、让卡自己去后端取

```html
<kitchenette-cooking-card api-base="https://kitchen.example.com" session-id="ck_01" token="给浏览器用的口令"></kitchenette-cooking-card>
```

卡读 `GET <api-base>/api/kitchen?session_id=<id>`，回包是 `{ "now": ..., "timezone": "...", "session": { ... } }`。它出现时读一次；还在火上时每 15 秒读一次（看有没有被关火）；到点之后每 1.5 秒读一次、最多 6 秒（等出锅结果）；之后只在页面每次回到前台时再读一次。

如果页面不是由 kitchenette 服务自己提供的，浏览器只有在服务把这个页面的地址列进名单时才让卡读到结果：在后端配置的 `[server]` 里把页面地址加进 `cors_origins`（见 [`docs/CONFIG.md`](../docs/CONFIG.md)）。

**第一次就读不到时，卡没有东西可以倒数。** 卡会留在页面上，用一行字说明原因，同时发出 `kitchenette-error` 事件：

| 卡上那一行 | `detail.kind` | 该查什么 |
|---|---|---|
| 取不到这一锅：连不上厨房服务。 | `unreachable` | 服务起了没有？`api-base` 写对了没有？ |
| 取不到这一锅：浏览器拦下了这次读取，厨房服务的跨站名单里没有这个页面。 | `blocked` | 把页面地址加进 `cors_origins`。 |
| 取不到这一锅：厨房服务拒绝了，口令没带或不对。 | `unauthorized` | 标签上的 `token` 和服务的 `server.token` 对不对得上。 |
| 取不到这一锅：厨房服务里没有这一锅。 | `not_found` | `session-id`。 |
| 取不到这一锅：厨房服务出错了（状态码 500）。 | `server` | 服务的日志。 |
| 取不到这一锅：厨房服务的回答看不懂。 | `bad_response` | `api-base` 是不是指到了别的东西上。 |

```js
card.addEventListener("kitchenette-error", (e) => {
  // e.detail = { kind: "unauthorized", status: 401, message: "the kitchen server refused the request: ... (status 401)", error }
  console.warn(e.detail.kind, e.detail.status, e.detail.message);
});
```

`status` 是浏览器让页面看到的 HTTP 状态码，看不到时是 `null`。页面回到前台时，或者你改了 `api-base`、`session-id` 时，卡会再试一次。那一行字可以用 `strings.loadFailed` 换成自己的。

第一次读到之后，后面再有读取失败就不管它：倒数继续走，只是在下一次读成功之前，卡不知道这一锅有没有被关火、结果怎么样。

### 标签上能写的

| 属性 | |
|---|---|
| `api-base` | 后端地址。 |
| `session-id` | 没给 `session` 对象时，要取的那一锅。 |
| `token` | 每次请求带上 `Authorization: Bearer <token>`。每次请求时现读，可以随时换。写在标签上的东西，能看到页面的人都能看到，请用给浏览器用的口令。 |
| `timezone` | 卡上的钟点按哪个时区写，用 `Asia/Tokyo` 这样的时区名。见下面「钟点」。 |
| `assets` | 素材目录。默认是脚本文件所在位置的 `../../assets/clawd/`。 |
| `fonts` | 字体文件所在的目录。默认是脚本文件所在位置的 `../fonts/`。写 `fonts="none"` 就一个字体都不登记。 |
| `lang` | 写 `en` 时卡上的字是英文；不写或写别的是原本的中文。 |
| `theme` | 写 `dark` 用深色配色。 |

### 用脚本设置的

| 属性 | |
|---|---|
| `session` | 这一锅的数据对象。状态或出锅结果变了，用同一个 `id` 再赋一次；换了 `id` 就整张卡重新开始。 |
| `probe` | `async (sessionId, fresh) => ({ status, outcome })`。卡问「有没有被关火、结果怎么样」的地方。不想用 `api-base` 时，换成自己的取数办法。 |
| `clock` | `() => 毫秒时间戳`，默认 `Date.now`。例子页用它来快进。 |
| `manifest` | 素材登记表，换成自己的小人时用（见 [`docs/ANIMATION.md`](../docs/ANIMATION.md#换成自己的小人)）。 |
| `strings` | 改卡上任何一处文字（见 [`src/strings.ts`](src/strings.ts)）。 |
| `phase`、`segment`、`outfit` | 只读：这一锅现在在哪个阶段、台上在播哪一段、穿的是哪套衣服。 |

### 钟点

卡上写两个钟点：几点下锅、几点出锅（「17:03 下锅 · 做 10 分钟 · 17:13 出锅」）。按哪个时区写：

1. 卡从 `api-base` 读、而且回包里的 `timezone` 不是空的：用后端的；
2. 否则用标签上的 `timezone`；
3. 都没有，用访客设备的。

后端自己写给角色的话（「16:03 开火」）用的是它配置的时区。这个时区和访客设备不一样时，同一个时刻卡上和那些话里会是两个钟点；用 `api-base` 时卡自己会跟后端走，直接给 `session` 对象时可以把 `timezone` 写成后端的时区。写的不是一个真的时区名时，这一项会被跳过。倒数本身和时区无关。

### 没有素材的时候

小厨师不是必需的。站点上没有 `assets/clawd/`（也没给别的素材）时，卡先要一张图，要不到，这个页面上就不再要任何素材：没有素材时卡只有倒数，台上没有小厨师。浏览器控制台里会有那一条 404。

### 颜色和字体

颜色和字体都是 CSS 自定义属性，写在元素上或它的任何一层父元素上都行：

```css
kitchenette-cooking-card {
  --kitchenette-paper: #FEFEFD;         /* 卡的纸底 */
  --kitchenette-ink: #2A3550;           /* 描线、菜名、倒计时 */
  --kitchenette-accent: #4159E8;        /* 左边的色块、进度、状态字 */
  --kitchenette-mute: #5A6377;          /* 备注和最下面那一行 */
  --kitchenette-hair: rgba(42, 53, 80, 0.22);   /* 进度线还没走到的部分 */
  --kitchenette-shadow: #394CB3;        /* 错开的实心投影 */
  --kitchenette-shadow-offset: 4px;
  --kitchenette-font-serif: "Kitchenette Serif", "Songti SC", "Noto Serif SC", serif;
  --kitchenette-font-display: "Kitchenette Bodoni 28", serif;        /* 倒计时数字 */
  --kitchenette-font-display-small: "Kitchenette Bodoni 11", serif;  /* 符号块下面的小字 */
}
```

字体：

| 用在哪 | 字体 | 这里带了什么 |
|---|---|---|
| 倒计时数字、符号块下面的小字 | **Bodoni Moda**（© 2020 The Bodoni Moda Project Authors，SIL Open Font License 1.1），28 pt 与 11 pt 两个光学尺寸，字重 400 | 带了：`web/fonts/BodoniModa28pt-Regular.woff2` 和 `BodoniModa11pt-Regular.woff2`（只留基本拉丁字符），许可全文在 `web/fonts/OFL-BodoniModa.txt`。元素把它们登记成「Kitchenette Bodoni 28」「Kitchenette Bodoni 11」。 |
| 其余所有文字 | **Songti SC（宋体-简）**，苹果系统上的宋体；设备上没有它时用 **Noto Serif SC（思源宋体）**（© 2017-2024 Adobe，SIL Open Font License 1.1），字重 400 与 700 | Songti SC 本身不能随包分发，这里没有。思源宋体带了：`web/fonts/` 下四个 WOFF2，合计约 3.1 MB，许可全文在 `web/fonts/OFL-NotoSerifSC.txt`。元素把它们登记成「Kitchenette Serif」。 |

文字用哪个字体、会下载什么：

- 设备上已经有的字体优先，什么都不下载：系统的 Songti SC（macOS 自带），或者装过的 Noto Serif SC / Source Han Serif SC。
- 都没有时，浏览器才下载随包的思源宋体，而且只下载卡上的字用得到的部分。每个字重切成两份：`common`（拉丁字母、标点、假名和最常用的 3755 个汉字；常规 891 KB，粗体 917 KB）和 `rare`（另外 3084 个不太常用的汉字；常规 649 KB，粗体 669 KB）。一张普通的卡只取两个 `common` 文件，约 1.8 MB，取一次，之后走浏览器缓存。
- 随包文件共 7967 个字符。不在其中的字，用设备上有的衬线字体画。

想换成自己的字体：把 `--kitchenette-font-serif` 设成它。随包文件只在真的用到「Kitchenette Serif」时才会被取，所以不会下载。只想去掉随包的思源宋体、保留系统宋体：写 `--kitchenette-font-serif: "Songti SC", serif`。想让卡一个字体都不登记（数字字体也不要）：写 `fonts="none"`，这时站点上可以不放 `web/fonts/`。

## 在自己电脑上看

```sh
node web/scripts/serve.mjs          # 把仓库根目录开在 http://127.0.0.1:8123
node web/scripts/serve.mjs 9000     # 换一个端口
```

- `http://127.0.0.1:8123/web/examples/`：假数据的样例，能选做法、衣服、出锅结果，时间可以 ×10、×60 快进，也可以直接跳到出锅前 8 秒。页面不连任何服务。
- `http://127.0.0.1:8123/web/examples/gallery.html`：整套素材的每一段。

用别的静态文件服务器指向仓库根目录也一样。

## 改它

```sh
cd web
npm install
npm test             # 计时规则、时区、取数失败的测试（vitest）
npm run typecheck
npm run build        # 生成 dist/kitchenette-cooking-card.js
npm run manifest     # assets/clawd/ 里增删文件之后重新生成登记表
```

| | |
|---|---|
| `src/cookPhase.ts` | 这一锅在哪个阶段：出场、在做、端上来、收回、做完、关火。纯函数。 |
| `src/cookSegments.ts` | 这一刻播哪一段。纯函数。 |
| `src/element.ts` | 元素本身：数据、轮询、卡面、小厨师的位移和换段淡入。 |
| `src/api.ts` | 从后端读一锅饭；读不到时说清是哪一种原因。 |
| `src/manifest.ts`、`src/manifest.generated.ts` | 素材登记表。 |
| `src/seats.ts`、`src/seen.ts` | 同一页最多两个小厨师在动；这个页面见过哪些锅。 |
| `src/strings.ts`、`src/styles.ts`、`src/spring.ts` | 卡上的字、样式表、出场的回弹。 |
| `src/serifRange.generated.ts`、`scripts/subset_serif.py` | 随包宋体的 `rare` 部分有哪些字；从 Noto Serif SC 切出四个字体文件的脚本。 |
