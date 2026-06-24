# structure-research-report-skill

Codex skill for turning research PDFs into concise Chinese structured long images, with the publishing institution anonymized in final outputs.

## What It Does

- Reads sell-side research PDFs and helps Codex extract the report thesis.
- Anonymizes the publishing broker/bank/research-house name in the HTML, PNG, downloaded filename, source footnotes, and user-facing summaries.
- Structures the output into Chinese sections such as:
  - 行业背景
  - 企业介绍
  - 边际变化
  - 买入价格
  - 现价格
  - 市值与估值（现市值、目标价对应市值、PE-TTM、PB）
  - 近期重大事件与方向判断
  - 资讯搜寻（官方公告、财新、36氪等）
  - 情绪温度计（雪球讨论热度与多空共识）
  - 技术异动 + 资金异动
  - 近一个月走势图
  - 关键催化剂 / 风险
- Omits company, price, and valuation modules when the report has no specific companies or when all mentioned stocks are in currently unsupported quote markets such as Taiwan or Korea.
- Generates a self-contained `structured_report*.html`.
- Exports the HTML into a `1080px` wide PNG long image.
- Copies the PNG to `~/Downloads`.
- Opens the downloaded PNG with Pixea when Pixea is installed.
- Uses best-effort macOS UI automation to put Pixea into fullscreen and select the Hand Tool / move-picture mode.
- Automatically opens/verifies the local Futu OpenD app when a research PDF workflow starts or when valuation snapshots are requested.
- Uses Futu OpenAPI to build a stock event pulse packet for supported recommended stocks, including snapshots, analyst consensus, technical signals, funds flow, HK broker-flow data when available, and a one-month chart.
- Uses official filings plus 财新 and 36氪 for news/event context when current web research is needed; uses 雪球 as the priority source for user-discussion heat and bull/bear consensus.
- Converts PDFs or other supported documents to Markdown with local MinerU CLI first, then MinerU API fallback when configured.
- Archives the Markdown into Obsidian, copies the generated long-image PNG into the vault, and embeds that image at the very top of the note.
- Adds an automatic keyword wikilink section such as `[[Apple]]`, `[[AAPL]]`, and `[[WWDC]]`.

## Privacy And Credentials

This repository does **not** contain:

- Futu/OpenD credentials or account data
- API keys or LLM tokens
- MinerU API tokens
- Gmail, Google Drive, GitHub, or other connector credentials
- Research PDFs
- Generated HTML/PNG report outputs
- Exact publishing institution names in generated public-facing outputs

The bundled export script only screenshots local HTML files and copies PNGs to the local Downloads folder. If Codex uses Futu for prices, it uses the local user's own Futu/OpenD environment outside this repository.

The valuation helper queries only public market snapshot fields from the user's local Futu OpenD. It does not access trading accounts, positions, orders, credentials, or tokens.

The OpenD helper only checks whether `127.0.0.1:11111` is listening and, if not, opens the local macOS app such as `/Applications/Futu_OpenD.app`. It does not log in, trade, read positions, read orders, or send credentials anywhere.

The MinerU/Obsidian helper reads optional configuration only from environment variables, macOS Keychain, and local Obsidian configuration files. It does not store API tokens, access keys, or secret keys in the repository. If `MINERU_API_TOKEN` is used, the source document is uploaded to MinerU's API; otherwise the helper prefers local MinerU CLI when available.

## Installation

Clone or copy this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/pfli1993-ship-it/structure-research-report-skill.git \
  ~/.codex/skills/structure-research-report
```

Restart Codex if the skill is not discovered immediately.

## Usage

By default, this skill runs in `快处理模式`: it turns the report into a concise Chinese long image and archives it, can include a one-month chart for clearly supported company stocks when it is quick to fetch, and skips optional current-news browsing, Xueqiu sentiment, full Futu event-pulse interpretation, and technical/funds-flow cards unless the user explicitly asks for deep/slow/full processing.

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

Fetch a Futu-backed stock event pulse packet and one-month chart:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/get_stock_event_pulse.py \
  HK.00700 --target-price 450 --chart-out stock_pulse_00700_1m.png
```

The valuation command auto-starts Futu OpenD when needed. You can also verify or open OpenD directly:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/ensure_futu_opend.py
```

Archive a generated long image together with an existing MinerU Markdown file:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/mineru_obsidian_archive.py \
  report.md \
  --long-image structured_report_example_long.png \
  --keywords "Apple,AAPL,WWDC"
```

