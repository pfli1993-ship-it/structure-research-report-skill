---
name: structure-research-report
description: 用户上传/拖入研报时自动触发。把券商/投行/研究机构 PDF 研报结构化为中文投资摘要长图，适用于股票、宏观、外汇、行业、生物科技等研报；自动提取行业背景、企业介绍、边际变化、买入价格/目标价、现价格，生成 HTML/PNG，保存到下载文件夹并用 Pixea 打开。
---

# Structure Research Report

## Workflow

1. Read the PDF first.
   - Use `pdfplumber`/`pypdf` when text extraction works.
   - For image-only PDFs, render pages with `pdftoppm` and visually inspect/OCR the most relevant pages.
   - Extract the report title, date, author/source, rating, target price, current/report price, key thesis, catalysts, risks, and source notes.

2. Structure the content in Chinese.
   - For sector/multi-company reports, use sections similar to: `行业背景`, `企业介绍与边际变化`, `买入价格`, `现价格`.
   - For single-company reports, use: `行业背景`, `企业介绍与买入价格`, `边际变化`, `关键催化剂/风险`.
   - Treat “买入价格” as the broker report target price unless the user states another rule.
   - For “现价格（富途）”, use the `futuapi` skill/script when possible. If the market/code is unsupported or data permission fails, write the exact failure reason and do not substitute another quote source unless the user asks.

3. Generate a self-contained HTML long-image source.
   - Default width: `1080px`.
   - Use restrained research-card styling, clear source footnotes, and avoid overcrowded text.
   - Set the `<h1>` to the report topic; the export script uses it as the downloaded PNG filename.
   - Save as `structured_report_<topic>.html` or another `structured_report*.html` filename in the working directory.

4. Export, download, and open.
   - Run `scripts/export_long_images.mjs` from this skill to screenshot HTML into PNG, copy it to `~/Downloads`, rename it from the `<h1>` topic, and open it with Pixea.
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

The script prints JSON including `localPng`, `downloadPng`, and `openedInPixea`.

## Validation

- Confirm extracted rating/target price/current report price against the PDF table or title page.
- Confirm the PNG is non-empty and has width `1080`.
- Confirm the downloaded PNG exists in `~/Downloads` and `openedInPixea` is `true` when Pixea is installed.
- If quote retrieval fails, ensure the long image says why and does not silently replace the source.
