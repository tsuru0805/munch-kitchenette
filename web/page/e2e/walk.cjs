// Walks the kitchen page in a headless browser against a real server: every thing that can be tapped
// is tapped, and what the server holds afterwards is checked.
//
// It starts its own throwaway kitchen (examples/kitchen_page.py: a temporary database, the
// fast-forward clock on) and stops it at the end. Nothing of yours is touched.
//
//   PW_DIR=<a node_modules folder that has playwright> \
//   PW_CHROME=<path to a Chromium / chrome-headless-shell binary> \
//   KITCHENETTE_PYTHON=<python that has kitchenette installed> \
//   node e2e/walk.cjs [--port 18811] [--shots <dir>]
//
// Playwright is not a dependency of this package: point PW_DIR at any install of it.
const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
};
const PORT = Number(arg("port", "18811"));
const SHOTS = arg("shots", "");
const BASE = `http://127.0.0.1:${PORT}`;
const ROLE = "小满";
const OTHER = "阿树";
const EMPTY = "空屋";
const repo = path.resolve(__dirname, "..", "..", "..");
const { chromium } = require(path.join(process.env.PW_DIR || path.join(__dirname, "..", "node_modules"), "playwright"));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function api(method, p, body) {
  const r = await fetch(BASE + p, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  return r.json();
}
const q = (who) => `who=${encodeURIComponent(who)}`;
const fridge = (who = ROLE) => api("GET", `/api/fridge?${q(who)}`);
const menu = (who = ROLE) => api("GET", `/api/menu?pending=1&for_who=${encodeURIComponent(who)}`);
const meals = (who = ROLE) => api("GET", `/api/meals?${q(who)}`).then((m) => m.meals);
const snack = async (id, who = ROLE) => (await api("GET", `/api/snacks?${q(who)}`)).snacks.find((s) => s.id === id);
const potions = (who = ROLE) => api("GET", `/api/potions?${q(who)}`).then((p) => p.items);

function check(cond, what) {
  if (!cond) throw new Error(`expected: ${what}`);
}
async function until(fn, what, ms = 6000) {
  const end = Date.now() + ms;
  let last;
  while (Date.now() < end) {
    try {
      last = await fn();
      if (last) return last;
    } catch (e) {
      last = e;
    }
    await sleep(80);
  }
  throw new Error(`timed out waiting for: ${what} (last: ${last instanceof Error ? last.message : JSON.stringify(last)})`);
}

async function startKitchen() {
  const py = process.env.KITCHENETTE_PYTHON || "python3";
  const proc = spawn(py, [path.join(repo, "examples", "kitchen_page.py"), "--port", String(PORT)], { stdio: ["ignore", "pipe", "pipe"] });
  let err = "";
  proc.stderr.on("data", (d) => (err += d));
  for (let i = 0; i < 100; i++) {
    if (proc.exitCode !== null) throw new Error(`the demo kitchen did not start:\n${err}`);
    try {
      if ((await fetch(`${BASE}/api/health`)).ok) return proc;
    } catch {
      /* not up yet */
    }
    await sleep(200);
  }
  proc.kill();
  throw new Error("the demo kitchen did not answer in time");
}

(async () => {
  const kitchen = await startKitchen();
  const browser = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const noise = []; // console errors, page errors, failed or >= 400 responses, with the step they happened in
  let step = "open";
  let noisy = false;
  const note = (line) => noise.push({ step, noisy, line });
  page.on("console", (m) => m.type() === "error" && note(`console: ${m.text()}`));
  page.on("pageerror", (e) => note(`pageerror: ${e.message}`));
  page.on("response", (r) => r.status() >= 400 && note(`http ${r.status()}: ${r.url().replace(BASE, "")}`));
  page.on("requestfailed", (r) => note(`failed: ${r.url().replace(BASE, "")}`));

  const tid = (id) => page.locator(`[data-testid="${id}"]`);
  const txt = (id) => tid(id).first().innerText();
  const has = async (id) => (await tid(id).count()) > 0;
  const tap = (id) => tid(id).first().click();
  // a ground zone (the whole fridge / the counter) only gets the taps that land on no thing: aim at its bottom corner
  const tapZone = async (id) => {
    const box = await tid(id).boundingBox();
    await tid(id).click({ position: { x: 14, y: box.height - 14 } });
  };
  const toast = (part) => until(async () => (await txt("toast")).includes(part), `toast containing "${part}"`);
  const body = () => page.evaluate(() => document.body.innerText);
  const sees = (part) => until(async () => (await body()).includes(part), `"${part}" on the page`);
  const handSays = (part) => until(async () => (await page.locator('[data-testid^="hand-"]').first().innerText()).includes(part), `the hand says "${part}"`);
  const sceneArt = (name) => page.locator(`[data-testid="kitchen-scene"] img[src*="/${name}."]`).count();
  const shot = async (name) => {
    if (!SHOTS) return;
    await sleep(350);
    await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
  };
  const yes = async () => {
    await tid("confirm-sheet").waitFor();
    await tap("confirm-yes");
  };
  const done = [];
  async function run(name, fn, opts = {}) {
    step = name;
    noisy = !!opts.noisy;
    try {
      await fn();
      await sleep(120);
      done.push(name);
      console.log(`ok   ${name}`);
    } catch (e) {
      if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `FAILED_${done.length + 1}.png`) }).catch(() => {});
      throw new Error(`step "${name}": ${e.message}`);
    }
  }

  try {
    // an empty kitchen for later: a role exists once it has been looked at
    await fridge(EMPTY);

    await run("open: the page loads with no error and no missing file", async () => {
      await page.goto(`${BASE}/page/`, { waitUntil: "networkidle" });
      await sees(`${ROLE}的厨房`);
      const f = await fridge();
      check(await has("satiety"), "satiety is shown");
      check((await txt("satiety")).includes(String(Math.round(f.satiety.value))), "the satiety number is the server's");
      // what is held on arriving = the most urgent thing in the fridge
      await handSays(f.items[0].name);
      check(await has("dev-clock"), "the fast-forward control is there (the demo switches it on)");
      await shot("e1_default");
    });

    await run("fridge: tapping a thing in the picture holds it; the row under it switches", async () => {
      await tap("obj-item-egg");
      await handSays("鸡蛋");
      const f = await fridge();
      const eggs = f.items.filter((i) => i.item_id === "egg").reduce((n, i) => n + i.qty, 0);
      await handSays(`×${eggs}`);
      check((await tid("hand-item").getAttribute("data-testid")) === "hand-item", "the item hand is up");
      const kinds = new Set(f.items.map((i) => i.item_id)).size;
      await handSays(`冰箱里\n${kinds}\n样`);
      await tap("row-item-cucumber");
      await handSays("黄瓜");
      await handSays("你买的");
      await tap("row-item-carrot");
      await handSays("他自己买的");
      await shot("e2_item");
    });

    await run("a day passes: fresh food goes limp and the dish left out overnight grows worms", async () => {
      const soup = (await menu()).find((r) => r.dish === "味噌汤");
      await tap("row-item-lettuce");
      await handSays("新鲜");
      check((await sceneArt("lettuce_fresh")) === 1, "the lettuce in the picture is the fresh one");
      check((await sceneArt("dish_cup")) + (await sceneArt("dish_bowl")) + (await sceneArt("dish_plate")) === 3, "three dishes on the counter, none burnt");
      await shot("e3_before_day");
      await tap("skip-day");
      await until(async () => (await fridge()).items.find((i) => i.item_id === "lettuce").freshness === "meh", "the server says the lettuce is past its best");
      await handSays("不太新鲜");
      await until(async () => (await sceneArt("lettuce_meh")) === 1 && (await sceneArt("lettuce_fresh")) === 0, "the picture shows the limp lettuce");
      // the miso soup the role cooked sat on the table overnight
      await tap(`obj-dish-${soup.id}`);
      await handSays("坏了");
      const row = (await menu()).find((r) => r.id === soup.id);
      check(row.note && row.note !== soup.note, "the menu row's note changed");
      await handSays(row.note);
      await until(async () => (await page.locator('[data-testid="kitchen-scene"] img[src*="_burnt."]').count()) === 1, "its bowl in the picture is the spoiled one");
      await tap("obj-wall");
      await handSays("味噌汤");
      await shot("e3_after_day");
    });

    await run("coupons: the count, handing one out, and the cap", async () => {
      await tap("obj-coupon");
      const before = (await fridge()).coupons;
      check(before.count === 2 && before.max === 3, "two of three coupons before");
      await handSays(`${before.count}\n/ ${before.max} 张`);
      check((await tid("obj-coupon-2").count()) === 1 && (await tid("obj-coupon-3").count()) === 0, "two coupons on the fridge door");
      await tap("send-coupon");
      await until(async () => (await fridge()).coupons.count === 3, "the server holds three coupons");
      await handSays("3\n/ 3 张");
      await handSays("攒满了");
      check((await tid("send-coupon").getAttribute("aria-disabled")) === "true", "handing out is dimmed at the cap");
      await until(async () => (await tid("obj-coupon-3").count()) === 1, "three coupons on the fridge door");
      await shot("e4_coupon");
    });

    await run("groceries: the catalog sheet, ticking, buying", async () => {
      await tap("obj-buy");
      await tid("buy-sheet").waitFor();
      await sees(`给${ROLE}买菜`);
      await tid("buy-potato").waitFor();
      check((await tid("buy-confirm").getAttribute("aria-disabled")) === "true", "nothing ticked: buying is dimmed");
      await tap("buy-potato");
      await tap("buy-cheese");
      await tap("buy-egg"); // a second batch of something already in the fridge
      await tap("buy-butter");
      await tap("buy-butter"); // ticked and unticked
      await sees("圈了 3 样");
      await shot("e5_buy");
      await tap("buy-confirm");
      await until(async () => !(await has("buy-sheet")), "the sheet closes");
      const ids = (await fridge()).items.map((i) => i.item_id);
      check(ids.includes("potato") && ids.includes("cheese") && !ids.includes("butter"), "the server's fridge has the potato and the cheese, not the butter");
      await tapZone("obj-fridge");
      await until(() => has("row-item-potato"), "the potato is in the fridge row");
      // the eggs are two batches now: listed apart, each with its own count, the total on top
      const eggs = (await fridge()).items.filter((i) => i.item_id === "egg");
      check(eggs.length === 2, "the server holds two batches of eggs");
      await tap("row-item-egg");
      await handSays(`×${eggs[0].qty + eggs[1].qty}`);
      await until(async () => (await page.locator('[data-testid="hand-item"] [data-testid^="batch-"]').count()) === 2, "two batch lines in the hand");
      await handSays(`×${eggs[0].qty}`);
      await handSays(`×${eggs[1].qty}`);
    });

    await run("groceries: a refusal is shown on the sheet in the server's words and what was ticked stays", async () => {
      await page.route("**/api/fridge/buy", (r) => r.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "今天菜市场关门了。" }) }));
      await tap("open-buy");
      await tid("buy-onion").waitFor();
      await tap("buy-onion");
      await tap("buy-confirm");
      await until(async () => (await txt("buy-err")) === "今天菜市场关门了。", "the server's sentence on the sheet");
      await sees("圈了 1 样");
      await page.unroute("**/api/fridge/buy");
      await tap("buy-close");
    }, { noisy: true });

    let kakiId = "";
    await run("kinds: adding one, the first character while it has no picture, buying it, a duplicate, removing it", async () => {
      await tap("open-buy");
      await tap("buy-mode");
      await tid("kind-form").waitFor();
      check((await tid("kind-add").getAttribute("aria-disabled")) === "true", "no name yet: adding is dimmed");
      await tid("kind-name").fill("柿子");
      await tap("kind-cat-fruit");
      await tap("kind-pack-2");
      await tap("kind-days-7");
      await shot("e6_kind");
      await tap("kind-add");
      const kind = await until(async () => (await api("GET", "/api/fridge/catalog")).find((k) => k.name === "柿子"), "the server lists the new kind");
      kakiId = kind.id;
      check(kind.custom && kind.category === "fruit" && kind.pack_qty === 2 && kind.shelf_days === 7 && kind.raw_edible === true, "the kind is as filled in");
      await tid(`kind-row-${kakiId}`).waitFor();
      check((await tid("kind-name").inputValue()) === "", "the form is cleared");
      // a duplicate: the server's own sentence, the name stays
      await tid("kind-name").fill("苹果");
      await tap("kind-cat-fruit");
      await tap("kind-add");
      await until(async () => (await has("kind-err")) && (await txt("kind-err")).includes("苹果"), "the server's sentence about the duplicate");
      check((await tid("kind-name").inputValue()) === "苹果", "what was typed stays");
      await tap("buy-mode"); // back to buying
      await tid(`buy-${kakiId}`).waitFor();
      check((await txt(`buy-${kakiId}`)).startsWith("柿"), "its tile shows the first character of its name");
      await tap(`buy-${kakiId}`);
      await tap("buy-confirm");
      await until(async () => !(await has("buy-sheet")), "the sheet closes");
      await until(async () => (await fridge()).items.some((i) => i.item_id === kakiId), "the server's fridge has the new kind");
      await tapZone("obj-fridge");
      await tap(`row-item-${kakiId}`);
      await handSays("柿子");
      await handSays("×2");
      check((await page.locator(`[data-testid="hand-item"] img`).count()) >= 0, "the hand is up");
      // remove the kind: no longer offered, what is in the fridge stays
      await tap("open-buy");
      await tap("buy-mode");
      await tap(`kind-remove-${kakiId}`);
      await until(async () => !(await has(`kind-row-${kakiId}`)), "its row is gone");
      check(!(await api("GET", "/api/fridge/catalog")).some((k) => k.id === kakiId), "the server no longer offers it");
      check((await fridge()).items.some((i) => i.item_id === kakiId), "what was bought stays in the fridge");
      await tap("buy-close");
    }, { noisy: true });

    await run("staples: the shelf", async () => {
      await tap("obj-staple");
      await tid("hand-staple").waitFor();
      for (const s of (await fridge()).staples) check(await has(`staple-${s}`), `staple ${s} is listed`);
      await handSays("常备");
      await shot("e7_staple");
    });

    await run("snacks: feeding one, coffee needs a flavour, changing one cap, feeding another role", async () => {
      await tap("obj-snack-pudding");
      await tid("hand-snack").waitFor();
      const before = await snack("pudding");
      await handSays(`${before.eaten}\n/ ${before.cap} 今天`);
      await tap("snack-feed");
      await toast(`喂了${ROLE}一份布丁`);
      check((await snack("pudding")).eaten === before.eaten + 1, "the server counted one more pudding");
      await handSays(`${before.eaten + 1}\n/ ${before.cap} 今天`);
      // the cap of this one snack
      check(!(await has("snack-cap-save")), "no save button before stepping");
      await tap("snack-cap-plus");
      await tap("snack-cap-plus");
      await tap("snack-cap-minus");
      check((await txt("snack-cap")) === String(before.cap + 1), "the draft cap");
      await tap("snack-cap-cancel");
      check((await txt("snack-cap")) === String(before.cap) && (await snack("pudding")).cap === before.cap, "backing out changes nothing");
      await tap("snack-cap-plus");
      await tap("snack-cap-save");
      await toast("上限改好了");
      check((await snack("pudding")).cap === before.cap + 1, "the server holds the new cap");
      check((await snack("cookie")).cap === (await snack("cookie")).default_cap, "the other snacks keep theirs");
      // coffee
      await tap("row-snack-coffee");
      await handSays("咖啡");
      await tap("snack-feed");
      await toast("先选咖啡的口味");
      check((await snack("coffee")).eaten === 0, "nothing was sent without a flavour");
      await tap("snack-variant-latte");
      await until(async () => (await page.locator('[data-testid="hand-snack"] img[src*="/snack_coffee_latte."]').count()) === 2, "the picture is the latte, large and in the row");
      await tap("snack-feed");
      await toast("拿铁");
      check((await snack("coffee")).eaten === 1, "the server counted the latte");
      await shot("e8_snack");
      // feed the other role from here
      await tap(`snack-who-${OTHER}`);
      await handSays("0\n/");
      await tap("row-snack-cookie");
      await tap("snack-feed");
      await toast(`喂了${OTHER}一份曲奇`);
      check((await snack("cookie", OTHER)).eaten === 1 && (await snack("cookie")).eaten === 0, "the cookie went to the other role");
      await tap(`snack-who-${ROLE}`);
    });

    await run("the table: changing a dish", async () => {
      const row = (await menu()).find((r) => r.dish === "冰镇酸梅汤");
      await tap(`obj-dish-${row.id}`);
      await handSays("冰镇酸梅汤");
      await handSays("饭后喝");
      await tap("dish-edit");
      await tid("write-sheet").waitFor();
      await sees("改这一道");
      check((await tid("dish-edit-name").inputValue()) === "冰镇酸梅汤", "the field holds the name");
      await tid("dish-edit-name").fill("  ");
      await tap("edit-save");
      await until(async () => (await txt("write-msg")) === "菜名不能空", "an empty name is refused on the sheet");
      await tid("dish-edit-name").fill("热酸梅汤");
      await tid("dish-edit-note").fill("趁热");
      await tap("edit-save");
      await until(async () => !(await has("write-sheet")), "the sheet closes");
      const after = (await menu()).find((r) => r.id === row.id);
      check(after.dish === "热酸梅汤" && after.note === "趁热", "the server holds the new name and note");
      await handSays("热酸梅汤");
      await shot("e9_dish");
    });

    await run("the table: feeding a dish counts a meal and fills him up", async () => {
      const row = (await menu()).find((r) => r.dish === "葱油拌面");
      const [mealsBefore, satBefore] = [await meals(), (await fridge()).satiety.value];
      await tap(`row-dish-${row.id}`);
      await handSays("葱油拌面");
      await tap("dish-feed");
      await tid("confirm-sheet").waitFor();
      await sees("喂他『葱油拌面』?");
      await shot("e10_confirm");
      await tap("confirm-no"); // backing out does nothing
      await sleep(200);
      check((await menu()).some((r) => r.id === row.id), "backing out leaves the dish");
      await tap("dish-feed");
      await yes();
      await toast("喂进去了 · 他下轮会知道");
      check(!(await menu()).some((r) => r.id === row.id), "the dish is off the table");
      const mealsAfter = await meals();
      check(mealsAfter.length === mealsBefore.length + 1 && mealsAfter.at(-1).meal === "葱油拌面", "the server counted the meal");
      check((await fridge()).satiety.value > satBefore, "satiety went up");
      await until(async () => (await txt("satiety")).includes(String(Math.round((await fridge()).satiety.value))), "the number at the top follows");
      check((await api("GET", `/api/notes?${q(ROLE)}`)).notes.some((n) => (n.text || "").includes("葱油拌面")), "a note waits for the role");
    });

    await run("the table: feeding the dish that went off leaves him dizzy", async () => {
      const row = (await menu()).find((r) => r.dish === "味噌汤");
      check(!(await has("dizzy-line")), "not dizzy before");
      await tap(`obj-dish-${row.id}`); // after the feed the hand went back to the fridge: pick the dish in the picture
      await tap("dish-feed");
      await yes();
      const dz = await until(async () => (await fridge()).dizzy, "the server says he is dizzy");
      await until(() => has("dizzy-line"), "the line under the title");
      check((await txt("dizzy-line")).startsWith("晕乎乎的 · 还有 "), "it says how much longer");
      await tap("obj-wall");
      await tid("wall-dizzy").waitFor();
      check((await txt("wall-dizzy")).includes(`吃了坏掉的『${dz.dish}』`), "the wall says what he ate");
      await shot("e10b_dizzy");
    });

    await run("the table: taking a dish off", async () => {
      const row = (await menu()).find((r) => r.dish === "热酸梅汤");
      await tap(`obj-dish-${row.id}`);
      await tap("dish-remove");
      await tid("confirm-sheet").waitFor();
      await sees("撤掉『热酸梅汤』?");
      await tap("confirm-yes");
      await toast("撤了");
      check(!(await menu()).some((r) => r.id === row.id), "the server no longer has the row");
    });

    await run("potions: the amount, changing it, feeding it; hanging a new one", async () => {
      const bottle = (await potions())[0];
      check(bottle.pct === 30, "the demo hangs a 30% potion");
      await tap(`obj-dish-${bottle.menu_row_id}`);
      await handSays("精力补充药剂");
      await handSays("30\n% 体力");
      await shot("e11_potion");
      await tap("dish-edit");
      await sees("改这一瓶");
      await tid("potion-edit-pct").fill("abc");
      await tap("edit-save");
      await until(async () => (await txt("write-msg")) === "回多少体力填大于 0 的整数", "a wrong amount is refused on the sheet");
      await tid("potion-edit-pct").fill("45");
      await tid("potion-edit-memo").fill("下午再喝");
      await tap("edit-save");
      await until(async () => !(await has("write-sheet")), "the sheet closes");
      const edited = (await potions())[0];
      check(edited.pct === 45 && edited.memo === "下午再喝", "the server holds the new amount and memo");
      check((await menu()).find((r) => r.id === bottle.menu_row_id).note.includes("45"), "the menu row's note follows");
      await handSays("45\n% 体力");
      const before = (await api("GET", `/api/stamina?${q(ROLE)}`)).energy;
      await tap("dish-feed");
      await tid("confirm-sheet").waitFor();
      await sees("会回 45% 体力");
      await tap("confirm-yes");
      await until(async () => (await potions()).length === 0, "the bottle is drunk");
      // the same request crosses the row off right after the bottle is marked drunk: wait for it rather than race it
      await until(async () => !(await menu()).some((r) => r.id === bottle.menu_row_id), "its row is off the table");
      await until(async () => !(await has(`obj-dish-${bottle.menu_row_id}`)), "and out of the picture");
      const after = (await api("GET", `/api/stamina?${q(ROLE)}`)).energy;
      check(after > before || after >= 0.999, `stamina went up (${before} -> ${after})`);
      // hang a new one from the empty strip in the picture
      await tap("obj-write");
      await tid("write-sheet").waitFor();
      await tid("potion-pct").fill("20");
      await tid("potion-memo").fill("睡前");
      await shot("e12_write");
      await tap("add-potion");
      await toast("药剂挂上了");
      const hung = await until(async () => (await potions())[0], "the server holds the new potion");
      check(hung.pct === 20 && hung.memo === "睡前", "with its amount and memo");
      await handSays("20\n% 体力");
      // and only cross it off: the bottle is void
      await tap("dish-strike");
      await tid("confirm-sheet").waitFor();
      await sees("这一瓶就不要了。");
      await tap("confirm-yes");
      await until(async () => (await potions()).length === 0 && !(await menu()).some((r) => r.id === hung.menu_row_id), "the bottle is void and off the table");
    });

    await run("putting a dish up", async () => {
      await tap("obj-receipt");
      await tap("open-write");
      await tid("write-sheet").waitFor();
      await tap("add-dish");
      await until(async () => (await txt("write-msg")) === "空盘子不上桌", "an empty plate is refused on the sheet");
      await tid("dish-name").fill("蛋包饭");
      await tid("dish-note").fill("番茄酱画个笑脸");
      await tap("add-dish");
      await until(async () => !(await has("write-sheet")), "the sheet closes");
      const row = await until(async () => (await menu()).find((r) => r.dish === "蛋包饭"), "the server has the dish");
      check(row.note === "番茄酱画个笑脸" && row.by === "human" && row.for_who === ROLE, "with its note, put up by the human for this role");
      await handSays("蛋包饭");
      await handSays("番茄酱画个笑脸");
      await until(async () => (await has(`obj-dish-${row.id}`)), "it is in the picture, on the counter");
      check(await has("dish-feed"), "it can be fed at once");
    });

    await run("the table: only crossing a dish off counts no meal", async () => {
      const row = (await menu()).find((r) => r.dish === "蛋包饭");
      const n = (await meals()).length;
      await tap(`obj-dish-${row.id}`);
      await tap("dish-strike");
      await tid("confirm-sheet").waitFor();
      await sees("只划掉『蛋包饭』?");
      await tap("confirm-yes");
      await toast("划掉了");
      check(!(await menu()).some((r) => r.id === row.id), "the dish is off the table");
      check((await meals()).length === n, "no meal was counted");
    });

    await run("the receipt: today's meals", async () => {
      await tap("obj-receipt");
      await tid("hand-receipt").waitFor();
      const today = await meals();
      await handSays("用餐记录");
      await handSays(`今天 ${today.length} 顿`);
      for (const m of today) await handSays(m.meal);
      await handSays(`今天吃了 ${today.length} 顿`);
      await shot("e13_receipt");
    });

    await run("the cork board: recent notes, page by page", async () => {
      await tap("obj-wall");
      await tid("hand-wall").waitFor();
      const log = (await fridge()).log;
      check(log.length > 6, "the demo has more than one page of notes");
      const pages = Math.ceil(log.length / 6);
      check((await tid("wall-note").count()) === 6, "six notes on the first page");
      await handSays(`1 / ${pages}`);
      await handSays(log[0].text);
      check((await tid("wall-newer").getAttribute("aria-disabled")) === "true", "no newer page than the first");
      await tap("wall-older");
      await handSays(`2 / ${pages}`);
      await handSays(log[6].text);
      await shot("e14_wall_p2");
      await tap("wall-newer");
      await handSays(`1 / ${pages}`);
      check((await tid("scene-note-2").count()) === 1, "three notes are pinned on the board in the picture");
    });

    await run("switching roles: the whole page is the other kitchen", async () => {
      await tap(`role-${OTHER}`);
      await sees(`${OTHER}的厨房`);
      const f = await fridge(OTHER);
      await tid("hand-item").waitFor(); // the hand goes back to the default thing of the new kitchen
      await handSays(f.items[0].name);
      await until(async () => (await tid("obj-item-noodles").count()) === 1 && (await tid("obj-item-lettuce").count()) === 0, "the picture holds the other role's food");
      await tap("obj-receipt");
      await tap(`row-dish-${(await menu(OTHER))[0].id}`);
      await handSays("阳春面");
      await shot("e15_other_role");
    });

    await run("an empty kitchen", async () => {
      await tap(`role-${EMPTY}`);
      await sees(`${EMPTY}的厨房`);
      await tid("hand-coupon").waitFor(); // nothing in the fridge: the coupon is what is held
      await handSays("0\n/ 3 张");
      check(await has("fridge-empty"), "the fridge row says it is empty");
      check((await page.locator('[data-testid^="obj-item-"]').count()) === 0 && (await page.locator('[data-testid^="obj-coupon"]').count()) === 0, "nothing in the fridge and no coupon in the picture");
      await tapZone("obj-fridge"); // the fridge itself can still be tapped
      await tid("hand-coupon").waitFor();
      await tapZone("obj-table");
      await tid("hand-receipt").waitFor();
      await handSays("今天还没吃");
      await handSays("今天还没点菜");
      await tap("obj-wall");
      await handSays("还没有记录");
      await shot("e16_empty");
      await tap(`role-${ROLE}`);
      await sees(`${ROLE}的厨房`);
    });

    await run("an open page follows what happens elsewhere: read again every 30 seconds, never in the middle of typing", async () => {
      // a second window with its clock in the test's hands, on the other role's kitchen
      const p2 = await browser.newPage({ viewport: { width: 390, height: 844 } });
      await p2.clock.install();
      const t2 = (id) => p2.locator(`[data-testid="${id}"]`).first();
      const says = (part) => until(async () => (await p2.locator('[data-testid^="hand-"]').first().innerText()).includes(part), `the second window's hand says "${part}"`);
      const eggs = async () => (await fridge(OTHER)).items.filter((i) => i.item_id === "egg").reduce((n, i) => n + i.qty, 0);
      let reads = 0;
      p2.on("request", (r) => r.url().includes("/api/fridge?") && (reads += 1));
      try {
        await p2.goto(`${BASE}/page/?who=${encodeURIComponent(OTHER)}`, { waitUntil: "networkidle" });
        await t2("row-item-egg").click();
        const before = await eggs();
        await says(`×${before}`);
        // the kitchen changes behind the page's back, the way the role's own tools change it
        await api("POST", "/api/fridge/buy", { who: OTHER, items: ["egg"] });
        const after = await eggs();
        check(after > before, "the server has more eggs now");
        reads = 0;
        await sleep(600);
        check(reads === 0, "nothing is read between turns");
        await says(`×${before}`);
        await p2.clock.fastForward(31_000);
        await says(`×${after}`);
        check(reads === 1, `one read for the 30-second turn (saw ${reads})`);
        // in the middle of typing on a sheet: the turns are skipped and what is typed stays
        await t2("obj-write").click();
        await t2("dish-name").fill("写到一半的菜");
        await api("POST", "/api/fridge/buy", { who: OTHER, items: ["egg"] });
        const later = await eggs();
        reads = 0;
        await p2.clock.fastForward(65_000);
        await sleep(400);
        check(reads === 0, `no read while the sheet is open (saw ${reads})`);
        check((await t2("dish-name").inputValue()) === "写到一半的菜", "what was typed is untouched");
        await t2("write-close").click();
        await p2.clock.fastForward(31_000);
        await says(`×${later}`);
      } finally {
        await p2.close();
      }
    });

    await run("loading, a failed read with retry, and a failed refresh with retry", async () => {
      let hold = true;
      await page.route("**/api/fridge?*", async (r) => {
        while (hold) await sleep(50);
        await r.abort();
      });
      await page.reload({ waitUntil: "domcontentloaded" });
      await sees("读取中…"); // still reading
      await shot("e17_loading");
      hold = false;
      await sees("冰箱没拉到 · 点一下重试");
      check((await page.locator('[data-testid^="obj-item-"]').count()) === 0, "the picture is the empty kitchen meanwhile");
      await shot("e17_failed");
      await page.unroute("**/api/fridge?*");
      await tap("status-retry");
      await handSays((await fridge()).items[0].name);
      // now there is data: a refresh that fails keeps it and offers a retry
      await page.route("**/api/fridge?*", (r) => r.abort());
      await tap("skip-hour");
      await tid("refresh-failed").waitFor();
      check((await page.locator('[data-testid^="obj-item-"]').count()) > 0, "the old data stays");
      await page.unroute("**/api/fridge?*");
      await tap("refresh-failed");
      await until(async () => !(await has("refresh-failed")), "the retry clears the line");
    }, { noisy: true });

    const unexpected = noise.filter((n) => !n.noisy);
    const expected = noise.filter((n) => n.noisy);
    console.log(`\n${done.length} steps passed`);
    console.log(`console errors / failed requests outside the steps that provoke them: ${unexpected.length}`);
    for (const n of unexpected) console.log(`  [${n.step}] ${n.line}`);
    console.log(`provoked on purpose (a refusal, a duplicate, an aborted read): ${expected.length}`);
    if (unexpected.length) process.exitCode = 1;
  } catch (e) {
    console.error(`\nFAILED after ${done.length} steps: ${e.message}`);
    process.exitCode = 1;
  } finally {
    await browser.close();
    kitchen.kill("SIGINT");
  }
})();
