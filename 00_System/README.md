# Leon Content OS Automation

This folder connects the local IP workspace with Feishu Base and Feishu Calendar.

## Codex Maintenance Rule

When Codex changes this Feishu/local automation system, it must update this README in the same turn if the change affects commands, schedules, folder structure, Feishu fields, LaunchAgents, or the user's operating workflow. Every functional update must also add a dated entry to the Version Log with the update time and launched functionality.

Codex should not deeply read or analyze video/audio files by default. For media files, use metadata such as filename, path, size, and timestamps to save tokens unless the user explicitly asks for content-level analysis.

Git is for explicit system backups only. Codex must not create a Git commit unless the user explicitly asks to back up or commit the current version. When a Git backup is created, Codex must add a Version Log entry with the backup time, commit hash, commit message, backup summary, and rollback hint.

## Version Log

### 2026-05-24 20:44 BST - V0.5 Infrastructure Consolidation and Git Backup System

- Moved all local automation scripts into `00_System/scripts/` so system infrastructure lives under `00_System`.
- Organized the SSD media root into `Videos/` and `Assets/`.
- Moved local `02_Assets` to the SSD at `/Volumes/T7 Shield/Leon_IP_Media/Assets`; reusable media assets no longer live in the desktop workspace.
- Updated LaunchAgent templates and install scripts to use the new `00_System/scripts/ipctl.py` path.
- Added automatic retry and hourly watchdog backfill for `process-ideas`, so missed 10:00/19:00 runs can be recovered after network or startup failures.
- Initialized Git for system-layer version control with a whitelist `.gitignore`.
- Git tracks only automation code, system docs, config templates, field maps, LaunchAgents, and directory README files.
- Git ignores Word scripts, video/audio/image assets, SSD content, Feishu cache/logs, local credentials, strategy/private files, and analytics content.
- Git commits are only created when the user explicitly asks for a backup.

### 2026-05-24 20:26 BST - V0.4 Ideas Automation and Table Hygiene

- Added `process-ideas` to clean `Ideas Backlog`, infer missing fields, and promote `Selected` ideas into `Content Pipeline`.
- Automatically fills missing `ID`, `栏目`, and `状态` in `Ideas Backlog`.
- Automatically assigns `Video ID`, `栏目`, `内容等级`, `状态`, and `平台` for promoted Pipeline records.
- Creates matching local video folders and SSD media folders when available.
- Marks promoted Backlog ideas as `Moved` to avoid duplicate promotion.
- Added `clean-empty-rows` and integrated it into `process-ideas`.
- Deleted 5 empty `Content Pipeline` records that pushed V006 to the bottom of the table.
- Installed `com.leon.ip.process-ideas` to run daily at `10:00` and `19:00`, with `RunAtLoad` startup/login catch-up.

### 2026-05-24 20:15 BST - V0.3 SSD Media Sync and Workspace Cleanup

- Added `sync-ssd` to mirror local video folders to `/Volumes/T7 Shield/Leon_IP_Media/Videos`.
- SSD video folders contain only the video folder root, one `Exports/` folder, media files, and `.docx` script backups.
- Local Word scripts remain the source of truth; SSD scripts are backups only.
- Installed `com.leon.ip.sync-ssd` to run automatically when a volume is mounted.
- Cleaned local `.DS_Store`, `__pycache__`, Python bytecode, obsolete Markdown templates, and imported seed CSV files.
- Cleaned SSD AppleDouble `._*` metadata files without touching media files, exports, or script backups.
- Added the rule that Codex should not deeply read/analyze video or audio files unless explicitly asked.

### 2026-05-24 16:30 BST - V0.2 Feishu Base and Calendar Operating Layer

- Consolidated workflow around one Feishu Base: `Leon Content OS`.
- Simplified `Ideas Backlog` to `ID`, `选题`, `栏目`, and `状态`.
- Configured `栏目`, `状态`, `内容等级`, and `复盘状态` as controlled fields.
- Simplified `Content Pipeline` around visible production fields and stopped relying on path/data/calendar ID fields.
- Added school schedule events from screenshots into Feishu Calendar.
- Added `calendar-add` for arbitrary Feishu Calendar events.
- Added `set-publish-date` to update `Content Pipeline.发布日期` and create a Feishu Calendar publish event.

