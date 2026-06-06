---
name: structure-research-report
description: 用户上传/拖入研报时自动触发。把券商/投行/研究机构 PDF 研报结构化为中文投资摘要长图，适用于股票、宏观、外汇、行业、生物科技等研报；自动提取行业背景、企业介绍、边际变化、目标价、现价格、市值与估值，生成 HTML/PNG，保存到下载文件夹并用 Pixea 打开。
---

# Structure Research Report

## Workflow

0. Ensure Futu OpenD is available as soon as a research PDF is uploaded/dragged in.
   - Before extracting the report, run `scripts/ensure_futu_opend.py` to open the local Futu OpenD app when the default quote API port is not listening.
   - The helper checks `127.0.0.1:11111`; if the port is closed, it opens `/Applications/Futu_OpenD.app` or common fallback app names and waits for the port to become reachable.
   - This only starts the local OpenD application for quote access. It must not place trades, read positions, or access account/order data.
   - If OpenD cannot be found or the port does not become reachable, continue the report workflow and write the exact failure reason in the Futu price/valuation fields.

1. Read the PDF first.
   - Use `pdfplumber`/`pypdf` when text extraction works.
   - For image-only PDFs, render pages with `pdftoppm` and visually inspect/OCR the most relevant pages.
   - Extract the report title, date, author/source, rating, target price, current/report price, key thesis, catalysts, risks, and source notes.

2. Structure the content in Chinese.
   - For sector/multi-company reports that mention analyzable companies with usable quote mappings, use sections similar to: `行业背景`, `企业介绍与边际变化`, `价格与评级`, `市值与估值`.
   - For sector/macro/strategy reports that do not mention specific companies, omit company-specific sections entirely. Do not add placeholder modules such as `企业介绍`, `价格与评级`, `买入价格`, `现价格`, or `市值与估值`; focus the long image on `行业/宏观背景`, `边际变化`, `关键数据`, `投资含义`, and `风险`.
   - For Taiwan or Korea stocks, or any other market/code that the current Futu helper cannot fetch, omit `现价格`, `市值与估值`, `PE/PB`, and target-market-cap sections from the main body instead of showing “不适用/不支持” cards or tables. Mention the omission briefly in the footer/source note only when useful.
   - If a report mentions companies but all mentioned stocks are unsupported by the current Futu helper, include only qualitative company/industry impact when it is central to the thesis; do not display price/valuation tables unless the report itself provides enough reliable rating/target-price information and the user explicitly needs it.
   - For single-company reports with a supported Futu code, use: `行业背景`, `企业介绍`, `价格与评级`, `市值与估值`, `边际变化`, `关键催化剂/风险`.
   - Treat “买入价格” as the broker report target price unless the user states another rule.
   - For “现价格（富途）”, use the `futuapi` skill/script when possible. If the market/code is unsupported or data permission fails, write the exact failure reason and do not substitute another quote source unless the user asks.
   - For stock reports, include a fixed `市值与估值` module with:
     - `现市值`: Futu `total_market_val`.
     - `目标价对应市值`: `现市值 × 研报目标价 ÷ 富途现价`; label it as an estimate assuming the current share count remains unchanged.
     - `市盈率`: prefer Futu `pe_ttm_ratio` and label it `PE-TTM`; use `pe_ratio` only as a clearly labeled static-PE fallback.
     - `市净率`: Futu `pb_ratio`.
   - Run `scripts/get_valuation_snapshot.py <FUTU_CODE> --target-price <TARGET_PRICE>` to fetch and calculate the valuation module. This script automatically calls `scripts/ensure_futu_opend.py` first unless `--no-auto-start-opend` is passed. If Futu returns an invalid or unavailable field, show `暂无有效数据` and the failure reason instead of deriving it from another source.

3. Generate a self-contained HTML long-image source.
   - Default width: `1080px`.
   - Use restrained research-card styling, clear source footnotes, and avoid overcrowded text.
   - Set the `<h1>` to the report topic; the export script uses it as the downloaded PNG filename.
   - Save as `structured_report_<topic>.html` or another `structured_report*.html` filename in the working directory.
   - Display large market caps in readable local-currency units such as `亿元`, `HKD bn`, or `USD bn`, and keep the original currency explicit.

4. Export, download, and open.
   - Run `scripts/export_long_images.mjs` from this skill to screenshot HTML into PNG, copy it to `~/Downloads`, rename it from the `<h1>` topic, and open it with Pixea.
   - After Pixea opens, the script uses best-effort macOS UI automation to enter fullscreen and select Pixea's Hand Tool/move-picture mode. If macOS Accessibility permission blocks automation, the PNG export still succeeds and the JSON warning explains the issue.
   - Pass specific HTML files to export only those files, or pass no files to export all `structured_report*.html` in the current directory.

## Export Script

From any working directory:

```bash
node ~/.codex/skills/structure-research-report/scripts/export_long_images.mjs structured_report_example.html
```

Or export every `structured_report*.html` in the current directory:

```bash
node ~/.codex/skills/structure-research-report/scripts/export_long_images.mjs
```

The script prints JSON including `localPng`, `downloadPng`, `openedInPixea`, and `pixea` automation details such as `fullscreen`, `moveTool`, and `warning`.

## Valuation Snapshot

Open or verify Futu OpenD:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/ensure_futu_opend.py
```

Fetch valuation fields. This also auto-starts OpenD when needed:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/get_valuation_snapshot.py SH.688222 --target-price 31.60
```

The script prints JSON including `last_price`, `market_cap`, `target_market_cap`, `pe_ttm`, `pe_static`, and `pb`.

## Validation

- Confirm extracted rating/target price/current report price against the PDF table or title page.
- Confirm current market cap, PE-TTM/static PE, and PB come from the same Futu snapshot as the current price.
- Recalculate `目标价对应市值 = 现市值 × 目标价 ÷ 现价` and label the unchanged-share-count assumption.
- Confirm the PNG is non-empty and has width `1080`.
- Confirm the downloaded PNG exists in `~/Downloads` and `openedInPixea` is `true` when Pixea is installed.
- Confirm Pixea fullscreen/Hand Tool automation reports `menu` or `shortcut`/`space-fallback`; if it reports `failed`, tell the user to grant Accessibility permission to Codex/Terminal/System Events.
- If quote retrieval fails, ensure the long image says why and does not silently replace the source.
