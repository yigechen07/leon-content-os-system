#!/usr/bin/env python3
"""
Leon Content OS local controller.

Default behavior is safe: commands that would create local content folders or
write to Feishu require --execute. Without --execute they print a dry-run plan.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SYSTEM_DIR = ROOT / "00_System"
CACHE_DIR = SYSTEM_DIR / "cache"
STATE_DIR = SYSTEM_DIR / "state"
CONFIG_PATH = SYSTEM_DIR / "config.local.json"
CONFIG_EXAMPLE_PATH = SYSTEM_DIR / "config.example.json"
FIELD_MAP_PATH = SYSTEM_DIR / "field_map.json"
IDEA_AUTOMATION_LOG = SYSTEM_DIR / "logs" / "idea-automation.log"
LAST_IDEA_SUCCESS_PATH = STATE_DIR / "process_ideas_last_success.json"
LAST_IDEA_FAILURE_PATH = STATE_DIR / "process_ideas_last_failure.json"


TABLE_KEYS = [
    "content_pipeline",
    "ideas_backlog",
    "weekly_plan",
    "scripts_library",
    "analytics_review",
]


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        die(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return load_json(CONFIG_PATH)
    return load_json(CONFIG_EXAMPLE_PATH)


def load_field_map() -> dict[str, Any]:
    return load_json(FIELD_MAP_PATH)


def require_base_token(config: dict[str, Any], table_key: str | None = None) -> str:
    token = ""
    if table_key:
        token = str((config.get("base_tokens") or {}).get(table_key) or "").strip()
    if not token:
        token = str(config.get("base_token") or "").strip()
    if not token or token.startswith("replace_with"):
        die(
            "Missing 00_System/config.local.json base_token. "
            "Paste the Leon Content OS Base token before using Feishu read/write commands."
        )
    return token


def table_id(config: dict[str, Any], key: str) -> str:
    tables = config.get("tables", {})
    value = str(tables.get(key) or "").strip()
    if not value:
        die(f"Missing table mapping for {key} in config.local.json")
    return value


def content_root(config: dict[str, Any] | None = None) -> Path:
    config = config or load_config()
    raw = str(config.get("content_root") or "01_Videos").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def media_root(config: dict[str, Any] | None = None) -> Path:
    config = config or load_config()
    raw = str(config.get("media_root") or "").strip()
    if not raw:
        die("Missing media_root in 00_System/config.local.json")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def media_mount_root(path: Path) -> Path:
    parts = path.parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        return Path(parts[0]) / parts[1] / parts[2]
    return path.parent


def lark_cli_path() -> str | None:
    return shutil.which("lark-cli")


def run_cmd(args: list[str], *, expect_json: bool = True, allow_error: bool = False) -> Any:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        if allow_error:
            return {
                "ok": False,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        message = proc.stderr.strip() or proc.stdout.strip() or f"command failed: {args}"
        die(message)
    out = proc.stdout.strip()
    if not expect_json:
        return out
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


def lark(args: list[str], *, expect_json: bool = True, allow_error: bool = False) -> Any:
    cli = lark_cli_path()
    if not cli:
        die("lark-cli is not installed. Install with: npm install -g @larksuite/cli")
    return run_cmd([cli, *args], expect_json=expect_json, allow_error=allow_error)


def cli_base_args(config: dict[str, Any]) -> list[str]:
    identity = str(config.get("identity") or "user")
    return ["--as", identity]


def list_records(
    config: dict[str, Any],
    table_key: str,
    *,
    limit: int = 200,
    include_empty: bool = False,
) -> list[dict[str, Any]]:
    base_token = require_base_token(config, table_key)
    data = lark(
        [
            "base",
            "+record-list",
            "--base-token",
            base_token,
            "--table-id",
            table_id(config, table_key),
            "--limit",
            str(limit),
            "--format",
            "json",
            *cli_base_args(config),
        ]
    )
    return extract_records(data, include_empty=include_empty)


def upsert_record(
    config: dict[str, Any],
    table_key: str,
    fields: dict[str, Any],
    *,
    record_id: str | None = None,
    execute: bool = False,
) -> Any:
    base_token = require_base_token(config, table_key)
    cmd = [
        "base",
        "+record-upsert",
        "--base-token",
        base_token,
        "--table-id",
        table_id(config, table_key),
        "--json",
        json.dumps(fields, ensure_ascii=False),
        *cli_base_args(config),
    ]
    if record_id:
        cmd.extend(["--record-id", record_id])
    if not execute:
        cmd.append("--dry-run")
        print("[dry-run] lark-cli " + " ".join(cmd))
        return {"dry_run": True, "fields": fields, "record_id": record_id}
    return lark(cmd)


def delete_records(
    config: dict[str, Any],
    table_key: str,
    record_ids: list[str],
    *,
    execute: bool = False,
) -> Any:
    if not record_ids:
        return {"deleted": []}
    base_token = require_base_token(config, table_key)
    cmd = [
        "base",
        "+record-delete",
        "--base-token",
        base_token,
        "--table-id",
        table_id(config, table_key),
        "--json",
        json.dumps({"record_id_list": record_ids}, ensure_ascii=False),
        *cli_base_args(config),
    ]
    if not execute:
        cmd.append("--dry-run")
        print("[dry-run] lark-cli " + " ".join(cmd))
        return {"dry_run": True, "record_ids": record_ids}
    cmd.append("--yes")
    return lark(cmd)


def create_calendar_event(
    config: dict[str, Any],
    *,
    summary: str,
    start: str,
    end: str,
    description: str,
    execute: bool = False,
) -> Any:
    cmd = [
        "calendar",
        "+create",
        "--calendar-id",
        str(config.get("calendar_id") or "primary"),
        "--summary",
        summary,
        "--start",
        start,
        "--end",
        end,
        "--description",
        description,
        "--format",
        "json",
        *cli_base_args(config),
    ]
    if not execute:
        cmd.append("--dry-run")
        print("[dry-run] lark-cli " + " ".join(cmd))
        return {"dry_run": True, "summary": summary, "start": start, "end": end}
    return lark(cmd)


def extract_records(data: Any, *, include_empty: bool = False) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        payload = data.get("data")
        if isinstance(payload, dict):
            fields = payload.get("fields")
            rows = payload.get("data")
            record_ids = payload.get("record_id_list") or []
            if isinstance(fields, list) and isinstance(rows, list):
                records: list[dict[str, Any]] = []
                for idx, row in enumerate(rows):
                    if not isinstance(row, list):
                        continue
                    record = {
                        str(name): row[pos] if pos < len(row) else None
                        for pos, name in enumerate(fields)
                    }
                    if idx < len(record_ids):
                        record["_record_id"] = record_ids[idx]
                    if include_empty or any(
                        value not in (None, "", []) for key, value in record.items() if key != "_record_id"
                    ):
                        records.append(record)
                return records

    found: list[dict[str, Any]] = []

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            if "fields" in obj and isinstance(obj["fields"], dict):
                fields = obj["fields"].copy()
                rid = obj.get("record_id") or obj.get("id")
                if rid:
                    fields["_record_id"] = rid
                found.append(fields)
                return
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    visit(data)
    return found


def cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(filter(None, (cell_to_text(item) for item in value))).strip()
    if isinstance(value, dict):
        for key in ("text", "name", "value", "title", "link"):
            if key in value:
                return cell_to_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def field(record: dict[str, Any], fmap: dict[str, str], key: str, default: str = "") -> str:
    return cell_to_text(record.get(fmap.get(key, key), default)).strip()


def slugify_title(title: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#]+", "", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60] or "未命名选题"


def next_video_id(existing_records: list[dict[str, Any]] | None = None) -> str:
    nums: list[int] = []
    base = content_root()
    if not base.exists():
        base = ROOT
    for path in base.iterdir():
        if path.is_dir():
            match = re.match(r"V(\d{3,})_", path.name)
            if match:
                nums.append(int(match.group(1)))
    if existing_records:
        for record in existing_records:
            text = json.dumps(record, ensure_ascii=False)
            for match in re.finditer(r"\bV(\d{3,})\b", text):
                nums.append(int(match.group(1)))
    return f"V{(max(nums) + 1) if nums else 1:03d}"


def next_idea_id(existing_records: list[dict[str, Any]], idea_map: dict[str, str]) -> str:
    nums: list[int] = []
    for record in existing_records:
        text = field(record, idea_map, "id")
        match = re.search(r"\bNO\.(\d{3,})\b", text, flags=re.IGNORECASE)
        if match:
            nums.append(int(match.group(1)))
    return f"NO.{(max(nums) + 1) if nums else 1:03d}"


def normalize_select(value: str) -> str:
    return value.strip().lower()


def infer_column(title: str) -> str:
    text = title.lower()
    scores = {
        "反内耗 / 自我建设": 0,
        "Imperial / Biochemistry / 科研探索": 0,
        "关系 / 社交 / 成年感": 0,
        "Leon / 伦敦情绪地理": 0,
    }
    keyword_groups = {
        "反内耗 / 自我建设": [
            "内耗", "焦虑", "稳定", "成长", "状态", "交付", "完成", "迭代", "自律",
            "拖延", "上班", "效率", "长期", "努力", "自我", "burnout", "productive",
        ],
        "Imperial / Biochemistry / 科研探索": [
            "imperial", "biochemistry", "科研", "学术", "实验", "教授", "大学", "大一",
            "paper", "论文", "lab", "生化", "生物", "science", "research", "chatgpt",
        ],
        "关系 / 社交 / 成年感": [
            "关系", "社交", "朋友", "孤独", "成年", "室友", "同学", "恋爱", "边界",
            "沟通", "被喜欢", "合群", "人际",
        ],
        "Leon / 伦敦情绪地理": [
            "leon", "伦敦", "london", "城市", "街区", "生活", "情绪", "名字", "身份",
            "来到", "英国", "留学", "一个人",
        ],
    }
    for column, keywords in keyword_groups.items():
        for keyword in keywords:
            if keyword in text:
                scores[column] += 1
    best_column = max(scores, key=scores.get)
    return best_column if scores[best_column] > 0 else "反内耗 / 自我建设"


def infer_content_level(title: str) -> str:
    text = title.lower()
    s_keywords = [
        "为什么", "绝大多数", "不如", "必须", "真相", "我第一次", "不特殊",
        "教授", "chatgpt", "imperial", "学术会议", "关系不会自动发生",
    ]
    xs_keywords = [
        "小事", "日常", "随手", "一句话", "最低配", "短", "清单", "提醒",
        "quick", "note",
    ]
    if any(keyword in text for keyword in s_keywords):
        return "S"
    if any(keyword in text for keyword in xs_keywords) or len(title) <= 12:
        return "XS"
    return "M"


def video_id_number(record: dict[str, Any], pipe_map: dict[str, str]) -> int:
    match = re.search(r"\bV(\d{3,})\b", field(record, pipe_map, "video_id"))
    return int(match.group(1)) if match else 0


def latest_platforms(
    pipeline_records: list[dict[str, Any]],
    pipe_map: dict[str, str],
    config: dict[str, Any],
) -> list[str]:
    latest = max(pipeline_records, key=lambda record: video_id_number(record, pipe_map), default=None)
    if latest:
        raw = latest.get(pipe_map["platforms"])
        if isinstance(raw, list):
            platforms = [cell_to_text(item).strip() for item in raw if cell_to_text(item).strip()]
            if platforms:
                return platforms
        text = field(latest, pipe_map, "platforms")
        if text:
            return [part.strip() for part in re.split(r"[,，/、\s]+", text) if part.strip()]
    return list(config.get("default_platforms", []))


def is_empty_record(record: dict[str, Any]) -> bool:
    return all(
        cell_to_text(value).strip() == ""
        for key, value in record.items()
        if key != "_record_id"
    )


def cleanup_empty_rows(
    config: dict[str, Any],
    table_key: str,
    *,
    limit: int = 200,
    execute: bool = False,
) -> dict[str, Any]:
    records = list_records(config, table_key, limit=limit, include_empty=True)
    empty_ids = [
        str(record.get("_record_id") or "").strip()
        for record in records
        if is_empty_record(record) and str(record.get("_record_id") or "").strip()
    ]
    result: dict[str, Any] = {
        "table": table_key,
        "records_checked": len(records),
        "empty_record_ids": empty_ids,
    }
    if empty_ids:
        result["delete_result"] = delete_records(config, table_key, empty_ids, execute=execute)
    return result


def ensure_ssd_video_folder(config: dict[str, Any], folder_name: str, *, execute: bool) -> dict[str, Any]:
    dst_root = media_root(config)
    mount_root = media_mount_root(dst_root)
    result: dict[str, Any] = {
        "media_root": str(dst_root),
        "mounted": mount_root.exists(),
        "created_dirs": [],
        "skipped": [],
    }
    if not mount_root.exists():
        result["skipped"].append("media_root not mounted")
        return result

    target_folder = dst_root / folder_name
    exports_folder = target_folder / "Exports"
    for folder in (target_folder, exports_folder):
        if not folder.exists():
            result["created_dirs"].append(str(folder))
            if execute:
                folder.mkdir(parents=True, exist_ok=True)
    return result


def content_paths(video_id: str, title: str) -> tuple[Path, dict[str, Path]]:
    folder = content_root() / f"{video_id}_{slugify_title(title)}"
    return folder, {
        "script": folder / f"{slugify_title(title)}_script.docx",
        "analytics": folder / "analytics.md",
    }


def existing_content_folder(video_id: str, title: str) -> Path:
    base = content_root()
    if video_id and base.exists():
        matches = sorted(path for path in base.iterdir() if path.is_dir() and path.name.startswith(f"{video_id}_"))
        if matches:
            return matches[0]
    return content_paths(video_id, title)[0]


def find_script_docx(folder: Path) -> Path | None:
    matches = sorted(folder.glob("*.docx"))
    return matches[0] if matches else None


def ensure_content_folder(
    *,
    video_id: str,
    title: str,
    column: str = "",
    content_level: str = "M",
    platforms: str = "小红书, 抖音, 视频号",
    core_point: str = "",
    trigger_experience: str = "",
    hook: str = "",
    execute: bool = False,
) -> tuple[Path, dict[str, Path]]:
    folder, paths = content_paths(video_id, title)
    if not execute:
        print(f"[dry-run] create folder {folder}")
        print("[dry-run] no script files will be created; add the Word script manually")
        return folder, paths

    folder.mkdir(parents=True, exist_ok=True)
    return folder, paths


def cache_records(table_key: str, records: list[dict[str, Any]]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{table_key}.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_cached_records(table_key: str) -> list[dict[str, Any]]:
    path = CACHE_DIR / f"{table_key}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time_block(text: str) -> tuple[str, str] | None:
    text = text.strip()
    if not text:
        return None
    if "/" in text:
        start, end = [part.strip() for part in text.split("/", 1)]
        return start, end
    match = re.search(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2})?)\s*[-~]\s*"
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2})?)",
        text,
    )
    if match:
        return match.group(1), match.group(2)
    return None


def summarize_cli_result(result: Any) -> str:
    text = json.dumps(result, ensure_ascii=False)
    for key in ("event_id", "record_id", "id"):
        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
    return ""


def parse_date_time(date_text: str, time_text: str, config: dict[str, Any]) -> dt.datetime:
    date_part = dt.date.fromisoformat(date_text)
    hour, minute = [int(part) for part in time_text.split(":", 1)]
    tz = dt.timezone(dt.timedelta(hours=1 if config.get("timezone") == "Europe/London" else 0))
    return dt.datetime.combine(date_part, dt.time(hour, minute), tzinfo=tz)


def datetime_to_feishu_date_ms(value: dt.datetime) -> int:
    local_midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(local_midnight.timestamp() * 1000)


def find_pipeline_record(
    records: list[dict[str, Any]],
    fmap: dict[str, str],
    *,
    video_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any] | None:
    for record in records:
        if video_id and field(record, fmap, "video_id") == video_id:
            return record
        if title and title in field(record, fmap, "title"):
            return record
    return None


def cmd_doctor(_: argparse.Namespace) -> None:
    config = load_config()
    print("Leon Content OS doctor")
    print(f"- Workspace: {ROOT}")
    print(f"- Config: {CONFIG_PATH} ({'exists' if CONFIG_PATH.exists() else 'missing'})")
    print(f"- Field map: {FIELD_MAP_PATH} ({'exists' if FIELD_MAP_PATH.exists() else 'missing'})")
    print(f"- lark-cli: {lark_cli_path() or 'missing'}")
    print(f"- base_token configured: {bool(str(config.get('base_token') or '').strip())}")
    print(f"- calendar_id: {config.get('calendar_id') or 'primary'}")
    print("- lark-cli auth status:")
    status = lark(["auth", "status"], allow_error=True)
    print_json(status)
    if str(config.get("base_token") or "").strip():
        print("- Base access check:")
        check = lark(
            [
                "base",
                "+table-list",
                "--base-token",
                str(config["base_token"]),
                *cli_base_args(config),
            ],
            allow_error=True,
        )
        print_json(check)


def cmd_pull(args: argparse.Namespace) -> None:
    config = load_config()
    keys = args.table or TABLE_KEYS
    for key in keys:
        records = list_records(config, key, limit=args.limit)
        path = cache_records(key, records)
        print(f"Pulled {len(records)} records from {key} -> {path}")


def cmd_sync(args: argparse.Namespace) -> None:
    config = load_config()
    fmap = load_field_map()["content_pipeline"]
    records = list_records(config, "content_pipeline", limit=args.limit)
    if not records:
        print("No Content Pipeline records found.")
        return

    for record in records:
        title = field(record, fmap, "title")
        if not title:
            continue
        video_id = field(record, fmap, "video_id") or next_video_id(records)
        folder = existing_content_folder(video_id, title)
        if folder.exists():
            continue
        column = field(record, fmap, "column")
        content_level = field(record, fmap, "content_level") or config.get("default_content_level", "M")
        platforms = field(record, fmap, "platforms") or ", ".join(config.get("default_platforms", []))
        folder, paths = ensure_content_folder(
            video_id=video_id,
            title=title,
            column=column,
            content_level=content_level,
            platforms=platforms,
            execute=args.execute,
        )
        update = {
            fmap["video_id"]: video_id,
            fmap["status"]: field(record, fmap, "status") or "Idea",
        }
        upsert_record(
            config,
            "content_pipeline",
            update,
            record_id=field(record, fmap, "record_id"),
            execute=args.execute,
        )


def cmd_new_from_idea(args: argparse.Namespace) -> None:
    config = load_config()
    maps = load_field_map()
    idea_map = maps["ideas_backlog"]
    pipe_map = maps["content_pipeline"]
    ideas = list_records(config, "ideas_backlog", limit=args.limit)
    selected = None
    for idea in ideas:
        idea_title = field(idea, idea_map, "idea")
        status = field(idea, idea_map, "status").lower()
        if args.title and args.title not in idea_title:
            continue
        if args.record_id and args.record_id != field(idea, idea_map, "record_id"):
            continue
        if not args.title and not args.record_id and status not in ("", "idea"):
            continue
        selected = idea
        break
    if not selected:
        die("No matching idea found. Use --title or --record-id, or pull/check Ideas Backlog.")

    existing_pipeline = load_cached_records("content_pipeline")
    title = field(selected, idea_map, "idea")
    video_id = args.video_id or next_video_id(existing_pipeline)
    column = field(selected, idea_map, "column")
    platforms = ", ".join(config.get("default_platforms", []))
    folder, paths = ensure_content_folder(
        video_id=video_id,
        title=title,
        column=column,
        content_level=config.get("default_content_level", "M"),
        platforms=platforms,
        execute=args.execute,
    )
    pipeline_fields = {
        pipe_map["video_id"]: video_id,
        pipe_map["title"]: title,
        pipe_map["column"]: column,
        pipe_map["status"]: "Idea",
        pipe_map["content_level"]: config.get("default_content_level", "M"),
        pipe_map["platforms"]: config.get("default_platforms", []),
    }
    upsert_record(config, "content_pipeline", pipeline_fields, execute=args.execute)
    idea_update = {idea_map["status"]: "Moved"}
    upsert_record(
        config,
        "ideas_backlog",
        idea_update,
        record_id=field(selected, idea_map, "record_id"),
        execute=args.execute,
    )


def append_idea_log(summary: dict[str, Any]) -> None:
    IDEA_AUTOMATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with IDEA_AUTOMATION_LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n[{stamp}] process-ideas\n")
        f.write(json.dumps(summary, ensure_ascii=False, indent=2))
        f.write("\n")


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def record_process_ideas_success(summary: dict[str, Any]) -> None:
    write_json_file(
        LAST_IDEA_SUCCESS_PATH,
        {
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
        },
    )


def record_process_ideas_failure(error: str, *, attempt: int, max_attempts: int) -> None:
    data = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "error": error,
    }
    write_json_file(LAST_IDEA_FAILURE_PATH, data)
    append_idea_log({"execute": True, "failed": True, **data})


def process_ideas_once(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()
    maps = load_field_map()
    idea_map = maps["ideas_backlog"]
    pipe_map = maps["content_pipeline"]
    empty_row_cleanup = [
        cleanup_empty_rows(config, "ideas_backlog", limit=args.limit, execute=args.execute),
        cleanup_empty_rows(config, "content_pipeline", limit=args.limit, execute=args.execute),
    ]
    ideas = list_records(config, "ideas_backlog", limit=args.limit)
    pipeline = list_records(config, "content_pipeline", limit=args.limit)

    summary: dict[str, Any] = {
        "execute": args.execute,
        "empty_row_cleanup": empty_row_cleanup,
        "ideas_checked": len(ideas),
        "pipeline_checked": len(pipeline),
        "idea_updates": [],
        "promoted": [],
        "skipped": [],
    }

    used_idea_ids = {field(record, idea_map, "id") for record in ideas if field(record, idea_map, "id")}
    existing_titles = {field(record, pipe_map, "title") for record in pipeline if field(record, pipe_map, "title")}
    next_id_number = 1
    for idea_id in used_idea_ids:
        match = re.search(r"\bNO\.(\d{3,})\b", idea_id, flags=re.IGNORECASE)
        if match:
            next_id_number = max(next_id_number, int(match.group(1)) + 1)

    for idea in ideas:
        record_id = field(idea, idea_map, "record_id")
        title = field(idea, idea_map, "idea")
        if not title:
            summary["skipped"].append({"record_id": record_id, "reason": "empty idea title"})
            continue

        idea_update: dict[str, Any] = {}
        idea_id = field(idea, idea_map, "id")
        if not idea_id:
            while f"NO.{next_id_number:03d}" in used_idea_ids:
                next_id_number += 1
            idea_id = f"NO.{next_id_number:03d}"
            used_idea_ids.add(idea_id)
            next_id_number += 1
            idea_update[idea_map["id"]] = idea_id

        column = field(idea, idea_map, "column")
        if not column:
            column = infer_column(title)
            idea_update[idea_map["column"]] = column

        status = field(idea, idea_map, "status")
        if not status:
            status = "Idea"
            idea_update[idea_map["status"]] = status

        if idea_update:
            summary["idea_updates"].append({
                "record_id": record_id,
                "title": title,
                "fields": idea_update,
            })
            upsert_record(
                config,
                "ideas_backlog",
                idea_update,
                record_id=record_id,
                execute=args.execute,
            )

        if normalize_select(status) != "selected":
            continue

        if title in existing_titles:
            moved_update = {idea_map["status"]: "Moved"}
            summary["skipped"].append({
                "record_id": record_id,
                "title": title,
                "reason": "title already exists in Content Pipeline; marking idea as Moved",
            })
            upsert_record(
                config,
                "ideas_backlog",
                moved_update,
                record_id=record_id,
                execute=args.execute,
            )
            continue

        video_id = next_video_id(pipeline)
        content_level = infer_content_level(title)
        platforms = latest_platforms(pipeline, pipe_map, config)
        folder, _ = ensure_content_folder(
            video_id=video_id,
            title=title,
            column=column,
            content_level=content_level,
            platforms=", ".join(platforms),
            execute=args.execute,
        )
        ssd_result = ensure_ssd_video_folder(config, folder.name, execute=args.execute)

        pipeline_fields = {
            pipe_map["video_id"]: video_id,
            pipe_map["title"]: title,
            pipe_map["column"]: column,
            pipe_map["status"]: "Idea",
            pipe_map["content_level"]: content_level,
            pipe_map["platforms"]: platforms,
        }
        upsert_record(config, "content_pipeline", pipeline_fields, execute=args.execute)
        upsert_record(
            config,
            "ideas_backlog",
            {idea_map["status"]: "Moved"},
            record_id=record_id,
            execute=args.execute,
        )

        promoted = {
            "idea_record_id": record_id,
            "idea_id": idea_id,
            "video_id": video_id,
            "title": title,
            "column": column,
            "content_level": content_level,
            "platforms": platforms,
            "local_folder": str(folder),
            "ssd": ssd_result,
        }
        summary["promoted"].append(promoted)
        pipeline.append({**pipeline_fields, "_record_id": ""})
        existing_titles.add(title)

    if args.execute:
        append_idea_log(summary)
        record_process_ideas_success(summary)
    return summary


def run_process_ideas_with_retries(args: argparse.Namespace) -> dict[str, Any]:
    max_attempts = (args.retries + 1) if args.execute else 1
    for attempt in range(1, max_attempts + 1):
        try:
            summary = process_ideas_once(args)
            if args.execute:
                summary["attempt"] = attempt
                summary["max_attempts"] = max_attempts
            return summary
        except SystemExit as exc:
            error = f"process-ideas failed with exit code {exc.code}"
            if args.execute:
                record_process_ideas_failure(error, attempt=attempt, max_attempts=max_attempts)
            if attempt >= max_attempts:
                raise
            print(f"{error}; retrying in {args.retry_delay} seconds...", file=sys.stderr)
            time.sleep(args.retry_delay)
        except Exception as exc:
            error = f"process-ideas failed: {exc}"
            if args.execute:
                record_process_ideas_failure(error, attempt=attempt, max_attempts=max_attempts)
            if attempt >= max_attempts:
                die(error)
            print(f"{error}; retrying in {args.retry_delay} seconds...", file=sys.stderr)
            time.sleep(args.retry_delay)
    die("process-ideas failed")


def cmd_process_ideas(args: argparse.Namespace) -> None:
    print_json(run_process_ideas_with_retries(args))


def today_local() -> dt.date:
    return dt.datetime.now().date()


def parse_success_timestamp() -> dt.datetime | None:
    data = read_json_file(LAST_IDEA_SUCCESS_PATH)
    timestamp = str(data.get("timestamp") or "")
    if not timestamp:
        return None
    try:
        return dt.datetime.fromisoformat(timestamp)
    except ValueError:
        return None


def missed_process_ideas_windows(now: dt.datetime) -> list[str]:
    last_success = parse_success_timestamp()
    windows = [
        ("10:00", now.replace(hour=10, minute=0, second=0, microsecond=0)),
        ("19:00", now.replace(hour=19, minute=0, second=0, microsecond=0)),
    ]
    missed: list[str] = []
    for label, window_start in windows:
        if now < window_start:
            continue
        if not last_success or last_success < window_start:
            missed.append(label)
    return missed


def cmd_watchdog(args: argparse.Namespace) -> None:
    now = dt.datetime.now()
    missed = missed_process_ideas_windows(now)
    summary: dict[str, Any] = {
        "execute": args.execute,
        "checked_at": now.isoformat(timespec="seconds"),
        "last_success": read_json_file(LAST_IDEA_SUCCESS_PATH),
        "missed_windows": missed,
        "action": "none",
    }
    if missed:
        summary["action"] = "process-ideas"
        if args.execute:
            process_args = argparse.Namespace(
                limit=args.limit,
                execute=True,
                retries=args.retries,
                retry_delay=args.retry_delay,
            )
            summary["process_ideas_result"] = run_process_ideas_with_retries(process_args)
        else:
            summary["dry_run_note"] = "Would run process-ideas --execute."
    print_json(summary)


def cmd_clean_empty_rows(args: argparse.Namespace) -> None:
    config = load_config()
    tables = args.table or ["ideas_backlog", "content_pipeline"]
    summary = {
        "execute": args.execute,
        "tables": [
            cleanup_empty_rows(config, table_key, limit=args.limit, execute=args.execute)
            for table_key in tables
        ],
    }
    print_json(summary)


def cmd_schedule_week(args: argparse.Namespace) -> None:
    config = load_config()
    maps = load_field_map()
    weekly_map = maps["weekly_plan"]
    pipe_map = maps["content_pipeline"]
    weekly = list_records(config, "weekly_plan", limit=args.limit)
    if not weekly:
        die("No Weekly Plan records found.")
    chosen = weekly[0]
    if args.week:
        chosen = next((r for r in weekly if args.week in field(r, weekly_map, "week")), None)
        if not chosen:
            die(f"No Weekly Plan record matched week: {args.week}")

    block = parse_time_block(args.time_block or field(chosen, weekly_map, "creation_block"))
    if not block:
        die(
            "Missing or invalid time block. Use --time-block "
            "'2026-05-24T20:00:00+01:00/2026-05-24T22:30:00+01:00'."
        )
    start, end = block
    summary = args.summary or f"Leon Content OS 创作时间 - {field(chosen, weekly_map, 'week') or '本周'}"
    content_1 = field(chosen, weekly_map, "content_1")
    content_2 = field(chosen, weekly_map, "content_2")
    description = f"Content 1: {content_1}\nContent 2: {content_2}\nCreated by ipctl.py"
    result = create_calendar_event(
        config,
        summary=summary,
        start=start,
        end=end,
        description=description,
        execute=args.execute,
    )
    event_id = summarize_cli_result(result)
    if event_id:
        for title in (content_1, content_2):
            if not title:
                continue
            records = list_records(config, "content_pipeline", limit=200)
            match = next((r for r in records if title in field(r, pipe_map, "title")), None)
            if match:
                upsert_record(
                    config,
                    "content_pipeline",
                    {pipe_map["status"]: "Scheduled"},
                    record_id=field(match, pipe_map, "record_id"),
                    execute=args.execute,
                )


def cmd_update_status(args: argparse.Namespace) -> None:
    config = load_config()
    fmap = load_field_map()["content_pipeline"]
    records = list_records(config, "content_pipeline", limit=args.limit)
    for record in records:
        video_id = field(record, fmap, "video_id")
        title = field(record, fmap, "title")
        if not video_id or not title:
            continue
        folder = existing_content_folder(video_id, title)
        if not folder.exists():
            continue
        current = field(record, fmap, "status") or "Idea"
        new_status = current
        script_docx = find_script_docx(folder)
        if (folder / "analytics.md").exists() and current == "Posted":
            new_status = "Reviewed"
        elif script_docx and current in ("Idea", "Brief"):
            new_status = "Script"
        if new_status != current:
            fields = {fmap["status"]: new_status}
            upsert_record(
                config,
                "content_pipeline",
                fields,
                record_id=field(record, fmap, "record_id"),
                execute=args.execute,
            )
            print(f"{field(record, fmap, 'title')}: {current} -> {new_status}")


def cmd_review(args: argparse.Namespace) -> None:
    config = load_config()
    maps = load_field_map()
    pipe_map = maps["content_pipeline"]
    analytics_map = maps["analytics_review"]
    records = list_records(config, "content_pipeline", limit=args.limit)
    record = None
    for item in records:
        if args.video_id and args.video_id == field(item, pipe_map, "video_id"):
            record = item
            break
        if args.title and args.title in field(item, pipe_map, "title"):
            record = item
            break
    if not record:
        die("No matching Content Pipeline record. Use --video-id or --title.")

    folder = existing_content_folder(field(record, pipe_map, "video_id"), field(record, pipe_map, "title"))
    analytics_file = folder / "analytics.md"
    notes = analytics_file.read_text(encoding="utf-8") if analytics_file.exists() else ""
    fields = {
        analytics_map["video_id"]: field(record, pipe_map, "video_id"),
        analytics_map["platform"]: args.platform,
        analytics_map["views"]: args.views or 0,
        analytics_map["likes"]: args.likes or 0,
        analytics_map["saves"]: args.saves or 0,
        analytics_map["comments"]: args.comments or 0,
        analytics_map["performance"]: args.performance or "待判断",
        analytics_map["reuse_points"]: args.reuse_points or "",
        analytics_map["next_optimization"]: args.next_optimization or notes[:900],
    }
    upsert_record(config, "analytics_review", fields, execute=args.execute)
    upsert_record(
        config,
        "content_pipeline",
        {pipe_map["status"]: "Reviewed", pipe_map["review_status"]: "Reviewed"},
        record_id=field(record, pipe_map, "record_id"),
        execute=args.execute,
    )


def cmd_set_publish_date(args: argparse.Namespace) -> None:
    config = load_config()
    fmap = load_field_map()["content_pipeline"]
    records = list_records(config, "content_pipeline", limit=args.limit)
    record = find_pipeline_record(records, fmap, video_id=args.video_id, title=args.title)
    if not record:
        die("No matching Content Pipeline record. Use --video-id or --title.")

    title = field(record, fmap, "title")
    video_id = field(record, fmap, "video_id")
    start_dt = parse_date_time(args.date, args.time, config)
    end_dt = start_dt + dt.timedelta(minutes=args.duration)
    publish_field = fmap.get("publish_date")
    if not publish_field:
        die("Missing publish_date mapping in field_map.json")

    update = {
        publish_field: datetime_to_feishu_date_ms(start_dt),
        fmap["status"]: args.status,
    }
    if "review_status" in fmap and args.review_status:
        update[fmap["review_status"]] = args.review_status

    upsert_record(
        config,
        "content_pipeline",
        update,
        record_id=field(record, fmap, "record_id"),
        execute=args.execute,
    )
    create_calendar_event(
        config,
        summary=args.summary or f"发布：{title}",
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        description=args.description or f"{video_id} {title}\nSource: Leon Content OS",
        execute=args.execute,
    )


def cmd_calendar_add(args: argparse.Namespace) -> None:
    config = load_config()
    if "/" in args.time_block:
        start, end = parse_time_block(args.time_block) or (None, None)
        if not start or not end:
            die("Invalid --time-block. Use ISO_START/ISO_END.")
    else:
        die("Invalid --time-block. Use ISO_START/ISO_END, e.g. 2026-06-01T18:00:00+01:00/2026-06-01T19:00:00+01:00")
    create_calendar_event(
        config,
        summary=args.title,
        start=start,
        end=end,
        description=args.description or "Source: Leon Content OS",
        execute=args.execute,
    )


def iter_video_folders(config: dict[str, Any]) -> list[Path]:
    base = content_root(config)
    if not base.exists():
        die(f"Content root does not exist: {base}")
    return sorted(
        path for path in base.iterdir()
        if path.is_dir() and re.match(r"V\d{3,}_", path.name)
    )


def sync_ssd(config: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    src_root = content_root(config)
    dst_root = media_root(config)
    mount_root = media_mount_root(dst_root)
    summary: dict[str, Any] = {
        "content_root": str(src_root),
        "media_root": str(dst_root),
        "mounted": mount_root.exists(),
        "created_dirs": [],
        "copied_scripts": [],
        "skipped": [],
    }
    if not mount_root.exists():
        print(f"media_root not mounted: {dst_root}")
        return summary

    video_folders = iter_video_folders(config)
    if not dry_run:
        dst_root.mkdir(parents=True, exist_ok=True)

    for source_folder in video_folders:
        target_folder = dst_root / source_folder.name
        exports_folder = target_folder / "Exports"
        for folder in (target_folder, exports_folder):
            if not folder.exists():
                summary["created_dirs"].append(str(folder))
                if dry_run:
                    print(f"[dry-run] create folder {folder}")
                else:
                    folder.mkdir(parents=True, exist_ok=True)

        scripts = sorted(source_folder.glob("*.docx"))
        if not scripts:
            summary["skipped"].append({
                "video_folder": str(source_folder),
                "reason": "no docx script found",
            })
            continue
        for script in scripts:
            target_script = target_folder / script.name
            action = "copy"
            if target_script.exists():
                try:
                    same = (
                        target_script.stat().st_size == script.stat().st_size
                        and int(target_script.stat().st_mtime) >= int(script.stat().st_mtime)
                    )
                except FileNotFoundError:
                    same = False
                action = "skip-current" if same else "overwrite"
            summary["copied_scripts"].append({
                "source": str(script),
                "target": str(target_script),
                "action": action,
            })
            if dry_run:
                print(f"[dry-run] {action} {script} -> {target_script}")
            elif action != "skip-current":
                shutil.copy2(script, target_script)
    return summary


def append_sync_log(summary: dict[str, Any]) -> None:
    log_dir = SYSTEM_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "sync-ssd.log"
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n[{stamp}] sync-ssd\n")
        f.write(json.dumps(summary, ensure_ascii=False, indent=2))
        f.write("\n")


def cmd_sync_ssd(args: argparse.Namespace) -> None:
    config = load_config()
    summary = sync_ssd(config, dry_run=args.dry_run)
    if not args.dry_run:
        append_sync_log(summary)
    print_json(summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Leon Content OS controller")
    sub = parser.add_subparsers(required=True)

    doctor = sub.add_parser("doctor", help="Check local setup and lark-cli status")
    doctor.set_defaults(func=cmd_doctor)

    pull = sub.add_parser("pull", help="Pull Feishu Base records into local cache")
    pull.add_argument("--table", choices=TABLE_KEYS, action="append")
    pull.add_argument("--limit", type=int, default=200)
    pull.set_defaults(func=cmd_pull)

    sync = sub.add_parser("sync", help="Create local folders/templates for Pipeline records")
    sync.add_argument("--limit", type=int, default=200)
    sync.add_argument("--execute", action="store_true", help="Actually create files and update Feishu")
    sync.set_defaults(func=cmd_sync)

    new_idea = sub.add_parser("new-from-idea", help="Promote one Ideas Backlog record into Pipeline")
    new_idea.add_argument("--title")
    new_idea.add_argument("--record-id")
    new_idea.add_argument("--video-id")
    new_idea.add_argument("--limit", type=int, default=200)
    new_idea.add_argument("--execute", action="store_true", help="Actually create files and update Feishu")
    new_idea.set_defaults(func=cmd_new_from_idea)

    process = sub.add_parser("process-ideas", help="Auto-clean Ideas Backlog and promote Selected ideas")
    process.add_argument("--limit", type=int, default=200)
    process.add_argument("--execute", action="store_true", help="Actually update Feishu and create folders")
    process.add_argument("--retries", type=int, default=3, help="Retry count for execute mode failures")
    process.add_argument("--retry-delay", type=int, default=300, help="Seconds to wait between retries")
    process.set_defaults(func=cmd_process_ideas)

    watchdog = sub.add_parser("watchdog", help="Backfill missed Ideas automation windows")
    watchdog.add_argument("--limit", type=int, default=200)
    watchdog.add_argument("--execute", action="store_true", help="Actually backfill by running process-ideas")
    watchdog.add_argument("--retries", type=int, default=3, help="Retry count for backfill failures")
    watchdog.add_argument("--retry-delay", type=int, default=300, help="Seconds to wait between retries")
    watchdog.set_defaults(func=cmd_watchdog)

    clean_rows = sub.add_parser("clean-empty-rows", help="Delete fully empty Feishu Base records")
    clean_rows.add_argument("--table", choices=["ideas_backlog", "content_pipeline"], action="append")
    clean_rows.add_argument("--limit", type=int, default=200)
    clean_rows.add_argument("--execute", action="store_true", help="Actually delete empty records")
    clean_rows.set_defaults(func=cmd_clean_empty_rows)

    schedule = sub.add_parser("schedule-week", help="Create a Feishu Calendar content block")
    schedule.add_argument("--week")
    schedule.add_argument("--time-block")
    schedule.add_argument("--summary")
    schedule.add_argument("--limit", type=int, default=50)
    schedule.add_argument("--execute", action="store_true", help="Actually create calendar event and update Feishu")
    schedule.set_defaults(func=cmd_schedule_week)

    status = sub.add_parser("update-status", help="Advance Pipeline status from local file presence")
    status.add_argument("--limit", type=int, default=200)
    status.add_argument("--execute", action="store_true", help="Actually update Feishu")
    status.set_defaults(func=cmd_update_status)

    review = sub.add_parser("review", help="Write analytics review back to Feishu")
    review.add_argument("--video-id")
    review.add_argument("--title")
    review.add_argument("--platform", default="小红书")
    review.add_argument("--views", type=int)
    review.add_argument("--likes", type=int)
    review.add_argument("--saves", type=int)
    review.add_argument("--comments", type=int)
    review.add_argument("--performance")
    review.add_argument("--reuse-points")
    review.add_argument("--next-optimization")
    review.add_argument("--limit", type=int, default=200)
    review.add_argument("--execute", action="store_true", help="Actually update Feishu")
    review.set_defaults(func=cmd_review)

    publish = sub.add_parser("set-publish-date", help="Set a video publish date and create a Calendar event")
    publish.add_argument("--video-id")
    publish.add_argument("--title")
    publish.add_argument("--date", required=True, help="Publish date, YYYY-MM-DD")
    publish.add_argument("--time", default="18:00", help="Calendar event start time, HH:MM")
    publish.add_argument("--duration", type=int, default=30, help="Calendar event duration in minutes")
    publish.add_argument("--summary", help="Calendar event title; defaults to 发布：<title>")
    publish.add_argument("--description")
    publish.add_argument("--status", default="Scheduled")
    publish.add_argument("--review-status", default="Not Reviewed")
    publish.add_argument("--limit", type=int, default=200)
    publish.add_argument("--execute", action="store_true", help="Actually update Feishu and create Calendar event")
    publish.set_defaults(func=cmd_set_publish_date)

    cal = sub.add_parser("calendar-add", help="Create an arbitrary Feishu Calendar event")
    cal.add_argument("--title", required=True)
    cal.add_argument("--time-block", required=True, help="ISO_START/ISO_END")
    cal.add_argument("--description")
    cal.add_argument("--execute", action="store_true", help="Actually create the Calendar event")
    cal.set_defaults(func=cmd_calendar_add)

    sync_ssd_parser = sub.add_parser("sync-ssd", help="Sync local Word scripts to the SSD media library")
    sync_ssd_parser.add_argument("--dry-run", action="store_true", help="Preview folder creation and script backup")
    sync_ssd_parser.set_defaults(func=cmd_sync_ssd)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