### 2026-05-24 14:50 BST - V0.1 Local Content OS Foundation

- Organized the local IP workspace into system files, video folders, asset folders, analytics, and automation scripts.
- Standardized video folders under `01_Videos/Vxxx_标题/`.
- Set the local script workflow to use Word `.docx` files by default, without generated Brief/Script/Post Copy Markdown files.
- Added `00_System/README.md` as the system operating manual and Version Log.

### Git Backups

#### 2026-05-24 20:44 BST - System Infrastructure V0.5 Backup

- Commit: `a2c2321ba9310d3d8ab8cb2cf97ac5930a33c799`
- Message: `backup: system infrastructure v0.5`
- Summary: Initial system-layer backup after moving infrastructure scripts into `00_System/scripts/`, moving reusable assets to SSD, consolidating Version Log entries, and enforcing Git's system-only whitelist.
- Rollback hint: use `git restore --source a2c2321ba9310d3d8ab8cb2cf97ac5930a33c799 -- .` to restore the tracked system files from this backup.

#### 2026-05-24 20:44 BST - System Infrastructure V0.5.1 Backup

- Commit: `8978e5f4f73a9c8ba378b64060ada1f9a781af9c`
- Message: `backup: system infrastructure v0.5.1`
- Summary: Finalized SSD top-level structure with `/Volumes/T7 Shield/Leon_IP_Media/Videos` and `/Volumes/T7 Shield/Leon_IP_Media/Assets`, updated config templates, Git ignore rules, and operating documentation.
- Rollback hint: use `git restore --source 8978e5f4f73a9c8ba378b64060ada1f9a781af9c -- .` to restore the tracked system files from this backup.

## Current Model

- Feishu Base is the source of truth for ideas, pipeline status, publishing fields, links, and reviews.
- Feishu Calendar is the time layer for creation and publishing blocks.
- Local folders under `/Users/yige/Desktop/IP` store the system files and each video's Word script.
- The SSD at `/Volumes/T7 Shield/Leon_IP_Media` stores video media and reusable assets under separate `Videos/` and `Assets/` folders.
- `00_System/scripts/ipctl.py` is the local controller that Codex can run.

## Git Backup Policy

Git is initialized for system-layer backup only. It is not a content archive.

Tracked by Git:

- `00_System/scripts/ipctl.py`
- `00_System/scripts/install_launchagent_*.sh`
- `00_System/README.md`
- `00_System/config.example.json`
- `00_System/field_map.json`
- `00_System/launchd/*.plist`
- `.gitignore`
- `01_Videos/README.md`

Ignored by Git:

- Video Word scripts and all video project contents under `01_Videos/V*/`.
- Reusable media assets under `/Volumes/T7 Shield/Leon_IP_Media/Assets`.
- SSD content under `/Volumes/T7 Shield/Leon_IP_Media`.
- Local credentials in `00_System/config.local.json`.
- Feishu caches and logs under `00_System/cache/` and `00_System/logs/`.
- Runtime success/failure markers under `00_System/state/`.
- Private strategy/planning files under `00_System/Strategy/`.
- Local analytics/review notes under `02_Analytics/`.

Codex must not create Git commits automatically. A commit is only allowed when the user explicitly asks to back up or commit the current system version. Every Git backup commit must be recorded in the Version Log with its commit hash, message, summary, and rollback hint.

## Daily Operating Workflow

1. Capture rough ideas in ChatGPT or directly in Feishu `Ideas Backlog`.
2. In `Ideas Backlog`, add only the `选题` if you want to stay fast.
3. The automation fills missing `ID`, `栏目`, and `状态`.
4. When an idea is worth making, set its `状态` to `Selected`.
5. At the next automatic check, Codex/Feishu automation creates a `Content Pipeline` item and a local video folder.
6. Write the actual script as a `.docx` file inside the matching `01_Videos/Vxxx_标题/` folder.
7. Use `set-publish-date` when a video gets a publish date; it updates Feishu Base and creates a Feishu Calendar event.
8. Keep video footage and exports on the SSD. The local desktop workspace stays light.

