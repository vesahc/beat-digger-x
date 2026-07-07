#!/usr/bin/env python3
"""
Video Deletion Tool
Reads video_selections.json (exported from the HTML catalog) and deletes
video files, metadata sidecars, and extracted MP3s for entries marked as
deleted. Cleans up empty directories after deletion.

Usage:
  python delete_videos.py              # Interactive (prompts for confirmation)
  python delete_videos.py --dry-run    # Preview only, no changes
  python delete_videos.py --yes        # Skip confirmation prompt
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# ============== CONFIG ==============
SELECTIONS_FILE = "video_selections.json"
VIDEO_DIR = Path("downloads/video")
AUDIO_DIR = Path("downloads/audio")
ARCHIVE_FILE = ".archive.sqlite3"
# =====================================


def load_selections(filepath):
    """Load video_selections.json and return entries marked as deleted."""
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        print("   Export selections from the HTML catalog first (Export JSON button)")
        sys.exit(1)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Could not parse {filepath}: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        print(f"❌ Unexpected format in {filepath} — expected a JSON array")
        sys.exit(1)

    deleted = [item for item in data if item.get("deleted")]
    return deleted


def find_video_file(tweet_id):
    """Find a video file in VIDEO_DIR by tweet_id (exact stem match)."""
    for ext in (".mp4", ".webm", ".m4v", ".mkv"):
        for f in VIDEO_DIR.rglob(f"*{ext}"):
            if f.stem == tweet_id:
                return f
    return None


def find_metadata_sidecar(video_path):
    """Find the .json metadata sidecar for a video file."""
    json_path = video_path.with_suffix(".json")
    if json_path.exists():
        return json_path
    # Some gallery-dl versions append .json to the full filename
    alt_json = Path(str(video_path) + ".json")
    if alt_json.exists():
        return alt_json
    return None


def find_audio_file(tweet_id, username):
    """Find extracted MP3 in AUDIO_DIR by tweet_id and username."""
    if not AUDIO_DIR.exists():
        return None

    # extract_audio.py strips _1/_2 suffixes from tweet_id for audio naming
    clean_id = tweet_id
    if clean_id.endswith("_1") or clean_id.endswith("_2"):
        clean_id = clean_id.rsplit("_", 1)[0]

    # Primary: [username]-[clean_id].mp3
    if username and username not in ("video", "twitter"):
        candidate = AUDIO_DIR / f"{username}-{clean_id}.mp3"
        if candidate.exists():
            return candidate

    # Fallback: search for any mp3 containing the clean tweet_id
    for f in AUDIO_DIR.glob("*.mp3"):
        if clean_id in f.stem:
            return f

    return None


def build_archive_key(video_path, metadata_path):
    """Construct a gallery-dl archive key from metadata sidecar or filename."""
    if metadata_path and metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            tweet_id = data.get("tweet_id")
            retweet_id = data.get("retweet_id", 0)
            num = data.get("num")
            if tweet_id is not None and num is not None:
                return f"twitter{tweet_id}_{retweet_id}_{num}"
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: parse from filename {tweet_id}_{num}.ext
    match = re.match(r"(\d+)_(\d+)\.", video_path.name)
    if match:
        return f"twitter{match.group(1)}_0_{match.group(2)}"
    return None


def add_to_archive(key):
    """Insert an archive key so gallery-dl skips this video on future scrapes."""
    try:
        conn = sqlite3.connect(ARCHIVE_FILE, timeout=60)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS archive "
            "(entry TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        conn.execute("INSERT OR IGNORE INTO archive (entry) VALUES (?)", (key,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"  ⚠️  Archive update failed: {e}")


def cleanup_empty_dirs(start_path, stop_dirs):
    """Remove empty parent directories up the tree, stopping at stop_dirs."""
    current = start_path
    stop_set = {d.resolve() for d in stop_dirs}

    while current.resolve() not in stop_set:
        if not current.exists():
            current = current.parent
            continue
        try:
            current.rmdir()
            print(f"  📁 Removed empty directory: {current}")
            current = current.parent
        except OSError:
            # Directory not empty — stop cleanup
            break


def update_selections(filepath, plan):
    """Remove deleted entries from video_selections.json."""
    deleted_ids = {p["tweet_id"] for p in plan}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        remaining = [item for item in data if item.get("tweet_id") not in deleted_ids]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(remaining, f, indent=2)
        print(f"\n📝 Updated {filepath} — removed {len(deleted_ids)} deleted entries")
    except Exception as e:
        print(f"\n⚠️  Could not update {filepath}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Delete videos marked as deleted in video_selections.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python delete_videos.py              # Interactive mode
  python delete_videos.py --dry-run    # Preview only
  python delete_videos.py --yes        # Skip confirmation
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without making changes",   )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",   )
    parser.add_argument(
        "--file",
        default=SELECTIONS_FILE,
        help=f"Selections JSON file (default: {SELECTIONS_FILE})",
    )

    args = parser.parse_args()

    # Load selections
    deleted_entries = load_selections(args.file)
    if not deleted_entries:
        print("📄 No videos marked as deleted in selections file")
        sys.exit(0)

    print(f"📋 Found {len(deleted_entries)} videos marked for deletion\n")

    # Build deletion plan
    plan = []
    for entry in deleted_entries:
        tweet_id = entry.get("tweet_id")
        if not tweet_id:
            print(f"  ⚠️  Entry missing tweet_id, skipping: {entry}")
            continue

        video_path = find_video_file(tweet_id)
        if not video_path:
            plan.append({
                "tweet_id": tweet_id,
                "video_path": None,
                "metadata_path": None,
                "audio_path": None,
                "archive_key": None,
                "status": "not_found",
            })
            continue

        metadata_path = find_metadata_sidecar(video_path)
        username = (
            video_path.parent.name
            if video_path.parent.name not in ("video", "twitter")
            else None
        )
        audio_path = find_audio_file(tweet_id, username)

        archive_key = build_archive_key(video_path, metadata_path)

        plan.append({
            "tweet_id": tweet_id,
            "video_path": video_path,
            "metadata_path": metadata_path,
            "audio_path": audio_path,
            "archive_key": archive_key,
            "status": "found",
        })

    # Display plan
    found_count = sum(1 for p in plan if p["status"] == "found")
    not_found_count = sum(1 for p in plan if p["status"] == "not_found")

    print(f"{'=' * 60}")
    if args.dry_run:
        print(f"🔍 DRY RUN — no files will be deleted")
    print(f"{'=' * 60}\n")

    for p in plan:
        tid = p["tweet_id"]
        if p["status"] == "not_found":
            print(f"  ⚠️  Tweet {tid}: video file not found (already deleted?)")
            continue

        print(f"  Tweet {tid}:")
        print(f"    📹 Video:     {p['video_path']}")
        if p["metadata_path"]:
            print(f"    📄 Metadata:  {p['metadata_path']}")
        if p["audio_path"]:
            print(f"    🔊 Audio:     {p['audio_path']}")

    print(f"\n{'=' * 60}")
    print(f"  Found:       {found_count}")
    if not_found_count:
        print(f"  Not found:   {not_found_count} (already deleted?)")
    print(f"{'=' * 60}")

    if args.dry_run:
        print(f"\nTo actually delete these files, run:")
        print(f"  python {os.path.basename(__file__)} --yes")
        return

    if found_count == 0:
        print("\n📄 Nothing to delete")
        update_selections(args.file, plan)
        return

    # Confirmation
    if not args.yes:
        response = input(f"\n⚠️  Delete {found_count} video(s) and associated files? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("❌ Cancelled")
            return

    # Execute deletion
    print(f"\n🗑️  Deleting...\n")
    deleted_count = 0
    errors = []

    for p in plan:
        if p["status"] != "found":
            continue

        tid = p["tweet_id"]
        cleanup_dir = None

        # Delete video file
        if p["video_path"] and p["video_path"].exists():
            try:
                p["video_path"].unlink()
                print(f"  ✅ Deleted video: {p['video_path'].name}")
                cleanup_dir = p["video_path"].parent
                deleted_count += 1
            except Exception as e:
                errors.append(f"Tweet {tid}: video delete failed: {e}")
                print(f"  ❌ Video delete failed: {e}")

        # Delete metadata sidecar
        if p["metadata_path"] and p["metadata_path"].exists():
            try:
                p["metadata_path"].unlink()
                print(f"  ✅ Deleted metadata: {p['metadata_path'].name}")
            except Exception as e:
                errors.append(f"Tweet {tid}: metadata delete failed: {e}")

        # Delete audio file
        if p["audio_path"] and p["audio_path"].exists():
            try:
                p["audio_path"].unlink()
                print(f"  ✅ Deleted audio: {p['audio_path'].name}")
            except Exception as e:
                errors.append(f"Tweet {tid}: audio delete failed: {e}")

        # Add to download archive so it's skipped on future scrapes
        if p.get("archive_key"):
            add_to_archive(p["archive_key"])
            print(f"  📋 Added to archive: {p['archive_key']}")

        # Clean up empty directories (don't go above VIDEO_DIR)
        if cleanup_dir:
            cleanup_empty_dirs(cleanup_dir, [VIDEO_DIR])

    # Update selections file to remove deleted entries
    update_selections(args.file, plan)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"📊 COMPLETE")
    print(f"{'=' * 60}")
    print(f"✅ Deleted:  {deleted_count} video(s)")
    if errors:
        print(f"❌ Errors:   {len(errors)}")
        for err in errors:
            print(f"   • {err}")
    print(f"\n💡 Run 'python list_videos.py' to regenerate the HTML catalog")


if __name__ == "__main__":
    main()
