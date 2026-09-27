// Visual acceptance for the Professional Staging Workbook: drives the real
// app (Next dev server + FastAPI) in headless Chromium and saves
// screenshots. Usage:
//   node scripts/staging-acceptance.mjs <outDir> <json scenario file>
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const [outDir, scenarioFile] = process.argv.slice(2);
const scenarios = JSON.parse(readFileSync(scenarioFile, "utf-8"));
const BASE = process.env.WEB_URL ?? "http://127.0.0.1:3000";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const report = [];

for (const scenario of scenarios) {
  const context = await browser.newContext({
    viewport: scenario.mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
  });
  const entry = { name: scenario.name, steps: [], errors };
  try {
    await page.goto(`${BASE}/extraction/new?documentId=${scenario.documentId}`, {
      waitUntil: "domcontentloaded",
      timeout: 120_000,
    });
    const workbook = page.getByText("Professional Staging Workbook", { exact: true });
    await workbook.waitFor({ timeout: 120_000 });
    await workbook.scrollIntoViewIfNeeded();
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${outDir}/${scenario.name}-00-workbook.png`, fullPage: false });
    entry.steps.push("workbook rendered");

    for (const [index, step] of (scenario.steps ?? []).entries()) {
      const shot = `${outDir}/${scenario.name}-${String(index + 1).padStart(2, "0")}-${step.label}.png`;
      if (step.tab) {
        await page.getByRole("tab", { name: new RegExp(`^${step.tab}`) }).first().click();
      }
      if (step.clickButton) {
        await page.getByRole("button", { name: step.clickButton, exact: true }).first().click();
      }
      if (step.waitForText) {
        await page.getByText(step.waitForText).first().waitFor({ timeout: 60_000 });
      }
      await page.waitForTimeout(step.settle ?? 1200);
      if (step.drawer) {
        const drawer = page.locator("div.fixed.inset-0.z-50");
        await drawer.waitFor({ timeout: 30_000 });
        const highlight = drawer.locator("[data-evidence-highlight]");
        await highlight.first().waitFor({ timeout: 60_000 }).catch(() => {});
        entry.steps.push(`${step.label}: highlight elements = ${await highlight.count()}`);
        await page.screenshot({ path: shot });
        await page.keyboard.press("Escape");
        await drawer.getByRole("button", { name: "Close source verification" }).click({ force: true }).catch(() => {});
      } else {
        await page.screenshot({ path: shot, fullPage: step.fullPage ?? false });
        entry.steps.push(step.label);
      }
    }
    if (scenario.mobile) {
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      entry.steps.push(`horizontal page overflow px = ${overflow}`);
    }
  } catch (err) {
    entry.failure = String(err);
    await page.screenshot({ path: `${outDir}/${scenario.name}-zz-failure.png` }).catch(() => {});
  }
  report.push(entry);
  await context.close();
}

await browser.close();
writeFileSync(`${outDir}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
