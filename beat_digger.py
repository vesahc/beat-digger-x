#!/usr/bin/env python3
"""
Beat Digger X — Unified CLI

Single entry point for the Beat Digger X toolkit. Wraps the existing scripts
into subcommands for a streamlined workflow.

Subcommands:
  scrape    Download new videos from Twitter bookmarks
  mp3       Extract audio from downloaded videos
  catalog   Generate the interactive HTML catalog
  delete    Delete videos marked in the catalog
  clear     Clear bookmarks from Twitter
  archive   One-time backfill of download archive
  status    Show collection statistics
  all       Run full pipeline: scrape → mp3 → catalog

Examples:
  python3 beat_digger.py scrape                  # download new videos
  python3 beat_digger.py scrape --rescrape       # force fresh download
  python3 beat_digger.py scrape --extract-audio  # download + extract MP3
  python3 beat_digger.py catalog --open          # generate + open HTML
  python3 beat_digger.py delete --dry-run        # preview deletions
  python3 beat_digger.py all                     # scrape → mp3 → catalog
  python3 beat_digger.py status                  # show stats
"""

import argparse
import sqlite3
import sys
import time
import webbrowser
from contextlib import contextmanager
from pathlib import Path

# Project paths
VIDEO_DIR = Path("downloads/video")
AUDIO_DIR = Path("downloads/audio")
ARCHIVE_FILE = ".archive.sqlite3"
CATALOG_FILE = "video_list.html"
COOKIES_FILE = "cookies.txt"
UNBOOKMARK_FILE = "to_unbookmark.csv"


@contextmanager
def argv_override(args):
    """Temporarily override sys.argv for calling script main() functions."""
    original = sys.argv
    sys.argv = [original[0]] + args
    try:
        yield
    finally:
        sys.argv = original


# ── Subcommand implementations ──────────────────────────────────────────

def run_scrape(rescrape=False, extract_audio=False):
    """Download new videos from Twitter bookmarks."""
    import scrape_bookmarks

    args = ["--rescrape"] if rescrape else []
    with argv_override(args):
        scrape_bookmarks.main()

    if extract_audio:
        print("\n" + "=" * 60)
        print("🎵 Extracting audio from downloaded videos...")
        print("=" * 60 + "\n")
        run_mp3()


def run_mp3():
    """Extract audio from downloaded videos."""
    import download_bookmarks
    download_bookmarks.main()


def run_catalog(open_browser=False):
    """Generate the interactive HTML catalog."""
    import list_videos
    list_videos.main()

    if open_browser:
        catalog_path = Path(CATALOG_FILE).resolve()
        print(f"\n🌐 Opening {catalog_path} in browser...")
        try:
            webbrowser.open(f"file://{catalog_path}")
        except Exception:
            print(f"   Could not open browser. Open manually: {catalog_path}")


def run_delete(dry_run=False, yes=False, file=None):
    """Delete videos marked in the catalog, then regenerate catalog."""
    import delete_videos

    args = []
    if dry_run:
        args.append("--dry-run")
    if yes:
        args.append("--yes")
    if file:
        args.extend(["--file", file])

    try:
        with argv_override(args):
            delete_videos.main()
    except SystemExit as e:
        if e.code != 0:
            raise  # Real error, propagate
        # exit(0) = no deletions found, skip regen
        return

    # Auto-regenerate catalog after successful deletion (skip on dry-run)
    if not dry_run:
        print("\n" + "=" * 60)
        print("📋 Regenerating catalog...")
        print("=" * 60 + "\n")
        run_catalog()


def run_clear(mode="manual", confirm=False, batch_size=None, file=None):
    """Clear bookmarks from Twitter."""
    import clear_bookmarks

    args = ["--mode", mode]
    if confirm:
        args.append("--confirm")
    if batch_size is not None:
        args.extend(["--batch-size", str(batch_size)])
    if file:
        args.extend(["--file", file])

    with argv_override(args):
        clear_bookmarks.main()


