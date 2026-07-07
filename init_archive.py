#!/usr/bin/env python3
"""
Download Archive Initializer

One-time backfill script that scans existing downloaded videos and their
metadata sidecars, then populates a gallery-dl SQLite download archive
(.archive.sqlite3) so already-downloaded videos are skipped on future runs.

Usage:
  python3 init_archive.py              # Build/populate the archive
  python3 init_archive.py --dry-run    # Preview what would be added
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

# ============== CONFIG ==============
VIDEO_DIR = Path("downloads/video")
ARCHIVE_FILE = ".archive.sqlite3"
# =====================================


def ensure_schema(conn):
    """Create the archive table if it doesn't exist (matches gallery-dl schema)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS archive "
        "(entry TEXT PRIMARY KEY) WITHOUT ROWID"
    )
    conn.commit()


def build_key_from_sidecar(json_path):
    """Read a .json metadata sidecar and return the archive key, or None."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    tweet_id = data.get("tweet_id")
    retweet_id = data.get("retweet_id", 0)
    num = data.get("num")

    if tweet_id is None or num is None:
        return None

    return f"twitter{tweet_id}_{retweet_id}_{num}"


def build_key_from_filename(video_path):
    """Parse a video filename to construct an archive key (fallback).

    gallery-dl names files: {tweet_id}_{num}.{extension}
    retweet_id is unknown from the filename alone — assume 0.
    """
    match = re.match(r"(\d+)_(\d+)\.", video_path.name)
    if not match:
        return None
    tweet_id = match.group(1)
    num = match.group(2)
    return f"twitter{tweet_id}_0_{num}"


def collect_keys():
    """Scan VIDEO_DIR for all archive keys from sidecars and video filenames."""
    keys = set()
    sidecar_count = 0
    filename_count = 0

    if not VIDEO_DIR.exists():
        return keys, sidecar_count, filename_count

    video_exts = (".mp4", ".webm", ".m4v", ".mkv")
    video_files = []
    for ext in video_exts:
        video_files.extend(VIDEO_DIR.rglob(f"*{ext}"))

    for video_path in video_files:
        # Try sidecar first
        json_path = video_path.with_suffix(".json")
        if not json_path.exists():
            json_path = Path(str(video_path) + ".json")

        if json_path.exists():
            key = build_key_from_sidecar(json_path)
            if key:
                keys.add(key)
                sidecar_count += 1
                continue

        # Fallback: parse from filename
        key = build_key_from_filename(video_path)
        if key:
            keys.add(key)
            filename_count += 1

    return keys, sidecar_count, filename_count


def main():
    parser = argparse.ArgumentParser(
        description="Build gallery-dl download archive from existing downloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
After running this once, scrape_bookmarks.py will automatically skip
already-downloaded videos using the .archive.sqlite3 archive.
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview keys without writing to the archive database",
    )
    args = parser.parse_args()

    print("📋 Scanning existing downloads for archive entries...\n")

    keys, sidecar_count, filename_count = collect_keys()

    if not keys:
        print("❌ No downloadable videos found in downloads/video/")
        print("   Run scrape_bookmarks.py first to download some videos.")
        return

    print(f"  Found {len(keys)} unique video entries:")
    print(f"    📄 From metadata sidecars: {sidecar_count}")
    print(f"    📄 From filename fallback:  {filename_count}")

    if args.dry_run:
        print(f"\n🔍 DRY RUN — no database changes will be made")
        print(f"   {len(keys)} entries would be inserted into {ARCHIVE_FILE}")
        return

    # Write to archive
    conn = sqlite3.connect(ARCHIVE_FILE)
    ensure_schema(conn)

    inserted = 0
    for key in sorted(keys):
        cursor = conn.execute(
            "INSERT OR IGNORE INTO archive (entry) VALUES (?)", (key,)
        )
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()

    # Get total count
    total = conn.execute("SELECT COUNT(*) FROM archive").fetchone()[0]
    conn.close()

    print(f"\n✅ Archive updated: {ARCHIVE_FILE}")
    print(f"   Inserted:           {inserted} new entries")
    print(f"   Already in archive: {len(keys) - inserted}")
    print(f"   Total entries:      {total}")
    print(f"\n💡 Future runs of scrape_bookmarks.py will skip these videos automatically.")


if __name__ == "__main__":
    main()
