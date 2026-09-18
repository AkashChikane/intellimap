/**
 * Capture README-ready screenshots of IntelliMap.
 *
 * Run from Windows after API (:8000) and UI (:3000) are up.
 * Does not edit README.md — writes PNGs + a markdown snippet you can paste later.
 *
 *   capture-screenshots.bat
 *   or:  node scripts/capture-screenshots.mjs
 *
 * Optional env:
 *   BASE_URL   default http://localhost:3000
 *   OUT_DIR    default docs/screenshots
 */
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baseUrl = process.env.BASE_URL || "http://localhost:3000";
const outDir = path.resolve(root, process.env.OUT_DIR || "docs/screenshots");

const SHOTS = [
  { file: "01-home-upload.png", alt: "Upload a landscape workbook" },
  { file: "02-workbook.png", alt: "Workbook sheet review with Excel-style tabs" },
  { file: "03-review-findings.png", alt: "Findings review with meaning, fix, and accept/reject" },
  { file: "04-explorer.png", alt: "Scoped context diagram in the explorer" },
  { file: "05-explorer-findings.png", alt: "Findings sidebar and AI insights on the diagram" },
  { file: "06-explorer-assistant.png", alt: "Frame-grounded assistant beside the diagram" },
  { file: "07-spotlight.png", alt: "Find (Ctrl+K) spotlight over the diagram" },
  { file: "08-home-dark.png", alt: "Home screen in dark mode" },
  { file: "09-home-german.png", alt: "Home screen in German" },
];

async function waitForLoader(page) {
  const overlay = page.locator(".loader-overlay");
  try {
    await overlay.waitFor({ state: "visible", timeout: 2500 });
  } catch {
    /* overlay may not appear */
  }
  await overlay.waitFor({ state: "detached", timeout: 180000 }).catch(() => {});
}

async function shot(page, name, fullPage = false) {
  const dest = path.join(outDir, name);
  await page.waitForTimeout(400);
  await page.screenshot({
    path: dest,
    fullPage,
    animations: "disabled",
    caret: "hide",
  });
  console.log("wrote", path.relative(root, dest));
}

async function main() {
  await mkdir(outDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "en-US",
    colorScheme: "light",
  });
  await context.addInitScript(() => {
    localStorage.setItem("intellimap-color-mode", "light");
    localStorage.setItem("intellimap-lang", "en");
  });
  const page = await context.newPage();
  page.setDefaultTimeout(120000);

  console.log("Opening", baseUrl);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.getByTestId("api-pill").filter({ hasText: /ready|bereit/i }).waitFor({ timeout: 90000 });

  await shot(page, "01-home-upload.png", true);

  await page.getByTestId("load-sample").click();
  await waitForLoader(page);
  await page.getByTestId("workbook-stage").waitFor();
  await page.waitForTimeout(600);
  await shot(page, "02-workbook.png", true);

  await page.getByTestId("continue-review").click();
  await waitForLoader(page);
  await page.getByTestId("review-stage").waitFor();
  await page.waitForTimeout(500);
  await shot(page, "03-review-findings.png");

  await page.getByTestId("open-explorer").click();
  await waitForLoader(page);
  await page.getByTestId("explorer").waitFor();
  await page.locator(".im-node, .react-flow__node").first().waitFor({ timeout: 90000 });
  await page.waitForTimeout(800);
  await shot(page, "04-explorer.png");

  await page.getByTestId("toggle-findings").click();
  await page.waitForTimeout(500);
  await shot(page, "05-explorer-findings.png");
  await page.getByTestId("toggle-findings").click();

  await page.getByTestId("toggle-assistant").click();
  await page.waitForTimeout(500);
  await shot(page, "06-explorer-assistant.png");

  await page.getByTestId("open-find").click();
  await page.getByRole("dialog", { name: /find|suchen/i }).waitFor();
  const findBox = page.getByRole("dialog").locator("input").first();
  await findBox.fill("APP-0005");
  await page.waitForTimeout(400);
  await shot(page, "07-spotlight.png");
  await page.keyboard.press("Escape");

  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.getByTestId("api-pill").waitFor();
  await page.getByTestId("theme-toggle").click();
  await page.waitForTimeout(300);
  await shot(page, "08-home-dark.png", true);

  await page.getByTestId("theme-toggle").click();
  await page.getByTestId("lang-toggle").click();
  await page.waitForTimeout(300);
  await shot(page, "09-home-german.png", true);

  const snippet = [
    "## Screenshots",
    "",
    "Captured with `capture-screenshots.bat` (API on :8000, UI on :3000).",
    "",
    ...SHOTS.map(
      (s) => `![${s.alt}](docs/screenshots/${s.file})`
    ),
    "",
  ].join("\n");
  await writeFile(path.join(outDir, "README-SNIPPET.md"), snippet, "utf8");
  console.log("wrote docs/screenshots/README-SNIPPET.md — paste into README.md when ready");

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
