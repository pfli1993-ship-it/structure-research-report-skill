# structure-research-report-skill

Codex skill for turning broker research PDFs into concise Chinese structured long images.

## What It Does

- Reads sell-side research PDFs and helps Codex extract the report thesis.
- Structures the output into Chinese sections such as:
  - 行业背景
  - 企业介绍
  - 边际变化
  - 买入价格
  - 现价格
  - 市值与估值（现市值、目标价对应市值、PE-TTM、PB）
  - 关键催化剂 / 风险
- Generates a self-contained `structured_report*.html`.
- Exports the HTML into a `1080px` wide PNG long image.
- Copies the PNG to `~/Downloads`.
- Opens the downloaded PNG with Pixea when Pixea is installed.
- Uses best-effort macOS UI automation to put Pixea into fullscreen and select the Hand Tool / move-picture mode.

## Privacy And Credentials

This repository does **not** contain:

- Futu/OpenD credentials or account data
- API keys or LLM tokens
- Gmail, Google Drive, GitHub, or other connector credentials
- Research PDFs
- Generated HTML/PNG report outputs

The bundled export script only screenshots local HTML files and copies PNGs to the local Downloads folder. If Codex uses Futu for prices, it uses the local user's own Futu/OpenD environment outside this repository.

The valuation helper queries only public market snapshot fields from the user's local Futu OpenD. It does not access trading accounts, positions, orders, credentials, or tokens.

## Installation

Clone or copy this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/pfli1993-ship-it/structure-research-report-skill.git \
  ~/.codex/skills/structure-research-report
```

Restart Codex if the skill is not discovered immediately.

## Usage

Ask Codex:

```text
用 structure-research-report 把这份研报结构化成长图
```

After Codex creates a `structured_report*.html`, export it with:

```bash
node ~/.codex/skills/structure-research-report/scripts/export_long_images.mjs structured_report_example.html
```

Or export every `structured_report*.html` in the current directory:

```bash
node ~/.codex/skills/structure-research-report/scripts/export_long_images.mjs
```

Fetch a valuation snapshot and estimate the market cap corresponding to a report target price:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/get_valuation_snapshot.py \
  SH.688222 --target-price 31.60
```

The script prints JSON containing:

- `localPng`
- `downloadPng`
- `openedInPixea`
- `pixea.fullscreen`
- `pixea.moveTool`
- `pixea.warning`

## Requirements

- macOS for Pixea auto-open behavior.
- Google Chrome at `/Applications/Google Chrome.app`, or a Playwright-managed Chromium.
- Codex bundled Node runtime or a local Node environment with Playwright available.
- Futu OpenD and `futu-api` for current price, market cap, PE, and PB fields.
- macOS Accessibility permission for Codex/Terminal/System Events if you want Pixea fullscreen and Hand Tool automation. Without it, export still works and the JSON includes a warning.

## Notes

- The `<h1>` in the generated HTML is used as the downloaded PNG filename.
- Pixea automation is best-effort because menu labels and macOS permissions can vary by app version and language.
- Unsupported market quotes should be shown as unavailable with the exact failure reason instead of silently replacing the quote source.
- “买入价格” defaults to the broker report target price unless the user specifies another rule.
- Target-price market cap is an estimate calculated as `current market cap × target price ÷ current price`, assuming the current share count remains unchanged.
