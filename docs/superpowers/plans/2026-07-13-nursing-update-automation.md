# Nursing Update Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `nursing-coursetw-lin` update cloud-safe sources automatically, update `jct/tnpa` from the Mac, remind Lin to save `twna`, detect stale local/manual data, and provide a one-click fallback without duplicate same-day requests.

**Architecture:** Add an execution mode to each source so GitHub runs only cloud-safe sources while the existing local updater owns `jct/tnpa`. Keep `twna` strictly manual, add explicit freshness metadata and a macOS reminder, and add a GitHub-side offline watchdog. Reuse the existing update pipeline for both launchd and the Finder/Dock entry point.

**Tech Stack:** Python 3.10+, pytest, BeautifulSoup, GitHub Actions, macOS launchd, AppleScript via `osascript`, zsh, JSON, git.

## Global Constraints

- Scope is only `/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin`.
- `twna` must receive zero automated network requests.
- Do not use proxy rotation, residential proxies, fake User-Agent/header/cookie replay, or `verify=False`.
- Keep `sources_fresh_today()`: same-day success skips `jct/tnpa`; a later date may fetch again.
- Keep the automatic local schedule at Sunday 16:00 Asia/Taipei.
- Sunday 14:00 and 15:00 reminders may open the `twna` page only after an explicit user click.
- Monday 09:00 Asia/Taipei watchdog performs no source-site requests.
- Do not live-fetch `jct/tnpa` during implementation; 2026-07-12 already consumed the current weekly run. Use fixtures/mocks until the next normal Sunday.
- Do not add third-party runtime dependencies or a self-hosted GitHub runner.
- Do not push to `origin` during implementation. Keep task commits local until final review authorizes deployment.

---

## File Map

**Create:**

- `scripts/twna_freshness.py` — read/write manual-source timestamps and evaluate freshness.
- `scripts/twna_reminder.py` — decide whether to remind, display the dialog, handle explicit choices.
- `scripts/check_freshness.py` — offline CLI used by the GitHub watchdog.
- `scripts/run_local_update.command` — Finder/Dock wrapper around `local_update.py`.
- `scripts/launchd/com.lin.twna-reminder.plist` — Sunday 14:00/15:00 reminder schedule.
- `.github/workflows/freshness-watchdog.yml` — Monday offline stale-data gate.
- `tests/test_twna_freshness.py` — timestamp and reminder-suppression tests.
- `tests/test_twna_reminder.py` — dialog choice and zero-network behavior tests.
- `tests/test_freshness_watchdog.py` — watchdog boundary tests.

**Modify:**

- `config/site.py` — add `execution=cloud|local|manual` to every source.
- `scripts/sources/__init__.py` — select and run sources by execution profile.
- `scripts/update.py` — expose mutually exclusive `--sources` and `--profile` CLI options.
- `.github/workflows/update.yml` — run only the `cloud` profile.
- `scripts/import_twna_page.py` — record successful manual import/check timestamps.
- `scripts/twna_watch.py` — preserve freshness updates even when zero new courses are added.
- `scripts/local_update.py` — better twna summary and one bounded push/rebase retry.
- `data/manual_twna.json` — seed truthful initial manual-import metadata.
- `tests/test_parsers.py` — registry profile and importer timestamp tests.
- `tests/test_local_update.py` — same-day guard and git-race tests.
- `README.md` — document reminders, one-click fallback, profiles, watchdog, logs, install/remove commands.
- `HANDOFF_CODEX_BLOCKED_SOURCES.md` — no content change; add it to version control so the dirty-worktree guard does not block launchd.

---

### Task 1: Track the handoff and add source execution profiles

**Files:**
- Modify: `config/site.py:90-186`
- Modify: `scripts/sources/__init__.py:15-55`
- Modify: `scripts/update.py:31-48`
- Modify: `.github/workflows/update.yml:28-30`
- Test: `tests/test_parsers.py:49-61`
- Track: `HANDOFF_CODEX_BLOCKED_SOURCES.md`

**Interfaces:**
- Produces: `select_source_codes(only: list[str] | None = None, profile: str | None = None) -> list[str]`
- Produces: `run_all(only: list[str] | None = None, profile: str | None = None) -> tuple[list[dict], dict[str, dict]]`
- `execution` values are exactly `cloud`, `local`, `manual`.

