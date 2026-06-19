#!/usr/bin/env python3
"""Convert research files to Markdown with MinerU and archive them into Obsidian."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import requests
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("Missing dependency: requests. Install it with python3 -m pip install requests") from exc


STANDARD_API = "https://mineru.net/api/v4"
AGENT_API = "https://mineru.net/api/v1/agent"
DEFAULT_ARCHIVE_DIR = "研报"
DEFAULT_ATTACHMENT_DIR = "研报附件"
DEFAULT_KEYWORD_LIMIT = 18

BROKER_PATTERNS = [
    (r"\bJ\.?\s*P\.?\s*Morgan\b|\bJPMorgan\b|\bJPM\b", "某国际投行"),
    (r"\bCitigroup\b|\bCiti Research\b|\bCITI\b|\bCiti\b", "某国际投行"),
    (r"\bGoldman Sachs\b|\bGoldman\b", "某国际投行"),
    (r"\bMorgan Stanley\b", "某国际投行"),
    (r"\bBernstein\b", "某研究机构"),
    (r"\bJefferies\b", "某外资券商"),
    (r"\bNomura\b", "某外资券商"),
    (r"\bUBS\b", "某国际投行"),
    (r"\bBofA Securities\b|\bBank of America\b|\bBofA\b", "某国际投行"),
    (r"\bHSBC\b", "某国际投行"),
    (r"\bDeutsche Bank\b", "某国际投行"),
    (r"\bBarclays\b", "某国际投行"),
]

KEYWORD_SEEDS = [
    "Apple", "AAPL", "Broadcom", "AVGO", "NVIDIA", "NVDA", "AMD", "Oracle", "ORCL",
    "Tencent", "PDD", "Netflix", "Eli Lilly", "LLY", "TSMC", "CATL", "WuXi",
    "AI", "Apple Intelligence", "WWDC", "iPhone", "Siri", "Gemini", "TPU", "ASIC",
    "GPU", "Data Center", "GLP-1", "Obesity", "Smartphone", "Semiconductor",
    "Optical", "MLCC", "Biopharma", "Healthcare", "Transformer", "Export",
    "tariffs", "China", "Hong Kong", "Taiwan", "Korea",
]


@dataclass
class ConversionResult:
    markdown_path: Path
    method: str
    task_id: str | None = None
    source_url: str | None = None


def sanitize_filename(value: str, fallback: str = "research-report") -> str:
    value = re.sub(r"[\\/:*?\"<>|]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return (value or fallback)[:120]


def slug_data_id(path: Path) -> str:
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem)
    return raw[:96] or "research_report"


def run_json_safe(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - CLI should return structured errors.
        return {"ok": False, "error": str(exc), "type": type(exc).__name__}


def request_json(method: str, url: str, **kwargs) -> dict:
    response = requests.request(method, url, timeout=kwargs.pop("timeout", 60), **kwargs)
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        raise RuntimeError(f"MinerU API error {data.get('code')}: {data.get('msg')}")
    return data


def download_text(url: str) -> str:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def download_zip(url: str, output_dir: Path) -> Path:
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    zip_path = output_dir / "mineru_result.zip"
    zip_path.write_bytes(response.content)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(output_dir / "mineru_zip")
    candidates = list((output_dir / "mineru_zip").rglob("full.md"))
    if not candidates:
        candidates = list((output_dir / "mineru_zip").rglob("*.md"))
    if not candidates:
        raise RuntimeError("MinerU zip did not contain full.md or any Markdown file.")
    return candidates[0]


def poll_standard_batch(batch_id: str, headers: dict[str, str], timeout_s: int, interval_s: int) -> dict:
    deadline = time.time() + timeout_s
    url = f"{STANDARD_API}/extract-results/batch/{batch_id}"
    last_state = "unknown"
    while time.time() < deadline:
        data = request_json("GET", url, headers=headers)
        results = data.get("data", {}).get("extract_result", [])
        if isinstance(results, dict):
            results = [results]
        if results:
            item = results[0]
            last_state = item.get("state", "unknown")
            if last_state == "done":
                return item
            if last_state == "failed":
                raise RuntimeError(f"MinerU standard parse failed: {item.get('err_msg') or item}")
        time.sleep(interval_s)
    raise TimeoutError(f"MinerU standard parse timed out; last state={last_state}, batch_id={batch_id}")


def poll_agent_task(task_id: str, timeout_s: int, interval_s: int) -> dict:
    deadline = time.time() + timeout_s
    url = f"{AGENT_API}/parse/{task_id}"
    last_state = "unknown"
    while time.time() < deadline:
        data = request_json("GET", url)
        item = data.get("data", {})
        last_state = item.get("state", "unknown")
        if last_state == "done":
            return item
        if last_state == "failed":
            raise RuntimeError(f"MinerU agent parse failed: {item.get('err_msg') or item}")
        time.sleep(interval_s)
    raise TimeoutError(f"MinerU agent parse timed out; last state={last_state}, task_id={task_id}")


def convert_with_standard_api(input_path: Path, output_dir: Path, args: argparse.Namespace) -> ConversionResult:
    token = os.environ.get("MINERU_API_TOKEN") or os.environ.get("MINERU_TOKEN")
    if not token:
        raise RuntimeError("MINERU_API_TOKEN is not set.")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "files": [{"name": input_path.name, "data_id": slug_data_id(input_path)}],
        "model_version": args.model_version,
        "enable_table": args.enable_table,
        "enable_formula": args.enable_formula,
        "language": args.language,
    }
    if args.page_range:
        payload["files"][0]["page_ranges"] = args.page_range
    if args.ocr:
        payload["files"][0]["is_ocr"] = True

    created = request_json("POST", f"{STANDARD_API}/file-urls/batch", headers=headers, json=payload)
    batch_id = created["data"]["batch_id"]
    file_urls = created["data"]["file_urls"]
    if not file_urls:
        raise RuntimeError("MinerU standard API did not return upload URL.")

    with input_path.open("rb") as f:
        upload = requests.put(file_urls[0], data=f, timeout=300)
    if upload.status_code not in (200, 201):
        raise RuntimeError(f"MinerU standard upload failed: HTTP {upload.status_code} {upload.text[:200]}")

    item = poll_standard_batch(batch_id, headers, args.timeout, args.interval)
    zip_url = item.get("full_zip_url")
    if not zip_url:
        raise RuntimeError(f"MinerU standard result missing full_zip_url: {item}")
    md_path = download_zip(zip_url, output_dir)
    return ConversionResult(markdown_path=md_path, method="mineru-standard-api", task_id=batch_id, source_url=zip_url)


def convert_with_agent_api(input_path: Path, output_dir: Path, args: argparse.Namespace) -> ConversionResult:
    payload = {
        "file_name": input_path.name,
        "language": args.language,
        "enable_table": args.enable_table,
        "enable_formula": args.enable_formula,
        "is_ocr": args.ocr,
    }
    if args.page_range:
        payload["page_range"] = args.page_range
    created = request_json("POST", f"{AGENT_API}/parse/file", json=payload)
    task_id = created["data"]["task_id"]
    upload_url = created["data"]["file_url"]

    with input_path.open("rb") as f:
        upload = requests.put(upload_url, data=f, timeout=300)
    if upload.status_code not in (200, 201):
        raise RuntimeError(f"MinerU agent upload failed: HTTP {upload.status_code} {upload.text[:200]}")

    item = poll_agent_task(task_id, args.timeout, args.interval)
    markdown_url = item.get("markdown_url")
    if not markdown_url:
        raise RuntimeError(f"MinerU agent result missing markdown_url: {item}")
    markdown = download_text(markdown_url)
    md_path = output_dir / "full.md"
    md_path.write_text(markdown, encoding="utf-8")
    return ConversionResult(markdown_path=md_path, method="mineru-agent-api", task_id=task_id, source_url=markdown_url)


def candidate_cli_paths() -> list[str]:
    values = []
    env_cli = os.environ.get("MINERU_CLI")
    if env_cli:
        values.append(env_cli)
    for name in ("mineru", "magic-pdf"):
        found = shutil.which(name)
        if found:
            values.append(found)
    home = Path.home()
    for extra in (
        home / ".local/bin/mineru",
        home / ".local/bin/magic-pdf",
        home / "miniconda3/bin/mineru",
        home / "miniconda3/bin/magic-pdf",
        home / "anaconda3/bin/mineru",
        home / "anaconda3/bin/magic-pdf",
        Path("/opt/homebrew/bin/mineru"),
        Path("/opt/homebrew/bin/magic-pdf"),
        Path("/usr/local/bin/mineru"),
        Path("/usr/local/bin/magic-pdf"),
    ):
        if extra.exists():
            values.append(str(extra))
    deduped = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def cli_command_variants(exe: str, input_path: Path, output_dir: Path, args: argparse.Namespace) -> list[list[str]]:
    base = Path(exe).name
    variants: list[list[str]] = []
    user_args = os.environ.get("MINERU_CLI_ARGS")
    if user_args:
        variants.append([exe, *user_args.format(input=str(input_path), output=str(output_dir)).split()])
    if "magic-pdf" in base:
        variants.extend([
            [exe, "-p", str(input_path), "-o", str(output_dir), "-m", "auto"],
            [exe, "pdf-command", "--pdf", str(input_path), "--output-dir", str(output_dir), "--method", "auto"],
        ])
    else:
        variants.extend([
            [exe, "-p", str(input_path), "-o", str(output_dir)],
            [exe, "-p", str(input_path), "-o", str(output_dir), "-m", "auto"],
            [exe, "--path", str(input_path), "--output", str(output_dir)],
            [exe, "--input", str(input_path), "--output", str(output_dir)],
        ])
    return variants


def convert_with_cli(input_path: Path, output_dir: Path, args: argparse.Namespace) -> ConversionResult:
    errors = []
    for exe in candidate_cli_paths():
        for cmd in cli_command_variants(exe, input_path, output_dir, args):
            run_dir = output_dir / f"cli_{len(errors)}"
            run_dir.mkdir(parents=True, exist_ok=True)
            command = [cmd[0], *[part if part != str(output_dir) else str(run_dir) for part in cmd[1:]]]
            try:
                completed = subprocess.run(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=args.cli_timeout,
                    check=False,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{' '.join(command)} => {exc}")
                continue
            md_files = sorted(run_dir.rglob("*.md"), key=lambda p: p.stat().st_size, reverse=True)
            if completed.returncode == 0 and md_files:
                return ConversionResult(markdown_path=md_files[0], method=f"mineru-cli:{Path(exe).name}")
            errors.append(
                f"{' '.join(command)} => exit={completed.returncode}; "
                f"stdout={completed.stdout[-300:]}; stderr={completed.stderr[-300:]}"
            )
    raise RuntimeError("MinerU CLI conversion failed or CLI was not found. " + " | ".join(errors[-4:]))


def convert_to_markdown(input_path: Path, output_dir: Path, args: argparse.Namespace) -> ConversionResult:
    if input_path.suffix.lower() == ".md":
        return ConversionResult(markdown_path=input_path, method="existing-markdown")

    if args.method in ("auto", "cli"):
        result = run_json_safe(convert_with_cli, input_path, output_dir, args)
        if isinstance(result, ConversionResult):
            return result
        if args.method == "cli":
            raise RuntimeError(result["error"])

    if args.method in ("auto", "standard-api"):
        result = run_json_safe(convert_with_standard_api, input_path, output_dir, args)
        if isinstance(result, ConversionResult):
            return result
        if args.method == "standard-api":
            raise RuntimeError(result["error"])

    if args.method in ("auto", "agent-api"):
        result = run_json_safe(convert_with_agent_api, input_path, output_dir, args)
        if isinstance(result, ConversionResult):
            return result
        if args.method == "agent-api":
            raise RuntimeError(result["error"])

    raise RuntimeError("All MinerU conversion methods failed. Set MINERU_CLI or MINERU_API_TOKEN, or pass --method.")


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def anonymize_brokers(text: str) -> str:
    for pattern, replacement in BROKER_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"某国际投行['’]S TAKE", "机构观点", text, flags=re.IGNORECASE)
    text = re.sub(r"某研究机构['’]S TAKE", "机构观点", text, flags=re.IGNORECASE)
    return text


def extract_title(markdown: str, source: Path) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title
    for line in markdown.splitlines()[:30]:
        stripped = re.sub(r"[*_`]", "", line).strip()
        if len(stripped) >= 6 and not stripped.startswith("!"):
            return stripped
    return source.stem


def clean_keyword(keyword: str) -> str:
    keyword = keyword.strip(" \t\r\n.,;:，。；：()（）[]【】\"'“”‘’")
    keyword = re.sub(r"\s+", " ", keyword)
    return keyword


def extract_keywords(markdown: str, user_keywords: Iterable[str], limit: int) -> list[str]:
    found: list[str] = []
    semantic_text = re.split(
        r"\n##?\s*(?:Appendix|IMPORTANT DISCLOSURES|Important Disclosures|ANALYST CERTIFICATION|Analyst Certification)\b",
        markdown,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    def add(value: str) -> None:
        value = clean_keyword(value)
        if not value or len(value) > 48:
            return
        if re.search(r"某(国际投行|外资券商|研究机构|卖方机构)|TAKE$", value, re.IGNORECASE):
            return
        if value in {"机构观点", "报告来源"}:
            return
        if re.search(r"\b(CFA|Analyst|AC)\b|@|\+\d", value, re.IGNORECASE):
            return
        if value.lower() in {"buy", "sell", "neutral", "overweight", "underweight", "valuation", "risks"}:
            return
        if value.count("(") != value.count(")"):
            value = re.sub(r"\([^)]*$", "", value).strip()
        value = clean_keyword(value)
        if not value:
            return
        if value.lower() in {item.lower() for item in found}:
            return
        found.append(value)

    for keyword in user_keywords:
        add(keyword)

    for seed in KEYWORD_SEEDS:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(seed)}(?![A-Za-z0-9])", semantic_text, re.IGNORECASE):
            add(seed)

    ticker_patterns = [
        r"\b[A-Z]{1,5}\.(?:US|HK|SZ|SH|TW|TWO|KS|KQ)\b",
        r"\b(?:US|HK|SZ|SH)\.[0-9A-Z]{1,6}\b",
        r"\b[A-Z]{2,5}\s+US\b",
        r"\b[A-Z]{1,5}\.O\b",
    ]
    for pattern in ticker_patterns:
        for match in re.findall(pattern, semantic_text):
            add(match.replace(" ", "."))

    for match in re.findall(r"(?:#|##)\s*([^#\n]{3,80})", semantic_text):
        words = re.split(r"[:：\-–—|/]", match)
        for word in words[:2]:
            if re.search(r"[A-Za-z\u4e00-\u9fff]", word):
                add(word)

    return found[:limit]


def frontmatter(title: str, source: Path, conversion: ConversionResult, keywords: list[str]) -> str:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    escaped_title = title.replace('"', '\\"')
    tag_line = ", ".join(json.dumps(tag, ensure_ascii=False) for tag in keywords[:10])
    return (
        "---\n"
        f'title: "{escaped_title}"\n'
        "type: research-report\n"
        f"source_file: \"{str(source).replace(chr(34), chr(92) + chr(34))}\"\n"
        f"converted_at: {now}\n"
        f"converter: {conversion.method}\n"
        f"mineru_task_id: {conversion.task_id or ''}\n"
        f"tags: [{tag_line}]\n"
        "---\n\n"
    )


def copy_long_image(long_image: str | None, note_path: Path, vault: Path | None, attachment_dir: str) -> str:
    if not long_image:
        return ""
    image_path = Path(long_image).expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Long image not found: {image_path}")

    if vault:
        attachment_root = vault / attachment_dir
        attachment_root.mkdir(parents=True, exist_ok=True)
        dest = attachment_root / sanitize_filename(image_path.name, "research-report-long.png")
        if image_path != dest:
            shutil.copy2(image_path, dest)
        obsidian_path = dest.relative_to(vault).as_posix()
        return f"![[{obsidian_path}]]"

    dest = note_path.with_name(f"{note_path.stem}_long{image_path.suffix or '.png'}")
    if image_path != dest:
        shutil.copy2(image_path, dest)
    return f"![研报长图]({dest.name})"


def compose_note(
    markdown: str,
    title: str,
    source: Path,
    conversion: ConversionResult,
    keywords: list[str],
    image_embed: str,
) -> str:
    parts = [frontmatter(title, source, conversion, keywords)]
    if image_embed:
        parts.append(f"{image_embed}\n\n---\n\n")
    parts.append(add_link_index(markdown, keywords))
    return "".join(parts)


def add_link_index(markdown: str, keywords: list[str]) -> str:
    if not keywords:
        return markdown
    links = " · ".join(f"[[{keyword}]]" for keyword in keywords)
    return f"## 自动链接\n\n{links}\n\n---\n\n{markdown}"


def discover_vault(explicit: str | None) -> Path | None:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env:
        candidates.append(Path(env).expanduser())
    home = Path.home()
    candidates.extend([
        home / "Documents/Obsidian",
        home / "Documents/Obsidian Vault",
        home / "Library/Mobile Documents/iCloud~md~obsidian/Documents",
    ])
    obsidian_config = home / "Library/Application Support/obsidian/obsidian.json"
    if obsidian_config.exists():
        try:
            data = json.loads(obsidian_config.read_text(encoding="utf-8"))
            vaults = data.get("vaults", {})
            sorted_vaults = sorted(
                vaults.values(),
                key=lambda item: (not item.get("open", False), -int(item.get("ts", 0) or 0)),
            )
            for item in sorted_vaults:
                if item.get("path"):
                    candidates.append(Path(item["path"]).expanduser())
        except Exception:
            pass
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def archive_to_obsidian(markdown: str, title: str, source: Path, conversion: ConversionResult, keywords: list[str], args: argparse.Namespace) -> Path:
    vault = discover_vault(args.vault)
    destination_root = Path(args.output_dir).expanduser() if args.output_dir else None
    if vault:
        archive_root = vault / args.archive_dir
    elif destination_root:
        archive_root = destination_root / args.archive_dir
    else:
        archive_root = source.parent / args.archive_dir
    archive_root.mkdir(parents=True, exist_ok=True)

    note_name = sanitize_filename(title, source.stem) + ".md"
    note_path = archive_root / note_name
    image_embed = copy_long_image(args.long_image, note_path, vault, args.attachment_dir)
    body = compose_note(markdown, title, source, conversion, keywords, image_embed)
    note_path.write_text(body, encoding="utf-8")
    return note_path


def open_obsidian(note_path: Path, vault: Path | None, archive_dir: str) -> dict:
    result = {"opened": False, "method": "", "warning": ""}
    try:
        if vault:
            rel = note_path.relative_to(vault).as_posix()
            url = (
                "obsidian://open?"
                + urllib.parse.urlencode({"vault": vault.name, "file": rel}, quote_via=urllib.parse.quote)
            )
            subprocess.run(["open", url], check=True)
            result.update({"opened": True, "method": "obsidian-url"})
        else:
            subprocess.run(["open", "-a", "Obsidian"], check=True)
            result.update({"opened": True, "method": "open-app"})
            result["warning"] = f"Obsidian vault not found; note saved at {note_path}"
    except Exception as exc:  # noqa: BLE001
        result["warning"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a research report with MinerU and archive it to Obsidian.")
    parser.add_argument("input", help="PDF/DOC/PPT/XLS/image file, or an existing Markdown file.")
    parser.add_argument("--method", choices=["auto", "cli", "standard-api", "agent-api"], default="auto")
    parser.add_argument("--vault", help="Obsidian vault path. Defaults to OBSIDIAN_VAULT_PATH when set.")
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE_DIR, help="Folder inside the vault for archived reports.")
    parser.add_argument("--attachment-dir", default=DEFAULT_ATTACHMENT_DIR, help="Folder inside the vault for copied long-image PNGs.")
    parser.add_argument("--long-image", help="Generated long-image PNG to copy into Obsidian and embed at the top of the archived note.")
    parser.add_argument("--output-dir", help="Fallback output root when no Obsidian vault is found.")
    parser.add_argument("--keywords", default="", help="Comma-separated keywords to force as Obsidian links.")
    parser.add_argument("--keyword-limit", type=int, default=DEFAULT_KEYWORD_LIMIT)
    parser.add_argument("--no-anonymize", action="store_true", help="Preserve broker/source names in the archived note.")
    parser.add_argument("--no-open", action="store_true", help="Do not open Obsidian after archiving.")
    parser.add_argument("--language", default="ch")
    parser.add_argument("--model-version", default=os.environ.get("MINERU_MODEL_VERSION", "vlm"))
    parser.add_argument("--page-range", default="")
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--enable-table", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-formula", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("MINERU_TIMEOUT", "900")))
    parser.add_argument("--interval", type=int, default=int(os.environ.get("MINERU_POLL_INTERVAL", "5")))
    parser.add_argument("--cli-timeout", type=int, default=int(os.environ.get("MINERU_CLI_TIMEOUT", "1200")))
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    with tempfile.TemporaryDirectory(prefix="mineru_obsidian_") as temp_dir:
        temp_root = Path(temp_dir)
        conversion = convert_to_markdown(input_path, temp_root, args)
        markdown = read_markdown(conversion.markdown_path)
        if not args.no_anonymize:
            markdown = anonymize_brokers(markdown)
        title = extract_title(markdown, input_path)
        keywords = extract_keywords(markdown, args.keywords.split(",") if args.keywords else [], args.keyword_limit)
        note_path = archive_to_obsidian(markdown, title, input_path, conversion, keywords, args)

    vault = discover_vault(args.vault)
    opened = {"opened": False, "method": "not-attempted", "warning": ""}
    if not args.no_open:
        opened = open_obsidian(note_path, vault, args.archive_dir)

    print(json.dumps({
        "ok": True,
        "input": str(input_path),
        "notePath": str(note_path),
        "method": conversion.method,
        "mineruTaskId": conversion.task_id,
        "keywords": keywords,
        "obsidian": opened,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
