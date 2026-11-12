// The other ways the page is opened, in a headless browser against real servers it starts itself:
//   1. a server that wants a token and has stamina and satiety switched off: the token step, the
//      token never appearing in an address, and the parts that disappear;
//   2. the page inside another site's <iframe> (examples/page_embed.html): allowed and refused origins,
//      the token handed over by the host, "back" reaching the host.
//
//   PW_DIR=<a node_modules folder that has playwright> PW_CHROME=<a Chromium binary> \
//   KITCHENETTE_PYTHON=<python that has kitchenette installed> node e2e/modes.cjs [--port 18821]
//
// Uses three ports from --port up: the kitchen, a host page that may embed it, one that may not.
const { spawn } = require("node:child_process");
const http = require("node:http");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const at = process.argv.indexOf("--port");
const PORT = at > 0 ? Number(process.argv[at + 1]) : 18821;
const KITCHEN = `http://127.0.0.1:${PORT}`;
const HOST_OK = `http://127.0.0.1:${PORT + 1}`;
const HOST_NO = `http://127.0.0.1:${PORT + 2}`;
const TOKEN = "let-me-in-" + Math.random().toString(36).slice(2, 10);
const repo = path.resolve(__dirname, "..", "..", "..");
const { chromium } = require(path.join(process.env.PW_DIR || path.join(__dirname, "..", "node_modules"), "playwright"));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
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

async function startKitchen(tmp) {
  fs.writeFileSync(path.join(tmp, "kitchenette.toml"), [
    "[server]", `port = ${PORT}`, `token = "${TOKEN}"`, `db_path = "${path.join(tmp, "modes.db")}"`, `embed_origins = ["${HOST_OK}"]`,
    "[roles]", 'default = "小满"',
    "[stamina]", "enabled = false",
    "[satiety]", "enabled = false",
    "[art]", `dir = "${path.join(tmp, "art")}"`, "",
  ].join("\n"));
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith("KITCHENETTE_")));
  const log = [];
  const proc = spawn(process.env.KITCHENETTE_PYTHON || "python3", ["-m", "kitchenette", "serve"], { cwd: tmp, env, stdio: ["ignore", "pipe", "pipe"] });
  proc.stdout.on("data", (d) => log.push(String(d)));
  proc.stderr.on("data", (d) => log.push(String(d)));
  for (let i = 0; i < 100; i++) {
    if (proc.exitCode !== null) throw new Error(`the kitchen did not start:\n${log.join("")}`);
    try {
      if ((await fetch(`${KITCHEN}/api/health`)).ok) return { proc, log };
    } catch {
      /* not up yet */
    }
    await sleep(200);
  }
  proc.kill();
  throw new Error("the kitchen did not answer in time");
}

