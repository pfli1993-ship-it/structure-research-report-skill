---
name: structure-research-report
description: 用户上传/拖入研报时自动触发。把研究机构 PDF/Markdown 研报结构化为中文投资摘要长图，适用于股票、宏观、外汇、行业、生物科技等研报；可用 MinerU CLI/API 自动转换 PDF 为 Markdown，自动提取行业背景、企业介绍、边际变化、目标价、现价格、市值与估值，生成 HTML/PNG，保存到下载文件夹并用 Pixea 打开；同时可把 Markdown 与生成长图归档到 Obsidian 并按关键词建立双链；输出中隐去具体机构名称并模糊化来源。
---

# Structure Research Report

## Workflow

0. Ensure Futu OpenD is available as soon as a research PDF is uploaded/dragged in.
   - Before extracting the report, run `scripts/ensure_futu_opend.py` to open the local Futu OpenD app when the default quote API port is not listening.
   - The helper checks `127.0.0.1:11111`; if the port is closed, it opens `/Applications/Futu_OpenD.app` or common fallback app names and waits for the port to become reachable.
   - This only starts the local OpenD application for quote access. It must not place trades, read positions, or access account/order data.
   - If OpenD cannot be found or the port does not become reachable, continue the report workflow and write the exact failure reason in the Futu price/valuation fields.

1. Read or convert the report first.
   - If the user provides an existing MinerU Markdown file, read it directly.
   - If the user provides a PDF or other document file and asks for archive/Markdown workflow, run `scripts/mineru_obsidian_archive.py <file> --long-image <png>` after the long image is generated. The script prefers local MinerU CLI, then falls back to MinerU standard API when `MINERU_API_TOKEN`/`MINERU_TOKEN` is set, then to the lightweight Agent API.
   - If local MinerU CLI is installed outside PATH, set `MINERU_CLI=/absolute/path/to/mineru` or `MINERU_CLI_ARGS` for a custom command template containing `{input}` and `{output}`.
   - Never hard-code MinerU tokens, Obsidian paths, or any private CLI credentials in the skill. Read tokens only from environment variables.
   - If MinerU conversion fails or is unavailable, use `pdfplumber`/`pypdf` when text extraction works.
   - For image-only PDFs, render pages with `pdftoppm` and visually inspect/OCR the most relevant pages.
   - Extract the report title, date, author/source, rating, target price, current/report price, key thesis, catalysts, risks, and source notes.
   - Treat the extracted broker/bank/research-house name as internal-only metadata. Do not display specific institution names in the final HTML, PNG, downloaded filename, footer, or final user-facing summary unless the user explicitly asks to preserve them.

2. Structure the content in Chinese.
   - Anonymize the source institution everywhere in the output. Use fuzzy labels such as `某国际投行`, `某外资券商`, `某研究机构`, `某卖方机构`, or `报告机构`, choosing the least awkward label for the context.
   - Do not write exact broker/investment-bank/research-house names in header eyebrows, section titles, body copy, source footnotes, file names, or image titles. Do not use wording like `<机构名> 认为`; use `报告认为`, `研报认为`, or `机构观点认为`.
   - Company names, stock codes, analyst ratings, target prices, report dates, and market data may remain visible when they are part of the investment content. Only the publishing institution name is anonymized.
   - For sector/multi-company reports that mention analyzable companies with usable quote mappings, use sections similar to: `行业背景`, `企业介绍与边际变化`, `价格与评级`, `市值与估值`.
   - For sector/macro/strategy reports that do not mention specific companies, omit company-specific sections entirely. Do not add placeholder modules such as `企业介绍`, `价格与评级`, `买入价格`, `现价格`, or `市值与估值`; focus the long image on `行业/宏观背景`, `边际变化`, `关键数据`, `投资含义`, and `风险`.
   - For Taiwan or Korea stocks, or any other market/code that the current Futu helper cannot fetch, omit `现价格`, `市值与估值`, `PE/PB`, and target-market-cap sections from the main body instead of showing “不适用/不支持” cards or tables. Mention the omission briefly in the footer/source note only when useful.
   - If a report mentions companies but all mentioned stocks are unsupported by the current Futu helper, include only qualitative company/industry impact when it is central to the thesis; do not display price/valuation tables unless the report itself provides enough reliable rating/target-price information and the user explicitly needs it.
   - For single-company reports with a supported Futu code, use: `行业背景`, `企业介绍`, `价格与评级`, `市值与估值`, `边际变化`, `关键催化剂/风险`.
   - Treat “买入价格” as the anonymized research report target price unless the user states another rule.
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
   - Keep the `<h1>` and generated file title free of exact broker/investment-bank/research-house names so the downloaded PNG filename is also anonymized.
   - Save as `structured_report_<topic>.html` or another `structured_report*.html` filename in the working directory.
   - Display large market caps in readable local-currency units such as `亿元`, `HKD bn`, or `USD bn`, and keep the original currency explicit.

