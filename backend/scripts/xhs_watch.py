#!/usr/bin/env python3
"""
Watch backend/data/ for new 八爪鱼 CSV exports, merge them into xhs_notes.json,
then DELETE the processed CSV to keep the folder clean.

Usage:
    python scripts/xhs_watch.py            # process all *.csv now, then exit
    python scripts/xhs_watch.py --watch    # keep watching (polls every 5s)

Because processed CSVs are deleted, xhs_notes.json is the single source of truth.
Merging is therefore ADDITIVE and DEDUPED by note url (帖子详情页链接): re-collecting
the same restaurant later refreshes it without creating duplicate notes.
"""

import json
import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))

# Reuse the export parsing + COLUMN_MAP / aliases from the ingestion module.
from scripts.ingest_xhs_export import ingest, _OUT_FILE

_DATA_DIR = _BACKEND / "data"
_OUT = _OUT_FILE  # data/xhs_notes.json
_MIN_AGE_SECONDS = 2.0  # skip files still being written (mtime too recent)


def _load_existing() -> dict:
    if _OUT.exists():
        try:
            return json.loads(_OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"⚠️  {_OUT.name} is corrupt — starting fresh")
    return {}


def _note_key(note: dict) -> str:
    """Identity for dedup: prefer the note url, fall back to title."""
    return note.get("url") or note.get("title") or json.dumps(note, sort_keys=True, ensure_ascii=False)


def _merge(existing: dict, incoming: dict) -> int:
    added = 0
    for restaurant, notes in incoming.items():
        bucket = existing.setdefault(restaurant, [])
        seen = {_note_key(n) for n in bucket}
        for n in notes:
            k = _note_key(n)
            if k not in seen:
                bucket.append(n)
                seen.add(k)
                added += 1
    return added


def process_once() -> int:
    """Merge every settled *.csv in data/ into xhs_notes.json, then delete it."""
    now = time.time()
    csvs = sorted(
        p for p in _DATA_DIR.glob("*.csv")
        if now - p.stat().st_mtime >= _MIN_AGE_SECONDS  # not mid-write
    )
    if not csvs:
        return 0

    existing = _load_existing()
    total_added = 0
    for csv_path in csvs:
        try:
            incoming = ingest([csv_path])
        except Exception as e:
            print(f"⚠️  skipped {csv_path.name}: {e}")
            continue
        if not incoming:
            print(f"⚠️  {csv_path.name}: no rows matched COLUMN_MAP — left in place, NOT deleted")
            continue
        added = _merge(existing, incoming)
        total_added += added
        summary = ", ".join(f"{r}({len(ns)})" for r, ns in incoming.items())
        print(f"✓ {csv_path.name}: +{added} new notes  [{summary}]")
        csv_path.unlink()
        print(f"  🗑  deleted {csv_path.name}")

    _OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {_OUT.name}: {len(existing)} restaurants, "
          f"{sum(len(v) for v in existing.values())} notes total")
    return total_added


def watch(interval: float = 5.0) -> None:
    print(f"👀 watching {_DATA_DIR} for *.csv every {interval:g}s — Ctrl-C to stop")
    try:
        while True:
            process_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        process_once()
