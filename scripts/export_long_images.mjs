#!/usr/bin/env node

import { createRequire } from "module";
import fs from "fs/promises";
import path from "path";
import os from "os";
import { fileURLToPath } from "url";
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const cwd = process.cwd();
const downloadsDir = path.join(os.homedir(), "Downloads");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const pixeaAppName = "Pixea";
const bundledNodeModules = path.join(
  os.homedir(),
  ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
);

function requirePlaywright() {
  const candidates = [
    path.join(bundledNodeModules, "playwright"),
    "playwright",
  ];
  for (const candidate of candidates) {
    try {
      const require = createRequire(import.meta.url);
      return require(candidate);
    } catch {
      // Try the next candidate.
    }
  }
  throw new Error("Cannot load Playwright. Use the Codex bundled Node runtime or install playwright.");
}

const { chromium } = requirePlaywright();

function sanitizeFilename(name) {
  return name
    .replace(/[\\/:*?"<>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

function outputNameForHtml(htmlPath, title) {
  const safeTitle = sanitizeFilename(title);
  if (safeTitle) return `${safeTitle}.png`;
  return `${path.basename(htmlPath, path.extname(htmlPath))}.png`;
}

async function discoverHtmlFiles(args) {
  if (args.length) return args.map((arg) => path.resolve(cwd, arg));

  const entries = await fs.readdir(cwd);
  return entries
    .filter((entry) => /^structured_report.*\.html$/.test(entry))
    .sort()
    .map((entry) => path.join(cwd, entry));
}

async function openInPixea(filePath) {
  try {
    await execFileAsync("open", ["-a", pixeaAppName, filePath]);
    return true;
  } catch (error) {
    console.warn(`Cannot open with ${pixeaAppName}: ${filePath}`);
    console.warn(error.message);
    return false;
  }
}

async function exportOne(browser, htmlPath) {
  const page = await browser.newPage({
    viewport: { width: 1080, height: 1600 },
    deviceScaleFactor: 1,
  });

  try {
    await page.goto(`file://${htmlPath}`, { waitUntil: "networkidle" });
    const title = await page.locator("h1").first().innerText().catch(() => "");
    const localPng = path.join(
      path.dirname(htmlPath),
      `${path.basename(htmlPath, path.extname(htmlPath))}_long.png`,
    );
    const downloadPng = path.join(downloadsDir, outputNameForHtml(htmlPath, title));

    await page.screenshot({ path: localPng, fullPage: true });
    await fs.copyFile(localPng, downloadPng);
    const openedInPixea = await openInPixea(downloadPng);

    return { htmlPath, title, localPng, downloadPng, openedInPixea };
  } finally {
    await page.close();
  }
}

async function main() {
  const htmlFiles = await discoverHtmlFiles(process.argv.slice(2));
  if (!htmlFiles.length) {
    throw new Error("No structured_report*.html files found in the current directory.");
  }

  const launchOptions = { headless: true };
  try {
    await fs.access(chromePath);
    launchOptions.executablePath = chromePath;
  } catch {
    // Fall back to Playwright's managed browser if present.
  }

  const browser = await chromium.launch(launchOptions);
  try {
    const results = await Promise.all(htmlFiles.map((file) => exportOne(browser, file)));
    for (const result of results) {
      console.log(JSON.stringify(result, null, 2));
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
