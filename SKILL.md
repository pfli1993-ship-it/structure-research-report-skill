---
name: structure-research-report
description: 用户上传/拖入研报时自动触发。把研究机构 PDF/Markdown 研报结构化为中文投资摘要长图，适用于股票、宏观、外汇、行业、生物科技等研报；可用 MinerU CLI/API 自动转换 PDF 为 Markdown，自动提取行业背景、企业介绍、边际变化、目标价、现价格、市值与估值，并用富途 OpenAPI 补充推荐个股的近期重大事件、新闻公告、讨论温度、技术异动、资金异动与近一月走势图，生成 HTML/PNG 并保存到下载文件夹；同时可把 Markdown 与生成长图归档到 Obsidian 并按关键词建立双链；输出中隐去具体机构名称并模糊化来源。
---

# Structure Research Report

## Default Processing Mode

- Default to `快处理模式` unless the user explicitly asks for `深度处理`, `慢处理`, `完整处理`, `补充最新行情`, `补充新闻`, `雪球情绪`, `富途事件脉冲`, or similar expanded research.
- In fast mode, prioritize getting from the source report to the Chinese structured HTML/PNG and Obsidian archive quickly. Use the report's own disclosed facts, tables, ratings, target prices, and valuation context first.
- In fast mode, automatically skip non-core boilerplate before structuring: appendices, legal disclaimers, disclosure appendix, analyst certification, required disclosures, rating-history tables, methodology/legal notices, contact directories, global research office lists, copyright pages, and duplicated OCR/table fragments that do not affect the investment thesis.
- In fast mode, skip optional post-report market pulse work by default: do not browse for current news, do not search 雪球/community discussion, and do not expand recent-event, sentiment, technical/funds-flow interpretation cards unless explicitly requested.
- In fast mode, Futu current-price/valuation data and the `近一个月走势图` may be included for supported single-company or recommended-stock modules when they can be fetched quickly. If quote or chart lookup is slow, unsupported, or permission-limited, omit the module or state the exact limitation compactly instead of blocking the long-image workflow.
- When the user asks for deep/slow/full processing, enable the optional current-news, discussion-temperature, event-pulse, and technical/funds-flow workflow described below.

## Workflow

0. Ensure Futu OpenD is available as soon as a research PDF is uploaded/dragged in.
   - Before extracting the report, run `scripts/ensure_futu_opend.py` to open the local Futu OpenD app when the default quote API port is not listening.
   - The helper checks `127.0.0.1:11111`; if the port is closed, it opens `/Applications/Futu_OpenD.app` or common fallback app names and waits for the port to become reachable.
   - This only starts the local OpenD application for quote and market-data access. It must not place trades, read positions, read account funds, read orders, or access trading credentials.
   - If OpenD cannot be found or the port does not become reachable, continue the report workflow and write the exact failure reason in the Futu price/valuation fields.

1. Read or convert the report first.
   - If the user provides an existing MinerU Markdown file, read it directly.
   - If the user provides a PDF or other document file, plan to run `scripts/mineru_obsidian_archive.py <file> --long-image <png>` after the long image is generated, unless the user explicitly asks not to archive to Obsidian. The script prefers local MinerU CLI, then falls back to MinerU standard API when `MINERU_API_TOKEN`/`MINERU_TOKEN` is set, then to the lightweight Agent API.
   - If local MinerU CLI is installed outside PATH, set `MINERU_CLI=/absolute/path/to/mineru` or `MINERU_CLI_ARGS` for a custom command template containing `{input}` and `{output}`.
   - MinerU/OpenDataLab credentials can be supplied via environment variables (`MINERU_TOKEN`, `MINERU_API_TOKEN`, `OPENXLAB_AK`, `OPENXLAB_SK`, `MINERU_ACCESS_KEY`, `MINERU_SECRET_KEY`) or macOS Keychain service `structure-research-report/mineru` with the same account names.
   - Never hard-code MinerU tokens, access keys, secret keys, Obsidian paths, or any private CLI credentials in the skill. Read credentials only from environment variables or macOS Keychain.
   - If MinerU conversion fails or is unavailable, use `pdfplumber`/`pypdf` when text extraction works.
   - For image-only PDFs, render pages with `pdftoppm` and visually inspect/OCR the most relevant pages.
   - Extract the report title, date, author/source, rating, target price, current/report price, key thesis, catalysts, risks, and source notes.
   - Before summarizing or designing the long image, discard boilerplate and non-thesis blocks. Stop reading the source body once it reaches sections such as `Disclosure Appendix`, `Important Disclosures`, `Analyst Certification`, `Required Disclosures`, `Ratings Distribution`, `Valuation Methodology and Risks`, `Disclaimers`, `Legal Entity Disclosure`, `Global Research`, `Research Offices`, `Copyright`, or their Chinese equivalents (`附录`, `免责声明`, `重要披露`, `分析师声明`, `评级分布`, `法律声明`, `研究方法与风险`, `版权声明`) unless a specific line is needed to verify rating, target price, or risk methodology.
   - Ignore repeated page headers/footers, table-of-contents residue, OCR artifacts, analyst contact blocks, email/phone lists, entity-registration paragraphs, and boilerplate risk/legal text. Keep only source-note-level evidence required for investment content, anonymization, or validation.
   - Treat the extracted broker/bank/research-house name as internal-only metadata. Do not display specific institution names in the final HTML, PNG, downloaded filename, footer, or final user-facing summary unless the user explicitly asks to preserve them.

