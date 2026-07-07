#!/usr/bin/env python3
"""
Twitter Bookmark Video Scraper & Downloader
Uses gallery-dl to download all video media from your Twitter/X bookmarks directly.
Downloads MP4 files with tweet metadata (.json) sidecars.

Output: downloads/video/twitter/[User]/[TweetID].mp4 + .json
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ============== CONFIG ==============
COOKIES_FILE = "cookies.txt"
VIDEO_DIR = Path("downloads/video")
SKIP_LOG = "skipped_tweets.log"
FULL_LOG = "scrape_full.log"
ARCHIVE_FILE = ".archive.sqlite3"
# =====================================


def ensure_gallery_dl():
    result = subprocess.run(["which", "gallery-dl"], capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ gallery-dl not found. Run: pip install gallery-dl")
        sys.exit(1)


def ensure_cookies():
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ Cookies file not found: {COOKIES_FILE}")
        print("\nTo export your Twitter cookies:")
        print("   1. Install 'Get cookies.txt Locally' Chrome extension")
        print("   2. Log into Twitter/X in your browser")
        print("   3. Use the extension to export cookies from x.com")
        print(f"   4. Save the file as {COOKIES_FILE} in this directory")
        sys.exit(1)


def download_videos():
    """Download the actual video files from bookmarks."""
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "gallery-dl",
        "--cookies", COOKIES_FILE,
        "--download-archive", ARCHIVE_FILE,  # Skip already-downloaded/deleted videos
        "--write-metadata",          # Save .json metadata sidecars
        "--filter", "extension in ('mp4', 'webm', 'm4v')",  # Videos only
        "--filesize-max", "100M",     # Skip files larger than 100MB (doesn't abort run)
        "-d", str(VIDEO_DIR.resolve()),  # Absolute path
        "https://twitter.com/i/bookmarks",
    ]

    print("📥 Downloading video files from bookmarks...")
    print("   Each video will be saved to downloads/video/twitter/[User]/")
    print("   Metadata files (.json) will be saved alongside each video.")
    print("   gallery-dl will skip files you already have.")
    print("   Large videos (>100MB) and errors will be logged to skipped_tweets.log\n")

    skip_count = 0
    
    try:
        # Open log files
        with open(FULL_LOG, "w", encoding="utf-8") as full_log, \
             open(SKIP_LOG, "w", encoding="utf-8") as skip_log:
            
            skip_log.write(f"# Skipped/Errored Tweets Log\n")
            skip_log.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            skip_log.flush()  # Flush header immediately
            
            # Run gallery-dl with real-time output streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line-buffered output
            )
            
            # Use readline() for true real-time reading (not buffered iteration)
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                line = line.rstrip()
                if not line:
                    continue
                    
                # Print to console
                print(line, flush=True)
                
                # Write to full log
                full_log.write(line + "\n")
                full_log.flush()
                
                # Check for warnings/errors and log to skip file
                if "[warning]" in line or "[error]" in line or "Error" in line or "larger than" in line or "too large" in line:
                    # Try to extract tweet ID from the line
                    tweet_id_match = re.search(r'(\d{15,})', line)
                    if tweet_id_match:
                        tweet_id = tweet_id_match.group(1)
                        url = f"https://x.com/i/status/{tweet_id}"
                        skip_log.write(f"{url}\t{line}\n")
                    else:
                        skip_log.write(f"{line}\n")
                    skip_log.flush()
                    skip_count += 1
            
            process.wait(timeout=3600)
            
        if process.returncode != 0:
            print(f"\n⚠️  gallery-dl completed with warnings or errors.")
        else:
            print("\n✅ Downloads complete.")
            
        if skip_count > 0:
            print(f"📝 {skip_count} skipped/errored tweets logged to {SKIP_LOG}")
            
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Download timed out after 60 minutes")
        print("   You may have too many bookmarks. Some files were downloaded.")
        return False


def count_results():
    """Count downloaded videos and metadata files."""
    videos = list(VIDEO_DIR.rglob("*.mp4")) + list(VIDEO_DIR.rglob("*.webm")) + list(VIDEO_DIR.rglob("*.m4v"))
    metadata = list(VIDEO_DIR.rglob("*.json"))
    return len(videos), len(metadata)


def main():
    ensure_gallery_dl()
    ensure_cookies()

    # Check if videos already exist (resume capability)
    existing_videos, _ = count_results()
    if existing_videos > 0 and "--rescrape" not in sys.argv:
        print(f"📁 Found {existing_videos} existing video files in {VIDEO_DIR}/")
        print(f"   gallery-dl will skip these and only download new ones.")
        print(f"   Pass --rescrape to force a fresh download (ignores existing files).\n")

    # Download videos
    download_videos()

    # Count results
    video_count, meta_count = count_results()

    print(f"\n{'=' * 60}")
    print(f"📊 COMPLETE")
    print(f"{'=' * 60}")
    print(f"📹 Videos downloaded: {video_count}")
    print(f"📄 Metadata files:   {meta_count}")
    print(f"📁 Location:          {VIDEO_DIR}/")
    print(f"\n🚀 Next step: Run beat_digger.py mp3 to extract MP3 audio")


if __name__ == "__main__":
    main()
