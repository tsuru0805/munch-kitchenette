# The kitchen page

[中文在下面](#厨房页)

The kitchen as a page: one picture of the whole kitchen in which every thing can be tapped, and under it "the hand", where the thing you tapped is taken down and shown large with what you can do with it. It is the human's side of the kitchen: looking in the fridge, buying groceries, handing out coupons, putting dishes and potions on the menu, feeding. The role's side (cooking, eating, buying with coupons) goes through its tools, not through this page. A pot that is on the stove right now is not on this page either: the cooking card in the chat shows it (see [`web/README.md`](../web/README.md)); its dish appears here once it is served.

The page ships inside the Python package, already built. No node is needed to use it.

## Open it

```bash
kitchenette serve
```

then open <http://127.0.0.1:8765/page/> in a browser. It is laid out as a phone-width column; on a wide window it sits in the middle.

`?who=<role>` opens a given role's kitchen, e.g. `http://127.0.0.1:8765/page/?who=mika`. It has to be a role the server knows: one that has been used before, or one listed under `[roles] allowed`. For a name the server does not know, the page opens the default role and says so in a line under the title (「没有「…」这个角色 · 这是…的厨房」; tap it to put it away). Without `?who=` the page opens the role you looked at last time in this browser, or the default role.

To see it with something in it, without touching your own kitchen:

```bash
python examples/kitchen_page.py
```

This starts a throwaway server (a temporary database, a free port, the fast-forward clock on), stocks it (a fridge with food in every state, coupons, dishes and a potion on the menu, a meal eaten, notes on the cork board, a second role) and prints the page's address. Ctrl-C stops it and deletes the database. `--token something` makes that server ask for a token, to see the token step.

## What each part does

| Part | What you see | What you can do |
|---|---|---|
| Top | Whose kitchen it is; satiety (red when the role is hungry); "晕乎乎的 · 还有 …" while the role is dizzy from spoiled food. With more than one role, their names at the top right. | Tap a name to switch to that role's kitchen. |
| The picture | The kitchen in the light of the hour (day 6:00–17:00, dusk 17:00–19:00, night the rest, by the kitchen's clock; one fades into the next). The fridge filled from what is really in it (each thing drawn fresh, past its best or spoiled), coupons on the freezer door (up to three), snacks on the upper shelf and staples on the lower one, the first three dishes on the counter, a strip of paper per dish under the shelf (up to four), up to three notes pinned on the cork board. With the plays on: the bunch of flowers on the window sill (vendor), the three jars on the counter (jars), plates in the sink and on the drying rack (plates). The picture has only so much room, see below. | Tap any thing to hold it. Tapping an empty spot of the fridge or the counter holds the most urgent thing in the fridge / shows the table. The flowers, a jar, the sink or the rack open their page of the upgrade's sheet. |
| An ingredient in the hand | Name, how many, and per batch: fresh / past its best / spoiled, the day it keeps until, who bought it and when. Below: everything in the fridge, the most urgent first. | Tap another thing in the row to hold that instead. |
| The coupon | How many coupons the role holds, out of how many; the last coupon note. | "发一张": hand out a coupon (dimmed at the cap). "给他买菜": open the grocery sheet. |
| The tote on the fridge door / "给他买菜" | The catalog, by category. | Tick things (tap again to untick) and buy: they go into the fridge without a coupon. "添种类": add an ingredient kind of your own (name, category, whether it can be eaten as it is, how many in a pack, how long it keeps), and remove ones you added. A kind you added shows the first character of its name until the server has drawn a picture (only with an art provider, see [HOOKS.md](HOOKS.md)). |
| Staples | The staples the server lists. | Nothing: staples never run out. |
| A snack | Eaten today out of the daily cap, when the count resets, its tier, and what a serving restores. | "喂一份": feed one (coffee needs a flavour first). `−` / `+` then "存": change this snack's daily cap. With more than one role: choose whom to feed. |
| A dish | Name, how it turned out (很好 / 糊了 / 坏了), its note. Below: everything on the menu, and how many meals today. | "喂给他": feed it (it is crossed off, counts as a meal, and the role is told). "只划掉": cross it off without a meal. "改": change the name and note. "撤": take it off. |
| A potion | How much stamina it restores, its memo. | The same four actions; feeding adds the stamina at once and is not a meal. |
| The dashed strip / "挂一道" | A sheet with two parts. | Put a dish on the menu (name, note). Hang a potion (amount, memo). |
| The receipt | Today's meals and which part of the day each was eaten in. | |
| The cork board | The kitchen's recent notes (bought, tossed, spoiled, coupons, worms …), six to a page. | "更早的" / "新一些": page through them. |
| The row under the hand (the upgrade) | One word per entrance that is switched on: 食谱 · 图鉴 · 成就 · 小贩 · 零花钱 · 盘子 · 罐子. Nothing when all of them are off. | Tap one: a sheet drops from the top with a tab per entrance (see below). |
| The line at the top while a vendor is downstairs | "楼下有卖糖葫芦的 · 还待 20 分钟 →" | Tap it: the vendor tab. |

**What the picture has room for.** The fridge draws at most twelve kinds of ingredient, three to a shelf and three in the drawer, plus the milk in the door; several batches of one kind are drawn once. The counter shows the first three dishes and the shelf carries at most four strips. A kind you added yourself is not drawn in the picture until it has a picture of its own. Whatever does not fit is still there: the row at the bottom of the hand always lists everything in the fridge and everything on the menu, and each can be tapped there.

**What asks first and what does not.** Three things are asked on a slip of paper before they happen, on a dish or a potion: "喂给他" (feed it), "只划掉" (cross it off) and "撤" (take it off). Everything else happens at the tap: handing out a coupon, buying groceries, feeding a snack, saving a snack's cap, adding an ingredient kind and removing one you added ("撤掉"), drawing a picture again, putting a dish or a potion up, and saving a change.

**The upgrade's sheet.** 食谱: today's picks as the role reads them, searching the public recipes, "想吃这个" to order one (with orders on), the orders and withdrawing one, the role's own book (with its tasting notes), a page's code, and taking someone else's code (previewed first, then "收下"). 图鉴: one row per dish made (made / made well / eaten, the best result, the ingredients, the role's sentence), your comment on each; the recipes collected but not made yet. 成就: all of them, earned or not (the role only ever reads the earned ones). 小贩: what the vendor downstairs has, prices and what is left, "替他买" (free for the role), what the role spent today, its pocket money and giving some, the flower on the sill, and the role's requests for a new kind of flower to agree to or not. 零花钱: how much the role has and, with the built-in ledger, giving some — as much as you decide, whenever you like; the role is told on its next turn (with your own wallet configured, the money is given there). 盘子: the plates by state, "让他自己刷" on or off, how many to wash at a time. The 小贩 and 盘子 tabs have a small panel at the top with the cook doing the chore: at the window buying from the vendor, washing up step by step (and the plate he drops, once its time is up and it turned out broken), loading the dishwasher; with "reduce motion" on, a still frame (see [ANIMATION.md](ANIMATION.md#chores-on-the-kitchen-page)). 罐子: the three jars, what came out of them, feeding one serving, the daily cap. An entrance not opened yet on this device carries a small red 「新」 until it is opened once (kept in the browser's localStorage). None of this is drawn onto the picture; what the picture shows of the plays is the things themselves (the flowers, the jars, the plates), drawn in the same light.