def run_archive(dry_run=False):
    """One-time backfill of download archive."""
    import init_archive

    args = ["--dry-run"] if dry_run else []
    with argv_override(args):
        init_archive.main()


def run_status():
    """Show collection statistics."""
    print("=" * 60)
    print("📊 Beat Digger X — Status")
    print("=" * 60 + "\n")

    # Videos
    video_count = 0
    if VIDEO_DIR.exists():
        for ext in ("*.mp4", "*.webm", "*.m4v"):
            video_count += len(list(VIDEO_DIR.rglob(ext)))

    # MP3s
    mp3_count = 0
    if AUDIO_DIR.exists():
        mp3_count = len(list(AUDIO_DIR.rglob("*.mp3")))

    # Archive
    archive_count = 0
    archive_exists = Path(ARCHIVE_FILE).exists()
    if archive_exists:
        try:
            conn = sqlite3.connect(str(ARCHIVE_FILE))
            archive_count = conn.execute("SELECT COUNT(*) FROM archive").fetchone()[0]
            conn.close()
        except sqlite3.Error:
            archive_count = -1

    # Catalog freshness
    catalog_exists = Path(CATALOG_FILE).exists()
    if catalog_exists:
        catalog_age = time.time() - Path(CATALOG_FILE).stat().st_mtime
        if catalog_age < 3600:
            catalog_status = f"{catalog_age / 60:.0f} min ago"
        elif catalog_age < 86400:
            catalog_status = f"{catalog_age / 3600:.1f} hr ago"
        else:
            catalog_status = f"{catalog_age / 86400:.1f} days ago"
    else:
        catalog_status = "not generated"

    # Cookies
    cookies_exists = Path(COOKIES_FILE).exists()

    # Cross-ref CSV
    csv_exists = Path(UNBOOKMARK_FILE).exists()

    # Print status table
    print(f"  📹 Videos:      {video_count}")
    print(f"  🎵 MP3s:        {mp3_count}")
    if archive_count >= 0:
        print(f"  📦 Archive:     {archive_count} entries" + (" (not initialized)" if archive_count == 0 else ""))
    else:
        print(f"  📦 Archive:     error reading database")
    print(f"  📋 Catalog:     {'✅ ' + catalog_status if catalog_exists else '❌ ' + catalog_status}")
    print(f"  🍪 Cookies:     {'✅ found' if cookies_exists else '❌ missing'}")
    print(f"  📄 Unbookmark:  {'✅ found' if csv_exists else '— not generated'}")

    # Warnings / suggestions
    warnings = []
    if video_count > 0 and mp3_count == 0:
        warnings.append("Run 'beat_digger.py mp3' to extract audio")
    if video_count > 0 and not catalog_exists:
        warnings.append("Run 'beat_digger.py catalog' to generate the HTML catalog")
    if video_count > 0 and archive_count == 0:
        warnings.append("Run 'beat_digger.py archive' to initialize the download archive")
    if not cookies_exists:
        warnings.append("cookies.txt missing — scrape will fail without it")

    if warnings:
        print("\n  ⚠️  Suggestions:")
        for w in warnings:
            print(f"     • {w}")

    print()


def run_all(rescrape=False, open_browser=False):
    """Run full pipeline: scrape → mp3 → catalog."""
    print("=" * 60)
    print("🚀 Running full pipeline: scrape → mp3 → catalog")
    print("=" * 60 + "\n")

    # Step 1: Scrape
    print("── Step 1/3: Scraping bookmarks ──────────────────\n")
    try:
        run_scrape(rescrape=rescrape)
    except SystemExit as e:
        if e.code != 0:
            print(f"\n❌ Scrape failed (exit {e.code}), stopping pipeline.")
            raise

    # Step 2: MP3
    print("\n── Step 2/3: Extracting audio ────────────────────\n")
    try:
        run_mp3()
    except SystemExit as e:
        if e.code != 0:
            print(f"\n❌ Audio extraction failed (exit {e.code}), stopping pipeline.")
            raise

    # Step 3: Catalog
    print("\n── Step 3/3: Generating catalog ──────────────────\n")
    run_catalog(open_browser=open_browser)

    print("\n" + "=" * 60)
    print("✅ Pipeline complete!")
    print("=" * 60)