function hostServer(port) {
  const html = fs.readFileSync(path.join(repo, "examples", "page_embed.html"));
  const srv = http.createServer((req, res) => {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(html);
  });
  return new Promise((resolve) => srv.listen(port, "127.0.0.1", () => resolve(srv)));
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "kitchenette-modes-"));
  const kitchen = await startKitchen(tmp);
  const hosts = [await hostServer(PORT + 1), await hostServer(PORT + 2)];
  const browser = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  let passed = 0;
  const ok = (name) => {
    passed += 1;
    console.log(`ok   ${name}`);
  };
  try {
    const authed = (p, init = {}) => fetch(KITCHEN + p, { ...init, headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" } }).then((r) => r.json());
    await authed("/api/fridge/buy", { method: "POST", body: JSON.stringify({ who: "小满", items: ["egg", "tomato"] }) });
    await authed("/api/menu", { method: "POST", body: JSON.stringify({ dish: "蛋包饭", by: "human", for_who: "小满" }) });
    const addSecondRole = () => authed("/api/fridge/buy", { method: "POST", body: JSON.stringify({ who: "阿树", items: ["noodles"] }) });

    // ── 1. the token step, and what disappears ──────────────────────
    {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      const page = await ctx.newPage();
      const urls = [];
      page.on("request", (r) => urls.push(r.url()));
      const tid = (id) => page.locator(`[data-testid="${id}"]`);
      const body = () => page.evaluate(() => document.body.innerText);
      await page.goto(`${KITCHEN}/page/`, { waitUntil: "networkidle" });
      await tid("token-gate").waitFor();
      check(!(await body()).includes("的厨房"), "nothing of the kitchen is shown before the token");
      ok("a server with a token: the page asks for it");

      await tid("token-input").fill("not-the-token");
      await tid("token-enter").click();
      await until(async () => (await tid("token-err").count()) && (await tid("token-err").innerText()) === "口令不对", "the wrong token is refused in words");
      ok("a wrong token is refused");

      await tid("token-input").fill(TOKEN);
      await tid("token-enter").click();
      await until(async () => (await body()).includes("小满的厨房"), "the kitchen opens");
      ok("the right token opens the kitchen");

      check((await tid("satiety").count()) === 0, "satiety is not shown when it is switched off");
      await tid("obj-snack-pudding").click();
      await until(async () => (await tid("hand-snack").innerText()).includes("布丁"), "the snack hand");
      check(!(await tid("hand-snack").innerText()).includes("体力"), "nothing about stamina on a snack");
      check((await tid("snack-who-小满").count()) === 0, "a single role: no choice of whom to feed");
      check((await tid("roles").count()) === 0, "a single role: no role switch at the top");
      await tid("obj-write").click();
      await tid("write-sheet").waitFor();
      check((await tid("potion-add").count()) === 0, "no potion can be hung when stamina is switched off");
      check((await tid("add-dish").count()) === 1, "a dish still can");
      await tid("write-close").click();
      check((await tid("dev-clock").count()) === 0, "no fast-forward control on a server that did not switch it on");
      check((await tid("back").count()) === 0, "no back link when the page is opened on its own");
      ok("stamina and satiety switched off: their parts are gone; no fast-forward; no back link");

      await page.reload({ waitUntil: "networkidle" });
      await until(async () => (await body()).includes("小满的厨房"), "the kitchen opens again without asking");
      ok("the token is remembered in this browser");

      check(!urls.some((u) => u.includes(TOKEN)), "the token is in no address the browser requested");
      check(!page.url().includes(TOKEN), "nor in the page's own address");
      await sleep(300);
      check(!kitchen.log.join("").includes(TOKEN), "nor anywhere in the server's log");
      ok("the token never appears in an address or in the server's log");

      await tid("forget-token").click();
      await tid("token-gate").waitFor();
      await page.reload({ waitUntil: "networkidle" });
      await tid("token-gate").waitFor();
      ok("\"换口令\" forgets the token");
      await ctx.close();
    }

    // ── 2. embedded in another site's page ──────────────────────────
    {
      const ctx = await browser.newContext({ viewport: { width: 480, height: 1000 } });
      const page = await ctx.newPage();
      const errors = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      await page.goto(`${HOST_OK}/page_embed.html?kitchen=${encodeURIComponent(KITCHEN)}`, { waitUntil: "networkidle" });
      const frame = page.frameLocator("#kitchen");
      const hostLog = () => page.locator("#log").innerText();
      await until(async () => (await hostLog()).includes("kitchen: ready"), "the framed page says ready to its host");
      // the host answered with an empty credential: refused, and the page shows nothing of the kitchen
      await until(async () => (await hostLog()).includes("refused"), "an init without the right credential is refused");
      check((await frame.locator('[data-testid="title"]').count()) === 0, "no kitchen without the credential");
      ok("embedded: the page waits for its host and refuses a wrong credential");

      await page.locator("#token").fill(TOKEN);
      await page.locator("#send").click();
      await frame.locator('[data-testid="title"]').waitFor();
      check((await frame.locator('[data-testid="title"]').innerText()) === "小满的厨房", "the kitchen opens inside the frame");
      check((await frame.locator('[data-testid="forget-token"]').count()) === 0, "nothing is stored, so there is nothing to forget");
      ok("embedded: the host hands over the token and the kitchen opens");

      await frame.locator('[data-testid="back"]').click();
      await until(async () => (await hostLog()).includes("kitchen: close"), "back reaches the host");
      ok("embedded: \"返回\" tells the host");

      const framed = page.frames().find((f) => f.url().startsWith(KITCHEN));
      check(framed && !framed.url().includes(TOKEN), "the token is not in the frame's address");
      check((await framed.evaluate(() => { try { return localStorage.getItem("kitchenette.token"); } catch { return null; } })) === null, "and not stored by the framed page");
      ok("embedded: the token is neither in the address nor stored");

      // the host can switch the role and take the token back
      await addSecondRole();
      const send = (type, payload) => page.evaluate(([k, t, p]) => {
        document.getElementById("kitchen").contentWindow.postMessage({ v: 1, id: `x-${t}`, type: t, payload: p }, k);
      }, [KITCHEN, type, payload]);
      await send("logout", {});
      await frame.locator('[data-testid="booting"]').waitFor();
      check((await frame.locator('[data-testid="title"]').count()) === 0, "after logout nothing of the kitchen is shown");
      await page.locator("#who").fill("阿树");
      await page.locator("#send").click(); // a new init, naming the role to open
      await until(async () => (await frame.locator('[data-testid="title"]').count()) && (await frame.locator('[data-testid="title"]').innerText()) === "阿树的厨房", "init with who opens that role");
      await send("role", { who: "小满" });
      await until(async () => (await frame.locator('[data-testid="title"]').innerText()) === "小满的厨房", "a role message switches the kitchen");
      await until(async () => (await hostLog()).includes("kitchen: ok (x-role)"), "and is answered");
      ok("embedded: logout, a new init naming a role, and a role message");

      // a site that is not on the list may not frame the page at all
      const other = await ctx.newPage();
      const blocked = [];
      other.on("console", (m) => /frame-ancestors|Refused to frame/i.test(m.text()) && blocked.push(m.text()));
      await other.goto(`${HOST_NO}/page_embed.html?kitchen=${encodeURIComponent(KITCHEN)}`, { waitUntil: "load" });
      await sleep(1200);
      check(blocked.length > 0, "the browser refuses to frame the page for an unlisted site");
      check(!(await other.locator("#log").innerText()).includes("ready"), "and the page says nothing to it");
      ok("embedded: a site that is not listed in embed_origins cannot frame the page");
      await ctx.close();
    }
    console.log(`\n${passed} checks passed`);
  } catch (e) {
    console.error(`\nFAILED after ${passed} checks: ${e.message}`);
    process.exitCode = 1;
  } finally {
    await browser.close();
    hosts.forEach((h) => h.close());
    kitchen.proc.kill("SIGINT");
    await sleep(300);
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})();