- [ ] **Step 1: Write failing profile-selection tests**

Add to `tests/test_parsers.py`:

```python
from scripts.sources import run_all, select_source_codes


class TestSourceSelection:
    def test_profile_selects_only_enabled_matching_sources(self, monkeypatch):
        monkeypatch.setattr(cfg, "SOURCES", {
            "a": {"enabled": True, "execution": "cloud"},
            "b": {"enabled": True, "execution": "local"},
            "c": {"enabled": False, "execution": "cloud"},
        })
        assert select_source_codes(profile="cloud") == ["a"]
        assert select_source_codes(profile="local") == ["b"]

    def test_explicit_sources_override_enabled_and_execution(self, monkeypatch):
        monkeypatch.setattr(cfg, "SOURCES", {
            "a": {"enabled": False, "execution": "manual"},
        })
        assert select_source_codes(only=["a"]) == ["a"]

    def test_profile_and_only_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="only and profile"):
            select_source_codes(only=["a"], profile="cloud")
```

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_parsers.py::TestSourceSelection -q`

Expected: collection/import failure because `select_source_codes` does not exist.

- [ ] **Step 3: Implement source selection and profile plumbing**

In `scripts/sources/__init__.py`, implement:

```python
VALID_EXECUTIONS = {"cloud", "local", "manual"}


def select_source_codes(only=None, profile=None):
    if only is not None and profile is not None:
        raise ValueError("only and profile are mutually exclusive")
    if profile is not None and profile not in VALID_EXECUTIONS:
        raise ValueError(f"unknown execution profile: {profile}")
    if only is not None:
        return list(only)
    return [
        code for code, src in cfg.SOURCES.items()
        if src.get("enabled", False)
        and (profile is None or src.get("execution", "cloud") == profile)
    ]
```

Refactor `run_all()` to iterate over `select_source_codes()` while preserving the existing unknown-code outcome. Add `execution="cloud"` to normal sources, `local` to `jct/tnpa`, and `manual` to `twna`. In `scripts/update.py`, use an argparse mutually exclusive group for `--sources` and `--profile`; pass the parsed profile to `run_all`. Change the cloud command to:

```yaml
- name: Scrape cloud sources and rebuild page
  run: python scripts/update.py --profile cloud
```

- [ ] **Step 4: Verify profile behavior without network**

Run:

```bash
.venv/bin/python -m pytest tests/test_parsers.py::TestSourceSelection tests/test_status.py -q
.venv/bin/python scripts/update.py --help
```

Expected: targeted tests pass; help exits 0 and shows mutually exclusive `--sources` and `--profile` options. Do not run
the demo pipeline here because it writes generated production files.

- [ ] **Step 5: Track the handoff and commit**

Run:

```bash
git add HANDOFF_CODEX_BLOCKED_SOURCES.md config/site.py scripts/sources/__init__.py scripts/update.py .github/workflows/update.yml tests/test_parsers.py
git commit -m "feat: separate cloud local and manual sources"
```

---

### Task 2: Add truthful twna freshness metadata

**Files:**
- Create: `scripts/twna_freshness.py`
- Create: `tests/test_twna_freshness.py`
- Modify: `scripts/import_twna_page.py:49-82`
- Modify: `scripts/twna_watch.py:62-79`
- Modify: `tests/test_parsers.py:933-986`
- Modify: `data/manual_twna.json:1-3`

**Interfaces:**
- Produces: `latest_manual_activity(raw: dict) -> datetime | None`
- Produces: `is_fresh(raw: dict, now: datetime, max_age_days: int) -> bool`
- Produces: `mark_checked(path: Path, now: datetime) -> None`
- Produces: `mark_imported(raw: dict, now: datetime) -> None`
- Changes: `import_twna_page.run(html_path, data_path, *, now=None) -> dict`

- [ ] **Step 1: Write failing freshness tests**

Create `tests/test_twna_freshness.py`:

```python
import datetime as dt
import json

from scripts import twna_freshness

TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 7, 19, 14, 0, tzinfo=TZ)