Convert a PDF with MinerU and archive the converted Markdown into Obsidian:

```bash
python3 ~/.codex/skills/structure-research-report/scripts/mineru_obsidian_archive.py \
  report.pdf \
  --long-image structured_report_example_long.png
```

The archive helper uses `OBSIDIAN_VAULT_PATH` when set. If it is unset, it reads Obsidian's local `obsidian.json` and uses the currently open or most recent vault. Notes are saved under `研报` by default; PNG attachments are copied under `研报附件`.

The script prints JSON containing:

- `localPng`
- `downloadPng`
- `openedInPixea`
- `pixea.fullscreen`
- `pixea.moveTool`
- `pixea.warning`

The Obsidian archive script prints JSON containing:

- `notePath`
- `method`
- `mineruTaskId`
- `keywords`
- `obsidian.opened`
- `obsidian.warning`

## Requirements

- macOS for Pixea auto-open behavior.
- Google Chrome at `/Applications/Google Chrome.app`, or a Playwright-managed Chromium.
- Codex bundled Node runtime or a local Node environment with Playwright available.
- Futu OpenD and `futu-api` for current price, market cap, PE, and PB fields.
- `matplotlib` for the optional one-month chart generated by `get_stock_event_pulse.py`.
- Futu OpenD installed as `/Applications/Futu_OpenD.app` or another common OpenD app name for auto-start behavior.
- MinerU CLI, or `MINERU_API_TOKEN` / `MINERU_TOKEN` for MinerU standard API fallback.
- Obsidian for automatic note opening and vault archival.
- macOS Accessibility permission for Codex/Terminal/System Events if you want Pixea fullscreen and Hand Tool automation. Without it, export still works and the JSON includes a warning.

Optional environment variables:

- `MINERU_CLI`: absolute path to local MinerU CLI when it is not on `PATH`.
- `MINERU_CLI_ARGS`: custom CLI template using `{input}` and `{output}` placeholders.
- `MINERU_API_TOKEN` or `MINERU_TOKEN`: MinerU standard API token.
- `OPENXLAB_AK` / `OPENXLAB_SK` or `MINERU_ACCESS_KEY` / `MINERU_SECRET_KEY`: OpenDataLab/MinerU CLI credentials. The archive helper also reads these from macOS Keychain service `structure-research-report/mineru`.
- `MINERU_MODEL_VERSION`: default MinerU API model version, normally `vlm`.
- `OBSIDIAN_VAULT_PATH`: explicit Obsidian vault path.

## Notes

- The `<h1>` in the generated HTML is used as the downloaded PNG filename, so it should not contain exact broker, bank, or research-house names.
- Always hide the exact publishing institution name in final outputs. Prefer fuzzy wording such as `某国际投行`, `某外资券商`, `某研究机构`, `某卖方机构`, `报告机构`, `报告认为`, or `研报认为`.
- After Obsidian archival, scan MinerU Markdown for residual analyst names, broker abbreviations, emails, and broker disclosure URLs; anonymize the note and extend the archive script patterns when a new residual form appears.
- Pixea automation is best-effort because menu labels and macOS permissions can vary by app version and language.
- Unsupported market quotes should not be replaced with another source. For Taiwan, Korea, or other currently unsupported markets, omit current-price and valuation modules from the main image; mention the omission briefly in the source note only when useful.
- For Japan stocks that Futu returns as `Unknown stock`, use report-disclosed price/performance data only, label any performance chart as report-based rather than a real daily K-line, and omit Futu valuation/funds-flow cards.
- If a report does not mention specific companies, do not add placeholder `买入价格`, `现价格`, or `市值与估值` sections. Keep the long image focused on the report thesis, key data, marginal changes, investment implications, and risks.
- “买入价格” defaults to the anonymized research report target price unless the user specifies another rule.
- Target-price market cap is an estimate calculated as `current market cap × target price ÷ current price`, assuming the current share count remains unchanged.
- Futu OpenAPI does not provide the current workflow's news feed or retail discussion sentiment. Use official filings, 财新, and 36氪 for news context, and use 雪球 for discussion temperature. Do not bypass paywalls or login walls; cite only visible/accessed source details.
- In archived Obsidian Markdown, the first block after YAML frontmatter is the generated long-image embed. This makes the long image visible before the raw MinerU text.
- The archive helper avoids using appendix/legal disclosure sections for keyword link generation, so wikilinks focus on investable topics rather than disclosure boilerplate.
