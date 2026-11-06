// Browser tests for the Command map and Guild mode. Needs Node 18+ and Playwright:
//   npm i -D playwright && npx playwright install chromium && node tests/test_ui.mjs
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
const require = createRequire(import.meta.url);
let pw; try { pw = require("playwright"); } catch { try { pw = require(process.env.PLAYWRIGHT_PATH || "/opt/node22/lib/node_modules/playwright"); } catch { console.log("SKIP: playwright not installed"); process.exit(0); } }
const ui = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "ui");
const url = (f, q = "") => "file://" + path.join(ui, f) + q;
let pass = 0, fail = 0;
const ok = (cond, name) => { if (cond) { pass++; console.log("ok   " + name); } else { fail++; console.log("FAIL " + name); } };
const browser = await pw.chromium.launch();
async function fresh(file, vp = { width: 1360, height: 1900 }) {
  const ctx = await browser.newContext({ viewport: vp }); const p = await ctx.newPage(); const errs = [];
  p.on("pageerror", (e) => errs.push(e.message)); await p.goto(url(file)); await p.evaluate(() => localStorage.clear()); await p.reload(); await p.waitForTimeout(400); return { p, errs, ctx };
}
async function drag(p, from, to) {
  await p.locator(to).first().scrollIntoViewIfNeeded(); await p.locator(from).first().scrollIntoViewIfNeeded();
  const a = await p.locator(from).first().boundingBox(), b = await p.locator(to).first().boundingBox();
  await p.mouse.move(a.x + a.width / 2, a.y + a.height / 2); await p.mouse.down();
  await p.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 10 }); await p.mouse.up(); await p.waitForTimeout(150);
}

// ---------------- Command map
{
  const { p, errs, ctx } = await fresh("command.html");
  ok(await p.locator(".mission").count() === 4, "command: example loads four missions");
  await p.click("#btn-clear"); ok(await p.locator("#rtitle").textContent() === "Not ready", "command: empty field is not ready");
  await drag(p, '.unitcard[data-role="builder"]', '[data-slot="hq:owner"]');
  ok(await p.locator('[data-slot="hq:owner"] .tok').count() === 0, "command: builder refused in the owner slot");
  await drag(p, '.unitcard[data-role="owner"]', '[data-slot="hq:owner"]');
  ok(await p.locator('[data-slot="hq:owner"] .tok').count() === 1, "command: owner placed by drag");
  await p.click("#btn-load"); await p.click("#btn-deploy");
  const tabs = await p.locator("#filetabs button").allTextContents();
  ok(tabs.includes("ROLES.md") && tabs.some((t) => t.startsWith("inbox/001_")), "command: deploy writes ROLES and instructions");
  ok(errs.length === 0, "command: no page errors " + errs.join("; ")); await ctx.close();
}