def test_latest_activity_uses_newer_checked_timestamp():
    raw = {
        "manual_imported_at": "2026-07-10T00:00:00+08:00",
        "manual_checked_at": "2026-07-18T14:00:00+08:00",
    }
    assert twna_freshness.latest_manual_activity(raw) == dt.datetime(2026, 7, 18, 14, 0, tzinfo=TZ)


def test_freshness_boundary_is_inclusive():
    raw = {"manual_checked_at": "2026-07-12T14:00:00+08:00"}
    assert twna_freshness.is_fresh(raw, NOW, 7) is True
    assert twna_freshness.is_fresh(raw, NOW + dt.timedelta(seconds=1), 7) is False


def test_mark_checked_preserves_events(tmp_path):
    path = tmp_path / "manual_twna.json"
    path.write_text(json.dumps({"events": [{"title": "x"}]}), encoding="utf-8")
    twna_freshness.mark_checked(path, NOW)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["events"] == [{"title": "x"}]
    assert raw["manual_checked_at"] == "2026-07-19T14:00:00+08:00"
```

Add importer assertions that both timestamps update even when `added == 0`, and that missing/invalid HTML leaves timestamps unchanged.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_twna_freshness.py tests/test_parsers.py::TestImportTwnaPage -q`

Expected: import error because `twna_freshness.py` does not exist.

- [ ] **Step 3: Implement freshness helpers and importer integration**

Implement `scripts/twna_freshness.py` with timezone-aware ISO parsing and atomic JSON replacement through a same-directory temporary file. Core behavior:

```python
FIELDS = ("manual_imported_at", "manual_checked_at")


def latest_manual_activity(raw):
    values = []
    for field in FIELDS:
        value = raw.get(field, "")
        if value:
            values.append(dt.datetime.fromisoformat(value))
    return max(values) if values else None


def is_fresh(raw, now, max_age_days):
    latest = latest_manual_activity(raw)
    return latest is not None and now - latest <= dt.timedelta(days=max_age_days)


def mark_imported(raw, now):
    stamp = now.astimezone().isoformat(timespec="seconds")
    raw["manual_imported_at"] = stamp
    raw["manual_checked_at"] = stamp
```

Make `import_twna_page.run(..., now=None)` set both timestamps only after successful HTML parsing and JSON merge. Seed the real JSON with:

```json
"manual_imported_at": "2026-07-10T00:00:00+08:00",
"manual_checked_at": ""
```

Ensure `twna_watch.process()` leaves the modified metadata for `local_update.py` to commit even when no new event was added.

- [ ] **Step 4: Run focused and full offline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_twna_freshness.py tests/test_twna_watch.py tests/test_parsers.py::TestImportTwnaPage -q
.venv/bin/python -m pytest -q
```

Expected: all tests pass; no source fetch occurs.

- [ ] **Step 5: Commit**

```bash
git add scripts/twna_freshness.py scripts/import_twna_page.py scripts/twna_watch.py tests/test_twna_freshness.py tests/test_parsers.py data/manual_twna.json
git commit -m "feat: track manual twna freshness"
```

---

### Task 3: Add the Sunday twna reminder

**Files:**
- Create: `scripts/twna_reminder.py`
- Create: `scripts/launchd/com.lin.twna-reminder.plist`
- Create: `tests/test_twna_reminder.py`

**Interfaces:**
- Produces: `reminder_needed(data_path: Path, downloads: Path, now: datetime) -> bool`
- Produces: `handle_choice(choice: str, data_path: Path, now: datetime) -> int`
- CLI exits 0 for suppressed/reminded/handled choices and 1 for unreadable state or osascript failure.

- [ ] **Step 1: Write failing reminder tests**

Create tests that never invoke real AppleScript or a browser:

```python
def test_pending_saved_page_suppresses_reminder(tmp_path):
    data = tmp_path / "manual.json"
    data.write_text('{"events": []}', encoding="utf-8")
    page = tmp_path / "twna.html"
    page.write_text(TWNA_HTML, encoding="utf-8")
    assert twna_reminder.reminder_needed(data, tmp_path, NOW) is False