2. Structure the content in Chinese.
   - Anonymize the source institution everywhere in the output. Use fuzzy labels such as `某国际投行`, `某外资券商`, `某研究机构`, `某卖方机构`, or `报告机构`, choosing the least awkward label for the context.
   - Do not write exact broker/investment-bank/research-house names in header eyebrows, section titles, body copy, source footnotes, file names, or image titles. Do not use wording like `<机构名> 认为`; use `报告认为`, `研报认为`, or `机构观点认为`.
   - Company names, stock codes, analyst ratings, target prices, report dates, and market data may remain visible when they are part of the investment content. Only the publishing institution name is anonymized.
   - For sector/multi-company reports that mention analyzable companies with usable quote mappings, use sections similar to: `行业背景`, `企业介绍与边际变化`, `价格与评级`, `市值与估值`.
   - For sector/macro/strategy reports that do not mention specific companies, omit company-specific sections entirely. Do not add placeholder modules such as `企业介绍`, `价格与评级`, `买入价格`, `现价格`, or `市值与估值`; focus the long image on `行业/宏观背景`, `边际变化`, `关键数据`, `投资含义`, and `风险`.
   - For Taiwan or Korea stocks, or any other market/code that the current Futu helper cannot fetch, omit `现价格`, `市值与估值`, `PE/PB`, and target-market-cap sections from the main body instead of showing “不适用/不支持” cards or tables. Mention the omission briefly in the footer/source note only when useful.
   - For Japan stocks such as `285A.T`/`285A JP`, first try the Futu code only if a reliable mapping exists. If Futu returns `Unknown stock` or the market is unsupported, do not show Futu valuation, capital-flow, analyst-consensus, or K-line cards. Use report-disclosed price/performance data and clearly label any chart as `报告披露表现可视化`, not a real daily K-line.
   - If a report mentions companies but all mentioned stocks are unsupported by the current Futu helper, include only qualitative company/industry impact when it is central to the thesis; do not display price/valuation tables unless the report itself provides enough reliable rating/target-price information and the user explicitly needs it.
   - For single-company reports with a supported Futu code, use: `行业背景`, `企业介绍`, `价格与评级`, `市值与估值`, `边际变化`, `关键催化剂/风险`.
   - In deep/slow/full processing mode, for single-company reports, and for sector reports that highlight recommended stocks with supported Futu codes, add a post-report market pulse module after `市值与估值` or after the company impact section:
     - `近期重大事件与方向判断`: summarize the report's recommendation first, then add what changed recently from current sources. Separate `研报观点` from `近期事件` and `方向判断`; do not present news as if it came from the original report.
     - `资讯搜寻`: supplement the report with recent company news, exchange announcements, earnings releases, guidance, buybacks/dividends, product/regulatory developments, and other material items. Prefer company IR/exchange filings/regulator pages for official facts; use 财新 and 36氪 as priority Chinese business-news sources for event context, industry-chain clues, and management/regulatory interpretation; use other reputable sources only when these do not cover the item. Include dates and concise source labels. If the user asks for the latest, browse current sources before writing this section.
     - `情绪温度计`: summarize observable discussion heat and bull/bear consensus from 雪球 as the priority community source. Track discussion volume/recency, repeated bullish arguments, repeated bearish arguments, controversial points, and whether comments are mostly catalyst-driven, valuation-driven, or risk-driven. Label the method, such as `雪球讨论观察`; do not invent numeric sentiment scores without data. Use Futu analyst consensus only as `卖方共识温度`, not as a proxy for retail-user sentiment.
     - `技术异动 + 资金异动`: use Futu K-line, capital-flow, capital-distribution, and where applicable HK broker-flow data to judge breakout, trend, volume, and net inflow/outflow. Mention failed or permission-limited subfields in the footnote instead of fabricating them.
     - `近一个月走势图`: include the chart PNG generated by `scripts/get_stock_event_pulse.py` when Futu K-line data is available.
   - Treat “买入价格” as the anonymized research report target price unless the user states another rule.
   - For “现价格（富途）”, use the `futuapi` skill/script when possible. If the market/code is unsupported or data permission fails, write the exact failure reason and do not substitute another quote source unless the user asks.
   - For stock reports, include a fixed `市值与估值` module with:
     - `现市值`: Futu `total_market_val`.
     - `目标价对应市值`: `现市值 × 研报目标价 ÷ 富途现价`; label it as an estimate assuming the current share count remains unchanged.
     - `市盈率`: prefer Futu `pe_ttm_ratio` and label it `PE-TTM`; use `pe_ratio` only as a clearly labeled static-PE fallback.
     - `市净率`: Futu `pb_ratio`.
   - Run `scripts/get_valuation_snapshot.py <FUTU_CODE> --target-price <TARGET_PRICE>` to fetch and calculate the valuation module. This script automatically calls `scripts/ensure_futu_opend.py` first unless `--no-auto-start-opend` is passed. If Futu returns an invalid or unavailable field, show `暂无有效数据` and the failure reason instead of deriving it from another source.
   - In fast mode, run `scripts/get_stock_event_pulse.py <FUTU_CODE> --target-price <TARGET_PRICE>` only when a supported stock should include `近一个月走势图`; embed `chart.path` if present, but do not expand the rest of the event-pulse JSON into recent-event, sentiment, technical, or funds-flow cards unless the user asked for deep/slow/full processing.
   - In deep/slow/full processing mode, run `scripts/get_stock_event_pulse.py <FUTU_CODE> --target-price <TARGET_PRICE>` for every recommended/analyzable stock that receives the post-report market pulse module. The script automatically calls `scripts/ensure_futu_opend.py` first unless `--no-auto-start-opend` is passed. It returns JSON for `snapshot`, `analyst_consensus`, `technical`, `capital_flow`, `capital_distribution`, `top_brokers`, `kline`, and `chart`.
   - Use the event-pulse JSON as follows:
     - `snapshot` may also satisfy the current-price/valuation module when it contains the same fields required by `get_valuation_snapshot.py`.
     - `analyst_consensus` supports a small `卖方共识温度` card with target-price range, average target price, rating distribution, analyst count, and update date when available.
     - `technical.summary`, `one_month_return_pct`, `ma5/ma10/ma20`, `breakout_20d_high`, and `latest_volume_vs_5d_avg` support the technical-change narrative.
     - `capital_flow.direction`, `recent_5d_main_in_flow`, and `capital_distribution.net_super_big` support the funds-flow narrative.
     - `top_brokers` is only for HK stocks and requires permissions; if unavailable, omit the broker row or footnote the failure.
     - `chart.path` should be embedded in the HTML as the one-month chart if present. If `chart.error` is present, omit the chart image and write the reason in a compact data note.
   - The current local Futu OpenAPI methods available to this skill do not expose news/announcement feeds or community discussion sentiment. For `资讯搜寻`, browse official filings plus 财新 and 36氪 when needed; for user-discussion `情绪温度计`, browse/search 雪球 first. Cite the visible source, date, and what was actually accessible. Do not bypass paywalls, login walls, robots restrictions, or private/community-only content; if only titles/snippets are accessible, say so and avoid overclaiming. Keep web/platform findings separate from Futu-derived fields.