**The plays in the picture.** The flowers: one bunch at a time, the kind (six with pictures: rose, sunflower, tulip, bellflower, chamomile, narcissus) and how it looks (fresh / droopy / wilted); a kind without a picture (a new kind you agreed to) leaves the sill empty in the picture (nothing to tap there either) and is listed on the vendor page. A jar: empty, fruit (sealed with sugar or honey) or pickles (salt). The sink: none, a few (1–3), piled up (4 and more), foam while he is washing. The rack: the plates of the last washing, as they come out and for three hours after. A play that is switched off draws nothing of its own (the sill stays empty; the sink and the rack are part of the room and stay empty).

When the server has **stamina** switched off, the page shows nothing about stamina: no restore amounts on snacks, no potion part on the "挂一道" sheet. When **satiety** is switched off, the satiety number is not shown. See `[stamina] enabled` and `[satiety] enabled` in [CONFIG.md](CONFIG.md).

When the server runs with the fast-forward clock (`[server] dev_clock = true`, for demos only), a very small "过一小时 / 过一天" appears in the top left corner. It moves the clock of the whole server. On a server without it, it is not there.

The picture has room for the five snacks of the default shelf and the four default staples. If you change the snack list or the staples in the settings, everything is still listed in the hand; only things with a bundled picture are drawn in the picture.

## When the page reads again

The role changes its kitchen through its tools while the page is open, so the page does not only read once:

