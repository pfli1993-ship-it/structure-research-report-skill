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
  const result = {
    opened: false,
    automationAttempted: false,
    fullscreen: "not-attempted",
    moveTool: "not-attempted",
    warning: "",
  };

  try {
    await execFileAsync("open", ["-a", pixeaAppName, filePath]);
    result.opened = true;
  } catch (error) {
    console.warn(`Cannot open with ${pixeaAppName}: ${filePath}`);
    console.warn(error.message);
    result.warning = error.message;
    return result;
  }

  const automation = await automatePixeaViewer();
  return { ...result, ...automation };
}

async function automatePixeaViewer() {
  const script = `
set fullScreenState to "not-found"
set moveToolState to "not-found"

tell application "Pixea" to activate
delay 0.8

tell application "System Events"
  if not (exists process "Pixea") then error "Pixea process is not available"

  tell process "Pixea"
    set frontmost to true
    delay 0.2

    set isAlreadyFullScreen to false
    try
      set isAlreadyFullScreen to value of attribute "AXFullScreen" of window 1
    end try

    if isAlreadyFullScreen is true then
      set fullScreenState to "already-fullscreen"
    else
      repeat with topItem in menu bar items of menu bar 1
        try
          set topMenu to menu 1 of topItem
          repeat with itemRef in menu items of topMenu
            try
              set itemName to name of itemRef as text
              if itemName is "Toggle Full Screen" or itemName is "Toggle Fullscreen" or itemName is "切换全屏" or itemName is "切换全屏幕" then
                click itemRef
                set fullScreenState to "menu"
                exit repeat
              end if
            end try
          end repeat
        end try
        if fullScreenState is "menu" then exit repeat
      end repeat

      if fullScreenState is "not-found" then
        try
          keystroke "f" using {control down, command down}
          set fullScreenState to "shortcut"
        end try
      end if
    end if

    delay 1.0

    repeat with topItem in menu bar items of menu bar 1
      try
        set topMenu to menu 1 of topItem
        repeat with itemRef in menu items of topMenu
          try
            set itemName to name of itemRef as text
            if itemName is "Hand Tool" or itemName is "手形工具" or itemName is "手工具" then
              click itemRef
              set moveToolState to "menu"
              exit repeat
            end if
          end try
        end repeat
      end try
      if moveToolState is "menu" then exit repeat
    end repeat

    if moveToolState is "not-found" then
      try
        key code 49
        set moveToolState to "space-fallback"
      end try
    end if
  end tell
end tell

return "fullscreen=" & fullScreenState & ";moveTool=" & moveToolState
`;

  try {
    const { stdout } = await execFileAsync("osascript", ["-e", script], { timeout: 15000 });
    const statusLine = stdout.trim();
    return {
      automationAttempted: true,
      fullscreen: statusLine.match(/fullscreen=([^;]+)/)?.[1] ?? "unknown",
      moveTool: statusLine.match(/moveTool=([^;]+)/)?.[1] ?? "unknown",
      warning: "",
    };
  } catch (error) {
    const details = [error.stderr, error.stdout, error.message].filter(Boolean).join(" ");
    const message = [
      "Pixea UI automation failed. macOS may require Accessibility permission for Codex/Terminal/System Events.",
      details,
    ].join(" ");
    console.warn(message);
    return {
      automationAttempted: true,
      fullscreen: "failed",
      moveTool: "failed",
      warning: message,
    };
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
    const pixea = await openInPixea(downloadPng);

    return { htmlPath, title, localPng, downloadPng, openedInPixea: pixea.opened, pixea };
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