3. Generate a self-contained HTML long-image source.
   - Default width: `1080px`.
   - Use restrained research-card styling, clear source footnotes, and avoid overcrowded text.
   - Set the `<h1>` to the report topic; the export script uses it as the downloaded PNG filename.
   - Keep the `<h1>` and generated file title free of exact broker/investment-bank/research-house names so the downloaded PNG filename is also anonymized.
   - Save as `structured_report_<topic>.html` or another `structured_report*.html` filename in the working directory.
   - Display large market caps in readable local-currency units such as `亿元`, `HKD bn`, or `USD bn`, and keep the original currency explicit.
   - For the post-report market pulse module, keep the layout compact: one row for event/news bullets, one row for sentiment/consensus, one row for technical and funds-flow cards, and then the one-month chart. Avoid turning the long image into a raw news dump.

4. Export and download.
   - Run `scripts/export_long_images.mjs` from this skill to screenshot HTML into PNG, copy it to `~/Downloads`, and rename it from the `<h1>` topic.
   - Do not automatically open the generated image with Pixea or any other image viewer. The export script skips viewer opening by default.
   - Only if the user explicitly asks to open the generated image, set `STRUCTURE_REPORT_OPEN_VIEWER=1` before running the export script; in that mode the script opens Pixea and uses best-effort macOS UI automation to enter fullscreen and select Pixea's Hand Tool/move-picture mode.
   - Pass specific HTML files to export only those files, or pass no files to export all `structured_report*.html` in the current directory.