## Feishu Tables

### Ideas Backlog

Minimal idea intake table:

- `ID`: `NO.###`, filled automatically when missing.
- `选题`: the idea title. This is the main field you manually type.
- `栏目`: dropdown, inferred automatically when missing.
- `状态`: dropdown. Empty status becomes `Idea`; set it to `Selected` to promote the idea.

Current column choices:

- `反内耗 / 自我建设`
- `Imperial / Biochemistry / 科研探索`
- `关系 / 社交 / 成年感`
- `Leon / 伦敦情绪地理`

### Content Pipeline

Formal production table:

- `Video ID`: `V###`, assigned automatically when an idea is promoted.
- `标题`: copied from the selected idea.
- `栏目`: copied or inferred from the idea.
- `状态`: starts as `Idea`.
- `内容等级`: inferred as `XS`, `M`, or `S` from the idea content.
- `平台`: copied from the latest pipeline item, falling back to the default platforms in config.
- `发布日期`, links, and review fields are left blank until needed.

Content level meanings:

- `S`: strong point of view or high-priority content.
- `M`: normal mainline content.
- `XS`: light, short, low-production content.

## First-Time Setup

1. In Feishu, create the Base `Leon Content OS`.
2. Create these tables:
   - `Content Pipeline`
   - `Ideas Backlog`
   - `Weekly Plan`
   - `Scripts Library`
   - `Analytics Review`
3. Add fields matching `00_System/field_map.json`.
4. In Feishu Open Platform, create or configure a self-built app.
5. Grant minimum permissions for Base read/write and Calendar read/write.
6. Add the app to the target Base as a document app with edit permission.
7. Paste the Base token into `00_System/config.local.json`.
8. Configure Feishu CLI:

```bash
lark-cli config init
lark-cli auth login --recommend
lark-cli auth status
lark-cli doctor
```

## Commands

All write-capable commands are safe by default. Add `--execute` only when the dry-run looks correct.

```bash
python3 00_System/scripts/ipctl.py doctor
python3 00_System/scripts/ipctl.py pull
python3 00_System/scripts/ipctl.py sync
python3 00_System/scripts/ipctl.py sync --execute
python3 00_System/scripts/ipctl.py clean-empty-rows
python3 00_System/scripts/ipctl.py clean-empty-rows --execute
python3 00_System/scripts/ipctl.py process-ideas
python3 00_System/scripts/ipctl.py process-ideas --execute
python3 00_System/scripts/ipctl.py watchdog
python3 00_System/scripts/ipctl.py watchdog --execute
python3 00_System/scripts/ipctl.py new-from-idea --title "先完成再迭代"
python3 00_System/scripts/ipctl.py new-from-idea --title "先完成再迭代" --execute
python3 00_System/scripts/ipctl.py schedule-week --time-block "2026-05-24T20:00:00+01:00/2026-05-24T22:30:00+01:00"
python3 00_System/scripts/ipctl.py schedule-week --time-block "2026-05-24T20:00:00+01:00/2026-05-24T22:30:00+01:00" --execute
python3 00_System/scripts/ipctl.py update-status
python3 00_System/scripts/ipctl.py update-status --execute
python3 00_System/scripts/ipctl.py review --video-id V001 --platform 小红书 --views 1000 --likes 80 --saves 30 --comments 12
python3 00_System/scripts/ipctl.py review --video-id V001 --platform 小红书 --views 1000 --likes 80 --saves 30 --comments 12 --execute
python3 00_System/scripts/ipctl.py set-publish-date --video-id V001 --date 2026-06-01 --time 18:00
python3 00_System/scripts/ipctl.py set-publish-date --video-id V001 --date 2026-06-01 --time 18:00 --execute
python3 00_System/scripts/ipctl.py calendar-add --title "V001 录制" --time-block "2026-06-01T15:00:00+01:00/2026-06-01T16:00:00+01:00"
python3 00_System/scripts/ipctl.py calendar-add --title "V001 录制" --time-block "2026-06-01T15:00:00+01:00/2026-06-01T16:00:00+01:00" --execute
python3 00_System/scripts/ipctl.py sync-ssd --dry-run
python3 00_System/scripts/ipctl.py sync-ssd
```