4. Export, download, and open.
   - Run `scripts/export_long_images.mjs` from this skill to screenshot HTML into PNG, copy it to `~/Downloads`, rename it from the `<h1>` topic, and open it with Pixea.
   - After Pixea opens, the script uses best-effort macOS UI automation to enter fullscreen and select Pixea's Hand Tool/move-picture mode. If macOS Accessibility permission blocks automation, the PNG export still succeeds and the JSON warning explains the issue.
   - Pass specific HTML files to export only those files, or pass no files to export all `structured_report*.html` in the current directory.

5. Archive Markdown and long image to Obsidian when requested or when the user wants note archival.
   - Run `scripts/mineru_obsidian_archive.py <source-pdf-or-md> --long-image <local-or-download-png>`.
   - Set `OBSIDIAN_VAULT_PATH=/path/to/vault` to archive directly into the user's vault. If it is unset, the script reads Obsidian's local `obsidian.json` and uses the currently open or most recent vault when available. The default note folder is `研报`; copied PNG attachments go to `研报附件`.
   - The archived note must put the generated long image at the very top of the Markdown body, immediately after YAML frontmatter, so opening the note shows the long image first.
   - The script adds an `## 自动链接` section with `[[关键词]]` links derived from tickers, company names, themes, and user-provided keywords. Pass `--keywords "Apple,AAPL,WWDC"` to force links.
   - The archived Markdown also anonymizes broker/research-house names by default. Use exact source names only if the user explicitly asks to preserve them.
   - The script opens Obsidian with an `obsidian://open` URL when a vault is found; otherwise it saves the note to the fallback output directory and opens Obsidian best-effort.

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

## MinerU + Obsidian Archive

Archive an existing MinerU Markdown file and put a generated long image at the top:

```bash
OBSIDIAN_VAULT_PATH="/path/to/ObsidianVault" \
python3 ~/.codex/skills/structure-research-report/scripts/mineru_obsidian_archive.py report.md \
  --long-image structured_report_example_long.png \
  --keywords "Apple,AAPL,WWDC"
```

Convert a PDF with local MinerU CLI/API, archive the resulting Markdown, copy the long image into the vault, and open Obsidian:

```bash
OBSIDIAN_VAULT_PATH="/path/to/ObsidianVault" \
python3 ~/.codex/skills/structure-research-report/scripts/mineru_obsidian_archive.py report.pdf \
  --long-image structured_report_example_long.png
```

Environment variables:
- `MINERU_CLI`: optional absolute path to the local MinerU CLI.
- `MINERU_CLI_ARGS`: optional custom command template with `{input}` and `{output}`.
- `MINERU_API_TOKEN` or `MINERU_TOKEN`: optional MinerU standard API token.
- `OBSIDIAN_VAULT_PATH`: Obsidian vault path for direct archival.

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
- Confirm the final HTML/PNG and downloaded filename do not reveal the exact publishing institution name; use only fuzzy source labels.
- Confirm current market cap, PE-TTM/static PE, and PB come from the same Futu snapshot as the current price.
- Recalculate `目标价对应市值 = 现市值 × 目标价 ÷ 现价` and label the unchanged-share-count assumption.
- Confirm the PNG is non-empty and has width `1080`.
- Confirm the downloaded PNG exists in `~/Downloads` and `openedInPixea` is `true` when Pixea is installed.
- Confirm Pixea fullscreen/Hand Tool automation reports `menu` or `shortcut`/`space-fallback`; if it reports `failed`, tell the user to grant Accessibility permission to Codex/Terminal/System Events.
- When Obsidian archival is used, confirm the note exists, the copied long image exists, and the first non-frontmatter Markdown block is an image embed (`![[...]]` or `![...](...)`).
- Confirm the note contains an `## 自动链接` section with useful `[[关键词]]` links and does not reveal the exact publishing institution name unless explicitly requested.
- If quote retrieval fails, ensure the long image says why and does not silently replace the source.