5. Always archive Markdown and long image to Obsidian after export, unless the user explicitly asks not to archive.
   - Run `scripts/mineru_obsidian_archive.py <source-pdf-or-md> --long-image <local-or-download-png>` after `export_long_images.mjs` succeeds. Prefer the downloaded PNG path from the export JSON when available; otherwise use the local long-image PNG.
   - Set `OBSIDIAN_VAULT_PATH=/path/to/vault` to archive directly into the user's vault. If it is unset, the script reads Obsidian's local `obsidian.json` and uses the currently open or most recent vault when available. The default note folder is `研报`; copied PNG attachments go to `研报附件`.
   - The archived note filename must start with archive time in `YYYYMMDD-HHMMSS ` format, followed by the sanitized report title, so Obsidian file-name sorting matches archive chronology. The note frontmatter must also include `archived_at`.
   - The archived note must put the generated long image at the very top of the Markdown body, immediately after YAML frontmatter, so opening the note shows the long image first.
   - The script adds an `## 自动链接` section with `[[关键词]]` links derived from tickers, company names, themes, and user-provided keywords. Pass `--keywords "Apple,AAPL,WWDC"` to force links.
   - The archived Markdown also anonymizes broker/research-house names by default. Use exact source names only if the user explicitly asks to preserve them.
   - After archiving, scan the note for exact broker names, broker abbreviations, analyst names, analyst emails, and broker disclosure URLs. If any remain, anonymize them in the note and add the pattern to `scripts/mineru_obsidian_archive.py` before considering the workflow complete.
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

The script prints JSON including `localPng`, `downloadPng`, `openedInPixea`, and `pixea` status. By default `openedInPixea` is `false` and the status says viewer opening was skipped.

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
- `OPENXLAB_AK` / `OPENXLAB_SK` or `MINERU_ACCESS_KEY` / `MINERU_SECRET_KEY`: optional OpenDataLab/MinerU CLI credentials. The archive script also reads these from macOS Keychain service `structure-research-report/mineru`.
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

## Stock Event Pulse

Fetch a Futu-backed event/technical/funds packet and a one-month chart for a recommended stock:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/get_stock_event_pulse.py HK.00700 --target-price 450
```

Write the chart to a specific location:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/get_stock_event_pulse.py US.AAPL \
  --chart-out stock_pulse_AAPL_1m.png
```

The script prints JSON including `snapshot`, `analyst_consensus`, `technical`, `capital_flow`, `capital_distribution`, `top_brokers`, `kline`, `chart`, `limitations`, and optional `errors`. It only uses quote/market-data APIs and must not call trading/account APIs.

## Validation

- Confirm extracted rating/target price/current report price against the PDF table or title page.
- Confirm the final HTML/PNG and downloaded filename do not reveal the exact publishing institution name; use only fuzzy source labels.
- Confirm current market cap, PE-TTM/static PE, and PB come from the same Futu snapshot as the current price.
- Recalculate `目标价对应市值 = 现市值 × 目标价 ÷ 现价` and label the unchanged-share-count assumption.
- For every included post-report market pulse module, confirm `scripts/get_stock_event_pulse.py` was run for the displayed Futu code or clearly explain why it could not run.
- Confirm the `资讯搜寻` section uses current sourced news/announcement details and does not imply those items came from Futu when they came from web/company/exchange sources.
- Confirm the `情绪温度计` distinguishes user-discussion heat from Futu analyst consensus. If user-discussion data is unavailable, say so plainly and show only sourced analyst/news consensus.
- Confirm technical and funds-flow claims are traceable to the event-pulse JSON fields or are explicitly marked as source-limited.
- Confirm the one-month chart image exists when shown in HTML and is copied/embedded with a stable local path before export.
- Confirm the PNG is non-empty and has width `1080`.
- Confirm the downloaded PNG exists in `~/Downloads` and `openedInPixea` is `false` unless the user explicitly requested viewer opening.
- If viewer opening was explicitly requested, confirm Pixea fullscreen/Hand Tool automation reports `menu` or `shortcut`/`space-fallback`; if it reports `failed`, tell the user to grant Accessibility permission to Codex/Terminal/System Events.
- Confirm Obsidian archival was run by default after export unless the user explicitly opted out.
- Confirm the archived note filename starts with `YYYYMMDD-HHMMSS ` and frontmatter includes `archived_at`, so archive ordering can follow archive time.
- Confirm the note exists, the copied long image exists, and the first non-frontmatter Markdown block is an image embed (`![[...]]` or `![...](...)`).
- Confirm the note contains an `## 自动链接` section with useful `[[关键词]]` links and does not reveal the exact publishing institution name unless explicitly requested.
- Confirm the archived Markdown does not retain exact analyst names, broker entity abbreviations such as `JPMS`, or broker disclosure URLs after MinerU conversion.
- If quote retrieval fails, ensure the long image says why and does not silently replace the source.