def test_explicit_open_choice_is_only_path_that_opens_browser(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(twna_reminder.subprocess, "run", lambda args, **kw: calls.append(args))
    assert twna_reminder.handle_choice("稍後提醒", tmp_path / "x.json", NOW) == 0
    assert calls == []
    assert twna_reminder.handle_choice("開啟課程頁", tmp_path / "x.json", NOW) == 0
    assert calls == [["open", twna.LIST_URL]]


def test_confirmed_choice_records_check_without_opening(monkeypatch, tmp_path):
    data = tmp_path / "manual.json"
    data.write_text('{"events": []}', encoding="utf-8")
    calls = []
    monkeypatch.setattr(twna_reminder.subprocess, "run", lambda args, **kw: calls.append(args))
    assert twna_reminder.handle_choice("本週已確認", data, NOW) == 0
    assert calls == []
    assert "manual_checked_at" in data.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_twna_reminder.py -q`

Expected: import failure because `twna_reminder` does not exist.

- [ ] **Step 3: Implement reminder and plist**

Use `twna_freshness.is_fresh(..., 7)` plus `twna_watch.scan_folder()` for suppression. Display this AppleScript dialog only when needed:

```python
SCRIPT = '''button returned of (display dialog "台灣護理學會資料需要人工核對。請開啟課程頁，選擇「檔案 → 另存新檔 → 僅 HTML」，存到下載資料夾。" with title "護理教育訓練網站" buttons {"稍後提醒", "本週已確認", "開啟課程頁"} default button "開啟課程頁")'''
```

The plist uses a `StartCalendarInterval` array with Sunday 14:00 and 15:00 and writes stdout/stderr to `/tmp/nursing-twna-reminder.log`. Use the existing `/Users/healon/Projects/nursing-coursetw-lin` symlink and project venv paths.

- [ ] **Step 4: Verify offline behavior and plist syntax**

Run:

```bash
.venv/bin/python -m pytest tests/test_twna_reminder.py tests/test_twna_freshness.py tests/test_twna_watch.py -q
plutil -lint scripts/launchd/com.lin.twna-reminder.plist
```

Expected: tests pass; plist reports `OK`. Do not execute the real reminder yet.

- [ ] **Step 5: Commit**

```bash
git add scripts/twna_reminder.py scripts/launchd/com.lin.twna-reminder.plist tests/test_twna_reminder.py
git commit -m "feat: remind for weekly twna review"
```

---

### Task 4: Harden local update without changing the same-day guard

**Files:**
- Modify: `scripts/local_update.py:48-156`
- Modify: `tests/test_local_update.py`

**Interfaces:**
- Preserves: `sources_fresh_today(snapshot, today_iso, codes=LOCAL_SOURCES) -> bool`
- Produces: `push_with_one_rebase_retry() -> tuple[bool, str]`
- Must not call `scripts/update.py` again during git retry.

- [ ] **Step 1: Write failing git-race and same-day tests**

Add tests with a queued fake `_git`:

```python
import subprocess


def result(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


def test_push_retries_once_after_non_fast_forward(monkeypatch):
    responses = iter([
        result(1, err="non-fast-forward"),
        result(0),
        result(0),
    ])
    calls = []
    monkeypatch.setattr(local_update, "_git", lambda *args: calls.append(args) or next(responses))
    ok, detail = local_update.push_with_one_rebase_retry()
    assert ok is True
    assert calls == [
        ("push", "origin", "main"),
        ("pull", "--rebase", "origin", "main"),
        ("push", "origin", "main"),
    ]


def test_push_conflict_aborts_rebase_and_does_not_retry_again(monkeypatch):
    responses = iter([
        result(1, err="non-fast-forward"),
        result(1, err="CONFLICT"),
        result(0),
    ])
    calls = []
    monkeypatch.setattr(local_update, "_git", lambda *args: calls.append(args) or next(responses))
    ok, detail = local_update.push_with_one_rebase_retry()
    assert ok is False
    assert "CONFLICT" in detail
    assert calls[-1] == ("rebase", "--abort")
```

Retain and extend the existing tests proving same date returns true and next date returns false.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_local_update.py -q`

Expected: failure because `push_with_one_rebase_retry` does not exist.

- [ ] **Step 3: Implement bounded retry and accurate twna summary**

Implement:

```python
def push_with_one_rebase_retry():
    first = _git("push", "origin", "main")
    if first.returncode == 0:
        return True, ""
    detail = (first.stderr or first.stdout).strip()
    if "non-fast-forward" not in detail and "fetch first" not in detail.lower():
        return False, detail
    rebase = _git("pull", "--rebase", "origin", "main")
    if rebase.returncode != 0:
        conflict = (rebase.stderr or rebase.stdout).strip()
        _git("rebase", "--abort")
        return False, conflict
    second = _git("push", "origin", "main")
    return second.returncode == 0, (second.stderr or second.stdout).strip()
```

Replace the direct final push with this helper. Read twna freshness after folder scanning so the completion notification distinguishes imported, recently confirmed, and unconfirmed/stale. Do not change the fetch decision from `sources_fresh_today()`.

- [ ] **Step 4: Run local tests and full offline suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_local_update.py tests/test_twna_freshness.py -q
.venv/bin/python -m pytest -q
```

Expected: all pass; no source-site requests.

- [ ] **Step 5: Commit**

```bash
git add scripts/local_update.py tests/test_local_update.py
git commit -m "fix: make local update resilient to git races"
```

---

### Task 5: Add Finder/Dock one-click fallback

**Files:**
- Create: `scripts/run_local_update.command`
- Modify: `README.md`

**Interfaces:**
- Invokes exactly one business entry point: `.venv/bin/python scripts/local_update.py`.
- Appends combined output to `~/Library/Logs/nursing-course-update.log` and preserves the Python exit code.

- [ ] **Step 1: Create a shell syntax check that initially fails**

Run: `zsh -n scripts/run_local_update.command`

Expected: non-zero because the file does not exist.

- [ ] **Step 2: Implement the wrapper**

Create the executable file:

```zsh
#!/bin/zsh
set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/nursing-course-update.log"

mkdir -p "$LOG_DIR"
if [[ ! -x "$PYTHON" ]]; then
  osascript -e 'display notification "找不到專案 Python；請確認外接 SSD 已連接" with title "護理教育訓練網站"'
  exit 1
fi

"$PYTHON" "$ROOT/scripts/local_update.py" 2>&1 | tee -a "$LOG_FILE"
exit ${pipestatus[1]}
```

Set executable mode with `chmod +x scripts/run_local_update.command`. Document double-clicking and dragging it to the Dock. The wrapper must not duplicate any update logic.

- [ ] **Step 3: Verify syntax and missing-environment behavior**

Run:

```bash
zsh -n scripts/run_local_update.command
test -x scripts/run_local_update.command
```

Expected: both commands exit 0. Do not execute the wrapper because it would run live sources on a new date.

- [ ] **Step 4: Commit**

```bash
git add scripts/run_local_update.command README.md
git commit -m "feat: add one-click local update"
```

---

### Task 6: Add the offline GitHub freshness watchdog

**Files:**
- Create: `scripts/check_freshness.py`
- Create: `tests/test_freshness_watchdog.py`
- Create: `.github/workflows/freshness-watchdog.yml`

**Interfaces:**
- Produces: `evaluate(status_snapshot: dict, manual_twna: dict, now: datetime, max_age_days: int = 8) -> list[str]`
- CLI returns 0 when no failures and 1 when any local/manual source is missing, invalid, or stale.

- [ ] **Step 1: Write failing boundary tests**

Create `tests/test_freshness_watchdog.py`:

```python
import datetime as dt
from scripts import check_freshness

TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 7, 20, 9, 0, tzinfo=TZ)


def snapshot(last_success="2026-07-12"):
    return {"sources": {
        "jct": {"last_success": last_success},
        "tnpa": {"last_success": last_success},
    }}


def test_exactly_eight_days_is_fresh():
    manual = {"manual_checked_at": "2026-07-12T09:00:00+08:00"}
    assert check_freshness.evaluate(snapshot(), manual, NOW, 8) == []


def test_older_than_eight_days_reports_each_source():
    failures = check_freshness.evaluate(
        snapshot("2026-07-11"),
        {"manual_checked_at": "2026-07-11T08:59:59+08:00"},
        NOW,
        8,
    )
    assert any("jct" in x for x in failures)
    assert any("tnpa" in x for x in failures)
    assert any("twna" in x for x in failures)


def test_missing_or_invalid_state_fails_closed():
    failures = check_freshness.evaluate({}, {}, NOW, 8)
    assert len(failures) == 3
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_freshness_watchdog.py -q`

Expected: import failure because `check_freshness.py` does not exist.

- [ ] **Step 3: Implement the pure evaluator and CLI**

Parse `jct/tnpa.last_success` as Taipei calendar dates and compare at date precision; use `twna_freshness.latest_manual_activity()` for twna. The CLI loads the real JSON paths, prints one line per failure, and exits 1 if `evaluate()` returns anything.

Create `.github/workflows/freshness-watchdog.yml`:

```yaml
name: local-source-freshness

on:
  schedule:
    - cron: "0 1 * * 1"  # Monday 09:00 Asia/Taipei
  workflow_dispatch: {}

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python scripts/check_freshness.py --max-age-days 8
```

- [ ] **Step 4: Verify offline and inspect workflow**

Run:

```bash
.venv/bin/python -m pytest tests/test_freshness_watchdog.py tests/test_twna_freshness.py -q
.venv/bin/python scripts/check_freshness.py --max-age-days 8
```

Expected during implementation week: the real command may exit 1 for stale twna and must print the exact stale reason; this is valid evidence, not a test failure. The pytest command must pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/check_freshness.py tests/test_freshness_watchdog.py .github/workflows/freshness-watchdog.yml
git commit -m "feat: detect stale local and manual sources"
```

---

### Task 7: Documentation, launchd installation, and full verification

**Files:**
- Modify: `README.md`
- Modify: `HANDOFF.md`
- Verify: all files changed in Tasks 1-6

**Interfaces:**
- User-facing commands and schedules must match the implemented plist/workflow exactly.

- [ ] **Step 1: Update operating documentation**

Document:

- cloud/local/manual execution modes;
- Sunday 14:00/15:00 reminder and 16:00 local update;
- Monday 09:00 watchdog;
- `manual_imported_at` versus `manual_checked_at`;
- one-click `.command`, Dock setup, and log path;
- same-day skip versus next-day allowed fetch;
- install/remove commands for `com.lin.twna-reminder`;
- failure recovery for dirty worktree, stale watchdog, and git rebase conflict.

Update `HANDOFF.md` so future agents do not reintroduce cloud attempts for `jct/tnpa` or automated twna access.

- [ ] **Step 2: Run static verification**

Run:

```bash
plutil -lint scripts/launchd/*.plist
zsh -n scripts/run_local_update.command
git diff --check
.venv/bin/python -m pytest -q
```

Expected: every plist reports `OK`; shell syntax exits 0; diff check is clean; all tests pass with a count greater than the 170-test baseline.

- [ ] **Step 3: Verify zero forbidden calls with AST**

Run an inline AST audit over `scripts/**/*.py` that fails only when a real function call contains keyword `verify=False`:

```bash
.venv/bin/python - <<'PY'
import ast
from pathlib import Path

hits = []
for path in Path("scripts").rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    hits.append(f"{path}:{node.lineno}")
if hits:
    raise SystemExit("forbidden verify=False calls: " + ", ".join(hits))
print("OK: no verify=False calls")
PY
```

Expected: `OK: no verify=False calls`.

- [ ] **Step 4: Install and inspect the reminder launchd job**

Run:

```bash
cp scripts/launchd/com.lin.twna-reminder.plist ~/Library/LaunchAgents/
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.lin.twna-reminder.plist 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.lin.twna-reminder.plist
launchctl print "gui/$(id -u)/com.lin.twna-reminder"
```

Expected: launchctl shows two Sunday calendar triggers at 14:00 and 15:00. Do not manually trigger it yet; that would be a UI smoke test only, not source access, but defer until after review.

- [ ] **Step 5: Commit final docs**

```bash
git add README.md HANDOFF.md
git commit -m "docs: document automated update operations"
```

- [ ] **Step 6: Final local evidence and deployment gate**

Run:

```bash
git status --short --branch
git log --oneline --decorate -10
.venv/bin/python -m pytest -q
```

Expected: working tree clean; branch ahead of origin by the task commits; full test suite passes. Do not run `scripts/local_update.py` live and do not push. Present the commit list and evidence to Lin, then request explicit approval to push and use the next normal Sunday as the single live end-to-end verification.