- when it opens, and when you switch to another role;
- after you hand out a coupon, buy groceries or feed a dish (the fridge, satiety and today's meals are read again; the other things you do are shown directly);
- every 30 seconds while the page is visible;
- at once when it comes back to the front (the tab is switched back to, the phone is unlocked).

While the page is hidden it reads nothing. A 30-second turn is skipped while you are in the middle of something (a sheet or a question is open, or a request is on its way), so nothing you are typing is touched; the next turn comes 30 seconds later. Something the role does therefore shows up here within about half a minute, without reloading.

## Tokens

The files under `/page/` are public; the data behind them is not. When `[server] token` is set, the page needs the token to read anything.

- **Opened on its own**, the page asks for the token once (the step says which one: the `token` under `[server]` in the server's settings) and keeps it in this browser's local storage. "换口令 →" at the bottom of the page forgets it.
- **Embedded** in another page or an app, the host hands the token over in a message (below) and the page stores nothing. Until it has one, the frame says what it is waiting for: 「在等嵌入它的页面给口令…」, or 「口令不对 · 在等嵌入它的页面重新给」 after a token the server refused, or 「厨房没连上 · 在等嵌入它的页面重试」 when the server could not be reached.

Either way the token is only ever sent as an `Authorization: Bearer` header. It is never part of an address, so it does not end up in the server's log, in the browser's history or in a referrer. Do not put it in a link yourself. Outside your own machine, serve over HTTPS (a reverse proxy or a tunnel in front of the server), or the token crosses the network in the clear.

## Embedding

### In an `<iframe>`

1. On the kitchen server, list the origin of the page that will frame it:

   ```toml
   [server]
   embed_origins = ["https://chat.example.com"]
   ```

   Without this the browser refuses to show the kitchen page in a frame on another site (the server sends `Content-Security-Policy: frame-ancestors 'self'` plus what you list). An origin is `scheme://host[:port]`, nothing after it.

2. Frame it with `?host=<your page's origin>`:

   ```html
   <iframe id="kitchen" src="https://kitchen.example.com/page/?host=https%3A%2F%2Fchat.example.com"
           style="width: 390px; height: 780px; border: 0"></iframe>
   ```

   The kitchen page talks to that one origin only. Where the browser can tell who the real parent is (Chrome, Safari), a `?host=` that does not match it is ignored. A framed page without `?host=` talks to nobody and behaves as if opened on its own (it asks for the token itself).

3. When the page says `ready`, answer with `init`:

   ```js
   const KITCHEN = "https://kitchen.example.com";
   const frame = document.getElementById("kitchen");
   window.addEventListener("message", (e) => {
     if (e.origin !== KITCHEN || e.source !== frame.contentWindow) return;   // accept from the kitchen only
     if (e.data.type === "ready") {
       frame.contentWindow.postMessage(
         { v: 1, id: "1", type: "init", payload: { credential: "<the token>", who: "mika" } },
         KITCHEN,                                                             // never "*"
       );
     }
     if (e.data.type === "close") { /* the person pressed "← 返回": hide the frame */ }
   });
   ```

A complete host page is in [`examples/page_embed.html`](../examples/page_embed.html).

### Messages

Every message is `{ "v": 1, "id": "<any string>", "type": "<type>", "payload": { … } }`.

| Direction | `type` | `payload` | |
|---|---|---|---|
| page → host | `ready` | `{v: 1}` | The page can take `init` now. Sent again after every reload: answer each one. |
| page → host | `close` | | The person pressed "← 返回" (the link is only there when embedded). |
| host → page | `init` | `{apiBase?, credential?, who?}` | `credential` = the token (leave it out when the server has none). `who` = the role to open; it has to be one the server lists. `apiBase` = the kitchen server's origin; leave it out when the page is served by that server. |
| host → page | `role` | `{who}` | Show this role's kitchen. Refused for a role the server does not list. |
| host → page | `logout` | | Forget the token and wait for a new `init`. |

The page answers every host message with `{ "v": 1, "id": "<the same id>", "ok": true, "result": {…} }` or `{ …, "ok": false, "error": "<why>" }`. `init` is answered once the server has accepted the token; it fails with `the kitchen server refused the credential` or `the kitchen server cannot be reached`, and can be sent again.

A role the server does not list is answered with `ok: false` and `unknown role "<name>": the kitchen server lists "a", "b"`. For `role` the kitchen stays on the role it was showing. For `init` the token was still accepted and the kitchen is open, on the default role (the error ends with `; showing "<default>"`). In both cases the page also says so in a line under the title.

### In an app's web view

The page uses a native bridge instead of `postMessage` when it finds one of these as it loads (or when its address carries `?embed=native`):

| Platform | Page → app | App → page |
|---|---|---|
| iOS `WKWebView` | `window.webkit.messageHandlers.kitchenette.postMessage(json)` | `evaluateJavaScript("window.kitchenette && window.kitchenette.receive(" + json + ")")` |
| react-native-webview | `window.ReactNativeWebView.postMessage(json)` | `injectJavaScript("window.kitchenette && window.kitchenette.receive(" + json + ")")` |
| Android `WebView` | `window.KitchenetteHost.postMessage(json)` (from `addJavascriptInterface(obj, "KitchenetteHost")`) | `evaluateJavascript("window.kitchenette && window.kitchenette.receive(" + json + ")", null)` |

The messages are the same; from the page they arrive as JSON strings. Register the bridge before the page loads, send `init` only after `ready`, and keep the web view on the kitchen's origin so the bridge is not exposed to other sites. A web view is not a frame: `embed_origins` does not apply to it.

### Hosting the page's files somewhere else

The build can also be served from another place than the kitchen server (a static host, your own app's bundle). Three things then change:

- Build it for the path it will be served under: `KITCHENETTE_PAGE_BASE=/my/path npm run build` (see "Rebuilding"), and copy `web/page/dist/`.
- Tell the page where the kitchen is: `?api=https://kitchen.example.com` in its address when opened on its own, or `apiBase` in `init` when embedded.
- On the kitchen server, let that site read `/api` from a browser: `[server] cors_origins = ["https://where-the-page-is.example.com"]`.

## Rebuilding

The source is in `web/page/` (React Native components run in the browser through Expo's web export). You only need this to change the page.

```bash
cd web/page
npm install
npm run build        # exports to web/page/dist/ and copies it to src/kitchenette/page/
```

`src/kitchenette/page/` is what the Python package ships and what `/page/` serves; commit it together with the source change.

```bash
npm test             # the page's unit tests
npm run typecheck
npm start            # a dev server with hot reload; pass ?api=http://127.0.0.1:8765 and list its origin in cors_origins
```

Two scripts drive the built page in a headless browser against real servers they start themselves (a temporary database each). They need [Playwright](https://playwright.dev), which is not a dependency of this package:

```bash
# from web/page/, with the repository installed in the Python you name
PW_DIR=/path/to/node_modules KITCHENETTE_PYTHON=python3 node e2e/walk.cjs     # every thing that can be tapped
PW_DIR=/path/to/node_modules KITCHENETTE_PYTHON=python3 node e2e/modes.cjs    # the token step, switches off, embedding
```

Other scripts in `web/page/scripts/`: `gen-art.mjs` (the picture table, after adding or replacing a picture), `gen-scene.mjs` (the kitchen in three lights and its pieces, read from the online demo `docs/play/`; run it after the demo was rebuilt), `gen-chores.mjs` (the cook's chore clips, used from `assets/clawd/`; run it after the sprite pack changed), `subset_fonts.py` (the font files), `contract_fixture.py` (the server answers the unit tests read).

## Pictures, fonts, third-party code

- **Pictures** (`web/page/assets/kitchen/`, 120 files, and the 105 of `docs/play/img/` that the page uses from there): the authors' own material, made with ChatGPT's image generation under the authors' own subscription and cut out by script; the red pen circle is drawn by code. Nothing from a third party.
- **Fonts**: Noto Serif SC (weights 400 and 300) and Bodoni Moda (three optical sizes), both under the SIL Open Font License 1.1, cut down and shipped as WOFF2 with the license texts. A copy of Noto Serif SC or Source Han Serif SC installed on the device is used first, and then nothing is downloaded.
- **Code in the script bundle**: React, React DOM, React Native for Web, Expo and a few small packages, all MIT except one BSD-3-Clause. The list with every license text is generated at build time.

The full account ships with the page: [`/page/ASSETS.md`](../web/page/public/ASSETS.md) and `/page/THIRD-PARTY.txt` (in the repository: `src/kitchenette/page/THIRD-PARTY.txt`).

---

# 厨房页

把厨房做成一个页面：一张画着整间厨房的图，图上每样东西都能点；图下面是「手边」，点了哪样，哪样就被拿下来放大，旁边写着能对它做什么。这是「人」这一侧的厨房：看冰箱、买菜、发券、往菜单上挂菜和药剂、投喂。小机那一侧（做饭、吃、用券买菜）走的是工具，不经过这个页面。小机正在火上的锅也不在这一页，在聊天里的做饭卡上（见 [`web/README.md`](../web/README.md)）；出锅之后那道菜才出现在这里。

页面已经构建好，随 Python 包一起装上。用它不需要装 node。

## 打开

```bash
kitchenette serve
```

然后用浏览器打开 <http://127.0.0.1:8765/page/>。页面按手机宽度排成一列；窗口宽的时候它在正中间。

地址后面加 `?who=<角色>` 可以直接打开某个角色的厨房，比如 `http://127.0.0.1:8765/page/?who=mika`。这个角色得是服务认识的：以前用过的，或者写在 `[roles] allowed` 里的。写了服务不认识的名字，页面会打开默认角色的厨房，并在标题下面写一行说明（「没有「…」这个角色 · 这是…的厨房」，点一下收起）。不加 `?who=` 的话，打开的是这个浏览器上次看的那个角色，没有就是默认角色。

想先看看里面有东西的样子、又不想动自己的厨房：

```bash
python examples/kitchen_page.py
```

它会起一个用完就扔的服务（临时的库、空闲的端口、开着快进钟），先放好东西（各种新鲜度的一冰箱食材、买菜券、菜单上的菜和一瓶药剂、吃过的一顿、软木板上的纸条、第二个角色），然后打印页面地址。按 Ctrl-C 停掉并删掉临时库。加 `--token 随便什么` 可以让这个服务要口令，用来看页面问口令的那一步。

## 每一块能做什么

| 哪一块 | 看到什么 | 能做什么 |
|---|---|---|
| 顶上 | 这是哪个小机的厨房；饱食度（他饿了会变红）；吃了坏掉的东西之后的「晕乎乎的 · 还有 …」。角色不止一个时，右上角有各人的名字。 | 点名字切到那个角色的厨房。 |
| 画 | 按厨房的钟点换光（白天 6 点到 17 点、傍晚 17 点到 19 点、其余是夜里；换的时候整张淡过去）。冰箱按真实库存摆（每样按新鲜、不太新鲜、坏了画成不同的样子），冷冻门上的买菜券（最多画三张），上层搁板的零食、下层搁板的常备，台面上的前三道菜，搁板下面一道菜一条的短册（最多四条），软木板上钉着的纸条（最多三张）。玩法开着时还有：窗台上的那束花（小贩）、台面上的三只罐子（罐子）、水槽和沥水架里的盘子（盘子）。画上的位置有限，见下面。 | 点哪样就拿哪样。点冰箱或台面的空处：拿冰箱里最该先用掉的那样 / 看桌上。点花、罐子、水槽或沥水架：打开升级那张纸上对应的那一页。 |
| 手边的一样食材 | 名字、几个；每一批各是新鲜 / 不太新鲜 / 坏了、能放到哪天、谁买的、哪天买的。下面一排是冰箱里全部，最该先用掉的在前。 | 点那一排里的另一样，换成它。 |
| 买菜券 | 小机手里有几张、最多几张；最近一条和券有关的记录。 | 「发一张」：给他一张券（满了置灰）。「给他买菜」：打开买菜的单子。 |
| 冰箱门上的布袋 /「给他买菜」 | 按类别排的目录。 | 圈几样（再点取消）然后买：不扣券，直接放进冰箱。「添种类」：自己添一样食材（名字、哪一类、拿出来就能吃吗、一份几个、能放几天），也能撤掉自己添的。自己添的种类在服务端画出小图之前，先显示名字的头一个字（要接了画图函数才会画，见 [HOOKS.md](HOOKS.md)）。 |
| 调料架 | 服务端列出的常备品。 | 没有：常备品用不完。 |
| 一款零食 | 今天吃了几份 / 每日上限、几点重置、档位、一份回多少体力。 | 「喂一份」（咖啡要先选口味）。点 `−` / `+` 再点「存」：改这一款的每日上限。角色不止一个时：选喂给谁。 |
| 一道菜 | 菜名、出锅结果（很好 / 糊了 / 坏了）、备注。下面是菜单上的全部，以及今天吃了几顿。 | 「喂给他」：喂掉（划掉、算一顿、会告诉他）。「只划掉」：划掉但不算一顿。「改」：改菜名和备注。「撤」：从菜单上拿掉。 |
| 一瓶药剂 | 回多少体力、备注。 | 同样四个动作；喂下去当场加体力，不算一顿饭。 |
| 虚线的那条短册 /「挂一道」 | 一张单子，分两段。 | 挂一道菜（菜名、备注）。挂一瓶药剂（回多少、备注）。 |
| 小票 | 今天吃的每一顿，各是在哪个时段吃的。 | |
| 软木板 | 厨房最近的事（买了什么、扔了什么、什么坏了、券、虫子……），一页六条。 | 「更早的」/「新一些」：翻页。 |
| 手边下面那一排（这次升级） | 开着的玩法各一个词：食谱 · 图鉴 · 成就 · 小贩 · 零花钱 · 盘子 · 罐子。全关着时这一排不存在。 | 点一个：从上落下一张纸，每个入口一个标签页（见下面）。 |
| 小贩在楼下时顶上那一行 | 「楼下有卖糖葫芦的 · 还待 20 分钟 →」 | 点它：直接打开小贩那一页。 |

**画上摆得下多少。** 冰箱里最多画十二样食材：每层三样、抽屉里三样，另外门架上放牛奶；同一样食材有好几批也只画一份。台面上摆前三道菜，搁板下面最多挂四条短册。你自己添的种类在有自己的小图之前，画上没有它。摆不下的并没有丢：手边最底下那一排永远列着冰箱里的全部和菜单上的全部，每一样都能在那里点。

**哪些会先问一句，哪些点了就做。** 对一道菜或一瓶药剂的三件事，会先在一张小纸条上问一句：「喂给他」「只划掉」「撤」。其余的都是点了就做：发券、买菜、喂零食、存零食的上限、添种类和撤掉自己添的种类、重画小图、挂一道菜或一瓶药剂、存改动。

**这次升级那张纸。** 食谱：今天可以试试（他读到的那段原样）、翻公共食谱、「想吃这个」点菜（点菜开着时）、点过的菜与撤回、他的食谱本（带札记）、一页的码、收别人的码（先给你看一遍再「收下」）。图鉴：做过的每道一行（做过 / 做好 / 吃过、最好的一次、用料、他的那句话），每道可以写你的评语；收藏了还没做的另列一行。成就：全部成就，拿没拿到都列（他只读得到拿到的）。小贩：楼下这一趟的货、价钱、还剩几份，「替他买」（不花他的钱），他今天在小贩那儿花了多少、零花钱还剩多少、给他零花钱，窗台的花，他想要的新花同意或不同意。零花钱：他现在有多少；用自带小账本时在这里给，给多少、什么时候给都由你，给了他下一轮会知道（接了你们自家的钱包，就在那边给）。盘子：各种状态各几只、「让他自己刷」开或关、一次刷几只。小贩、盘子这两页顶上各有一小格小厨师在做家务：在窗边跟小贩买东西、一步一步刷盘子（某只到点、结果是碎了，就放一遍摔碎）、往洗碗机里放盘子；设备开了「减少动态效果」时只显示一张静帧（见 [ANIMATION.md](ANIMATION.md#厨房页上的家务)）。罐子：三只罐子、开出来的成品、喂他一份、每天的上限。这台设备上还没点开过的入口旁边带一个小小的红色「新」，点开一次就消失（记在浏览器的 localStorage 里）。这些都不往画上叠东西；画上和玩法有关的，只是东西本身（花、罐子、盘子），按同一档光画。

**画上的玩法。** 花：一次一束，按品种（有图的六种：玫瑰、向日葵、郁金香、桔梗、洋甘菊、水仙）和样子（刚买的 / 有点蔫的 / 谢了的）；没有图的品种（你同意了的新品种）在画上窗台空着（那里也点不到），在小贩那一页照样列着。罐子：空着、泡着水果（封的是糖或蜂蜜）、泡着腌菜（封的是盐）。水槽：没有、几只（1 到 3）、堆高（4 只以上），他在刷的时候冒泡沫。沥水架：最近那一回刷的盘子，刷出来就摆上去，刷完再晾三个小时。关着的玩法在画上什么也不加（窗台空着；水槽、沥水架是房间的一部分，空着）。

服务端把**体力**关掉的时候，页面上不出现任何和体力有关的东西：零食不显示回多少，「挂一道」的单子上没有药剂那一段。把**饱食度**关掉的时候，顶上不显示饱食度。对应 [CONFIG.md](CONFIG.md) 里的 `[stamina] enabled` 和 `[satiety] enabled`。

服务开着快进钟的时候（`[server] dev_clock = true`，只给演示用），页面左上角会出现一个很小的「过一小时 / 过一天」。它拨的是整台服务的钟。没开快进钟的服务上，这个东西不存在。

画上只有默认零食架的五款和默认的四样常备的位置。你在设置里改了零食或常备品之后，手边照样全都列出来；画上只画包里有图的那些。

## 页面什么时候重新读

页面开着的时候，小机会用工具改动他的厨房，所以页面不是只读一次：

- 打开时，以及切到另一个角色时；
- 你发了券、买了菜、喂了一道菜之后（冰箱、饱食度、今天吃了几顿会重读一次；其余的操作直接显示在页面上）；
- 页面看得见的时候，每 30 秒一次；
- 回到前台的那一刻（切回这个标签页、手机解锁）。

页面在后台时什么都不读。你正做到一半的时候（单子或问句开着，或者有请求还在路上），那一次 30 秒的重读会跳过，不会动你正在填的东西；下一次在 30 秒之后。所以小机做了什么，不用刷新，大约半分钟之内就会出现在这里。

## 口令

`/page/` 下面的文件谁都能取；它背后的数据不是。设了 `[server] token` 之后，页面要有口令才读得到东西。

- **单独打开**时，页面问一次口令（那一步上写着要的是哪个：服务设置里 `[server]` 那一段的 `token`），存在这个浏览器的本地存储里。页面最底下的「换口令 →」会把它忘掉。
- **嵌在别的页面或 App 里**时，由宿主用一条消息把口令递过来（见下），页面什么都不存。口令到手之前，框里会写着它在等什么：「在等嵌入它的页面给口令…」；宿主给的口令被服务拒绝之后是「口令不对 · 在等嵌入它的页面重新给」；连不上服务时是「厨房没连上 · 在等嵌入它的页面重试」。

不管哪种，口令都只放在 `Authorization: Bearer` 请求头里发出去，从来不进地址，所以不会落进服务的日志、浏览器的历史记录或来源地址里。你自己也不要把它写进链接。出了自己这台电脑，请走 HTTPS（在服务前面放一个反向代理或隧道），否则口令是明文在网络上走的。

## 嵌进别的页面

### 用 `<iframe>`

1. 在厨房服务的设置里，写上要嵌它的那个页面的来源：

   ```toml
   [server]
   embed_origins = ["https://chat.example.com"]
   ```

   不写的话，浏览器不让别的网站把厨房页放进框里（服务发出的是 `Content-Security-Policy: frame-ancestors 'self'`，再加上你列的那些）。来源就是 `协议://主机[:端口]`，后面什么都不带。

2. 框的地址带上 `?host=<你那个页面的来源>`：

   ```html
   <iframe id="kitchen" src="https://kitchen.example.com/page/?host=https%3A%2F%2Fchat.example.com"
           style="width: 390px; height: 780px; border: 0"></iframe>
   ```

   厨房页只跟这一个来源说话。浏览器能认出真正的父页面是谁的时候（Chrome、Safari），`?host=` 和它对不上就不算数。不带 `?host=` 的话，框里的页面谁也不理，当成单独打开（自己问口令）。

3. 页面说 `ready` 之后，回它一条 `init`：

   ```js
   const KITCHEN = "https://kitchen.example.com";
   const frame = document.getElementById("kitchen");
   window.addEventListener("message", (e) => {
     if (e.origin !== KITCHEN || e.source !== frame.contentWindow) return;   // 只收厨房发来的
     if (e.data.type === "ready") {
       frame.contentWindow.postMessage(
         { v: 1, id: "1", type: "init", payload: { credential: "<口令>", who: "mika" } },
         KITCHEN,                                                             // 不要写 "*"
       );
     }
     if (e.data.type === "close") { /* 对方点了「← 返回」：把框收起来 */ }
   });
   ```

完整的宿主页面例子在 [`examples/page_embed.html`](../examples/page_embed.html)。

### 消息

每条消息都是 `{ "v": 1, "id": "<随便一个字符串>", "type": "<类型>", "payload": { … } }`。

| 方向 | `type` | `payload` | 说明 |
|---|---|---|---|
| 页面 → 宿主 | `ready` | `{v: 1}` | 页面可以接 `init` 了。每次重新加载都会再发一次，每次都要回。 |
| 页面 → 宿主 | `close` | | 对方点了「← 返回」（这个链接只在嵌入时才有）。 |
| 宿主 → 页面 | `init` | `{apiBase?, credential?, who?}` | `credential` = 口令（服务没设口令就不写）。`who` = 打开哪个角色，得是服务列出来的。`apiBase` = 厨房服务的来源；页面就是由那个服务提供的话不用写。 |
| 宿主 → 页面 | `role` | `{who}` | 换成这个角色的厨房。服务没列出的角色会被拒绝。 |
| 宿主 → 页面 | `logout` | | 忘掉口令，等下一条 `init`。 |

宿主发来的每条消息，页面都会回一条 `{ "v": 1, "id": "<同一个 id>", "ok": true, "result": {…} }` 或 `{ …, "ok": false, "error": "<原因>" }`。`init` 要等服务认了口令才回；失败时的原因是 `the kitchen server refused the credential`（口令不对）或 `the kitchen server cannot be reached`（连不上），可以再发一次。

服务没列出的角色，回的是 `ok: false`，原因是 `unknown role "<名字>": the kitchen server lists "a", "b"`。`role` 被拒时，厨房停在原来那个角色上。`init` 里的角色不认识时，口令照样算数、厨房照样打开，只是开的是默认角色（原因的结尾多一句 `; showing "<默认角色>"`）。两种情况下，页面标题下面也会写一行说明。

### 放进 App 的内嵌网页窗口

页面加载时如果发现下面任何一个（或者地址带 `?embed=native`），就改用原生桥，不用 `postMessage`：

| 平台 | 页面 → App | App → 页面 |
|---|---|---|
| iOS `WKWebView` | `window.webkit.messageHandlers.kitchenette.postMessage(json)` | `evaluateJavaScript("window.kitchenette && window.kitchenette.receive(" + json + ")")` |
| react-native-webview | `window.ReactNativeWebView.postMessage(json)` | `injectJavaScript("window.kitchenette && window.kitchenette.receive(" + json + ")")` |
| Android `WebView` | `window.KitchenetteHost.postMessage(json)`（来自 `addJavascriptInterface(obj, "KitchenetteHost")`） | `evaluateJavascript("window.kitchenette && window.kitchenette.receive(" + json + ")", null)` |

消息是同一套；页面发出来的是 JSON 字符串。桥要在页面加载之前注册好，`init` 要等收到 `ready` 之后再发，网页窗口不要离开厨房的来源（别让桥暴露给别的网站）。内嵌网页窗口不是框，`embed_origins` 管不到它。

### 把页面文件放在别处

构建好的页面也可以不由厨房服务提供，而是放在别的地方（静态托管、你自己 App 的包里）。这时有三件事要改：

- 按它将来所在的路径构建：`KITCHENETTE_PAGE_BASE=/my/path npm run build`（见「重新构建」），然后拷走 `web/page/dist/`。
- 告诉页面厨房在哪：单独打开时在地址上加 `?api=https://kitchen.example.com`；嵌入时在 `init` 里写 `apiBase`。
- 在厨房服务上允许那个网站从浏览器里读 `/api`：`[server] cors_origins = ["https://where-the-page-is.example.com"]`。

## 重新构建

源码在 `web/page/`（React Native 组件，经 Expo 的网页导出在浏览器里跑）。只有要改页面时才需要这一节。

```bash
cd web/page
npm install
npm run build        # 导出到 web/page/dist/，并拷到 src/kitchenette/page/
```

`src/kitchenette/page/` 就是 Python 包带着的、`/page/` 提供的那一份；改了源码要把它一起提交。

```bash
npm test             # 页面的单元测试
npm run typecheck
npm start            # 带热更新的开发服务；地址上加 ?api=http://127.0.0.1:8765，并把它的来源写进 cors_origins
```

另有两个脚本，用无头浏览器对着它们自己起的真服务（各用一个临时库）把构建好的页面点一遍。它们需要 [Playwright](https://playwright.dev)，那不是这个包的依赖：

```bash
# 在 web/page/ 下运行；KITCHENETTE_PYTHON 指向装了本仓库的那个 Python
PW_DIR=/path/to/node_modules KITCHENETTE_PYTHON=python3 node e2e/walk.cjs     # 能点的东西全点一遍
PW_DIR=/path/to/node_modules KITCHENETTE_PYTHON=python3 node e2e/modes.cjs    # 口令、关掉开关、嵌入
```

`web/page/scripts/` 里的其他脚本：`gen-art.mjs`（图片登记表，添了或换了图之后跑）、`gen-scene.mjs`（三档光的厨房和贴回去的小块，从在线试玩 `docs/play/` 读；试玩页重新生成之后跑）、`gen-chores.mjs`（小厨师的家务动画，直接用 `assets/clawd/` 里的；素材变了之后跑）、`subset_fonts.py`（切字体文件）、`contract_fixture.py`（单元测试读的那份服务端回包）。

## 图、字体、第三方代码

- **图**（`web/page/assets/kitchen/` 120 个文件，另有页面直接从 `docs/play/img/` 引用的 105 个）：作者自己的素材，用 ChatGPT 的出图功能（作者自己的订阅）画的，再用脚本抠图；红笔圈是代码画的。没有任何第三方的图。
- **字体**：思源宋体（Noto Serif SC，400 和 300 两个字重）和 Bodoni Moda（三个光学尺寸），都是 SIL Open Font License 1.1；切小之后以 WOFF2 随包带，许可全文一起带。设备上装了思源宋体（Noto Serif SC / Source Han Serif SC）就先用设备上的，什么都不下载。
- **脚本包里的代码**：React、React DOM、React Native for Web、Expo 和几个小包，除一个是 BSD-3-Clause 外都是 MIT。清单和每一份许可全文在构建时生成。

完整的说明跟着页面一起走：[`/page/ASSETS.md`](../web/page/public/ASSETS.md) 和 `/page/THIRD-PARTY.txt`（在仓库里是 `src/kitchenette/page/THIRD-PARTY.txt`）。