// ---------------- Guild
{
  const { p, errs, ctx } = await fresh("guild.html");
  
  await p.click('[data-room="map"]');
  ok(await p.locator("#tray .hero").count() === 9, "guild: demo guild has nine heroes");
  // forge a new artificer: cannot finish without the harness
  await p.click('[data-room="forge"]'); await p.click('[data-cls="artificer"]');
  await p.click("#f-next"); await p.click('[data-origin="Codex"]'); await p.click("#f-next");
  await p.fill("#h-name", "Test Smith"); await p.click("#f-next"); await p.click("#f-next");
  ok(await p.locator("#f-next").isDisabled(), "guild: can't enter without the full harness");
  await p.click("#f-back"); await p.click("#fit-all"); await p.waitForTimeout(1300);
  ok((await p.locator("#p-gear").textContent()) === "6/6", "guild: fit-all fits six pieces");
  await p.click("#f-next"); await p.click("#f-next");
  ok(await p.locator("#tray .hero", { hasText: "Test Smith" }).count() === 1, "guild: new hero joins the roster");
  // wrong class refused, right class placed
  await drag(p, '#tray .hero:has-text("Test Smith")', '[data-slot="q002:paladin"]');
  ok(await p.locator('[data-slot="q002:paladin"] .tok', { hasText: "Test" }).count() === 0, "guild: artificer refused in a paladin slot");
  ok((await p.locator("#toast").textContent()).includes("can't take"), "guild: refusal explains why");
  await drag(p, '#tray .hero:has-text("Ollo Inkwell")', '[data-slot="q002:scribe"]');
  ok(await p.locator('[data-slot="q002:scribe"] .tok').count() === 1, "guild: scribe placed by drag");
  // level-1 range: Nyx already holds one quest
  await drag(p, '#tray .hero:has-text("Nyx")', '[data-slot="q002:rogue"]');
  ok(await p.locator('[data-slot="q002:rogue"] .tok').count() === 0 && (await p.locator("#toast").textContent()).includes("at once"), "guild: level-1 hero limited to one quest");
  // proof: no XP without proof, sealed = full XP
  await p.click('[data-room="prove"]'); await p.click('#returned [data-prove]');
  ok(await p.locator("#pv-accept").isDisabled(), "guild: accept disabled without proof");
  const xp0 = await p.evaluate(() => Object.values(S.heroes).find((h) => h.name.startsWith("Brannoc")).xp);
  await p.fill("#pv-pr", "https://github.com/example/shop/pull/9"); await p.fill("#pv-tests", "24 passed"); await p.selectOption("#pv-verdict", "approve");
  await p.fill("#pv-op", "evidence/rate-limit.bundle"); await p.click("#pv-accept"); await p.waitForTimeout(400);
  const xp1 = await p.evaluate(() => Object.values(S.heroes).find((h) => h.name.startsWith("Brannoc")).xp);
  ok(xp1 - xp0 === 100, "guild: sealed quest gives the builder full XP (100)");
  ok((await p.locator("#chron li").first().textContent()).includes("◆"), "guild: chronicle marks the OpenProof seal");
  // talents
  await p.waitForTimeout(2600); await p.click('[data-room="train"]'); await p.click('[data-th]:has-text("Nyx")');
  const can = p.locator(".tal.can").first(); const name = (await can.locator("b").textContent());
  await can.click(); ok(await p.evaluate((n) => Object.values(S.heroes).find((h) => h.name.startsWith("Nyx")).talents.includes(n), name), "guild: level unlocks a talent that can be trained");
  // worlds rename everything, rules stay
  for (const [w, horn, boss] of [["neon", "Green-light the jobs", "Boss"], ["sky", "Press Start (deploy)", "Player One"], ["star", "Launch", "Admiral"]]) {
    await p.click(`[data-world="${w}"]`); await p.click('[data-room="map"]');
    ok((await p.locator("#btn-horn").textContent()) === horn && (await p.locator('[data-slot="keep:master"]').getAttribute("data-name")) === boss, `guild: ${w} world renames the game`);
  }
  // deploy files
  await p.click("#btn-horn"); const files = await p.locator("#ftabs button").allTextContents();
  ok(files.some((f) => f.startsWith("guild/")) && files.includes("COORDINATOR_PROMPT.txt"), "guild: deploy writes character sheets");
  ok(errs.length === 0, "guild: no page errors " + errs.join("; ")); await ctx.close();
}

// ---------------- Guild on a phone, handheld mode
{
  const { p, errs, ctx } = await fresh("guild.html", { width: 390, height: 844 });
  ok(await p.evaluate(() => document.documentElement.scrollWidth) <= 390, "phone: no sideways scroll");
  await p.click("#btn-hand"); ok(await p.locator("#pad").isVisible(), "phone: handheld pad shows");
  await p.click('[data-k="select"]'); ok(await p.locator("#room-map").evaluate((e) => e.classList.contains("on")), "phone: Select changes room");
  await p.click('[data-k="right"]'); await p.click('[data-k="right"]');
  ok(await p.evaluate(() => document.activeElement && document.activeElement !== document.body), "phone: D-pad moves focus");
  ok(errs.length === 0, "phone: no page errors " + errs.join("; ")); await ctx.close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`); process.exit(fail ? 1 : 0);