# ── CLI entry point ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Beat Digger X — Unified CLI for Twitter bookmark video downloading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python3 beat_digger.py scrape                  # download new videos
  python3 beat_digger.py scrape --rescrape       # force fresh download
  python3 beat_digger.py scrape --extract-audio  # download + extract MP3
  python3 beat_digger.py mp3                     # extract audio
  python3 beat_digger.py catalog --open          # generate + open catalog
  python3 beat_digger.py delete --dry-run        # preview deletions
  python3 beat_digger.py clear                   # clear bookmarks
  python3 beat_digger.py archive                 # init download archive
  python3 beat_digger.py status                  # show collection stats
  python3 beat_digger.py all                     # scrape → mp3 → catalog
  python3 beat_digger.py all --open              # pipeline + open catalog
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scrape
    p_scrape = subparsers.add_parser("scrape", help="Download new videos from Twitter bookmarks")
    p_scrape.add_argument("--rescrape", action="store_true", help="Force fresh download (ignores existing files)")
    p_scrape.add_argument("--extract-audio", action="store_true", help="Also extract MP3 audio after downloading")

    # mp3
    subparsers.add_parser("mp3", help="Extract audio from downloaded videos")

    # catalog
    p_catalog = subparsers.add_parser("catalog", help="Generate the interactive HTML catalog")
    p_catalog.add_argument("--open", action="store_true", help="Open the catalog in your browser after generating")

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete videos marked in the catalog")
    p_delete.add_argument("--dry-run", action="store_true", help="Preview what would be deleted without making changes")
    p_delete.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    p_delete.add_argument("--file", default=None, help="Selections JSON file (default: video_selections.json)")

    # clear
    p_clear = subparsers.add_parser("clear", help="Clear bookmarks from Twitter")
    p_clear.add_argument("--mode", choices=["manual", "auto"], default="manual", help="Unbookmark mode (default: manual)")
    p_clear.add_argument("--confirm", action="store_true", help="Confirm auto mode deletion (skips dry-run)")
    p_clear.add_argument("--batch-size", type=int, default=None, help="Number of tabs per batch in manual mode")
    p_clear.add_argument("--file", default=None, help="URL list file (default: to_unbookmark.csv)")

    # archive
    p_archive = subparsers.add_parser("archive", help="One-time backfill of download archive (for existing installs)")
    p_archive.add_argument("--dry-run", action="store_true", help="Preview keys without writing to the archive database")

    # status
    subparsers.add_parser("status", help="Show collection statistics")

    # all
    p_all = subparsers.add_parser("all", help="Run full pipeline: scrape → mp3 → catalog")
    p_all.add_argument("--rescrape", action="store_true", help="Force fresh download (ignores existing files)")
    p_all.add_argument("--open", action="store_true", help="Open the catalog in your browser after generating")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "scrape":
        run_scrape(rescrape=args.rescrape, extract_audio=args.extract_audio)
    elif args.command == "mp3":
        run_mp3()
    elif args.command == "catalog":
        run_catalog(open_browser=args.open)
    elif args.command == "delete":
        run_delete(dry_run=args.dry_run, yes=args.yes, file=args.file)
    elif args.command == "clear":
        run_clear(mode=args.mode, confirm=args.confirm, batch_size=args.batch_size, file=args.file)
    elif args.command == "archive":
        run_archive(dry_run=args.dry_run)
    elif args.command == "status":
        run_status()
    elif args.command == "all":
        run_all(rescrape=args.rescrape, open_browser=args.open)


if __name__ == "__main__":
    main()