## Ideas Backlog Automation

`process-ideas` is the main automatic Feishu workflow.

It does four things:

- Cleans fully empty rows from `Ideas Backlog` and `Content Pipeline`.
- Cleans `Ideas Backlog`: fills missing `ID`, `栏目`, and `状态`.
- Promotes `Selected` ideas into `Content Pipeline`.
- Creates matching local folders and, if the SSD is mounted, matching SSD media folders.

Promotion behavior:

- New pipeline item gets the next `V###`.
- Status starts as `Idea`.
- Content level is inferred as `XS`, `M`, or `S`.
- Platform is copied from the latest pipeline item.
- The source idea is marked `Moved` after successful promotion to avoid duplicates.
- No Brief, Script, or Post Copy Markdown templates are created.

Install the scheduled automation:

```bash
00_System/scripts/install_launchagent_process_ideas.sh
```

After installation, macOS runs `process-ideas --execute` every day at `10:00` and `19:00`. It retries execute-mode failures up to 3 times with a 5-minute delay. `RunAtLoad` is enabled, so if the Mac was off or asleep at a scheduled time, it runs once after login/startup. Logs are written to:

```text
00_System/logs/idea-automation.log
00_System/logs/launchd-process-ideas.out.log
00_System/logs/launchd-process-ideas.err.log
```

Install the watchdog backfill automation:

```bash
00_System/scripts/install_launchagent_watchdog.sh
```

The watchdog runs hourly and checks whether today's `10:00` or `19:00` process window has a successful run in `00_System/state/process_ideas_last_success.json`. If a due window has no success record, it runs `process-ideas --execute` as a safe backfill.

## SSD Sync

The SSD video media root is configured as:

```text
/Volumes/T7 Shield/Leon_IP_Media/Videos
```

Reusable assets live on the SSD:

```text
/Volumes/T7 Shield/Leon_IP_Media/Assets
├── Music/
├── Covers/
└── Reusable_Broll/
```

`sync-ssd` mirrors the local video folder names to the SSD, creates only `Exports/`, and backs up `.docx` scripts to each SSD video folder. It never deletes SSD files.

Install the automatic mount trigger:

```bash
00_System/scripts/install_launchagent_sync_ssd.sh
```

After installation, macOS runs `sync-ssd` whenever a volume is mounted. Logs are written under `00_System/logs/`.

## Calendar Sync

Use `set-publish-date` when a video has a planned publish date:

```bash
python3 00_System/scripts/ipctl.py set-publish-date --video-id V001 --date 2026-06-01 --time 18:00 --execute
```

This updates `Content Pipeline.发布日期`, moves the item to `Scheduled` by default, and creates a Feishu Calendar event.

Use `calendar-add` for one-off creation, recording, editing, or school-related blocks that should appear in Feishu Calendar:

```bash
python3 00_System/scripts/ipctl.py calendar-add --title "V001 录制" --time-block "2026-06-01T15:00:00+01:00/2026-06-01T16:00:00+01:00" --execute
```

## Local Folder Rules

Each local video folder should stay minimal:

```text
01_Videos/V001_短标题/
└── 短标题_script.docx
```

The Word document is the script source of truth. Codex should not create Brief, Script, or Post Copy Markdown files by default.

The SSD folder is also simple:

```text
/Volumes/T7 Shield/Leon_IP_Media/Videos/V001_短标题/
├── 短标题_script.docx
└── Exports/
```

The SSD script copy is only a backup. The local `.docx` remains the source of truth. Automation must never delete SSD files.

## Important

Do not store App Secret in this workspace. Let `lark-cli` keep sensitive credentials in the macOS keychain.
