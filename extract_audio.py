#!/usr/bin/env python3
"""
Audio Extractor
Reads video files downloaded by scrape_bookmarks.py, extracts their .json metadata
sidecars for tweet URLs, converts audio to 320kbps MP3 for Akai MPC compatibility,
and generates a CSV cross-reference file for unbookmarking.

Input:  downloads/video/*.mp4 + downloads/video/*.json (metadata sidecars)
Output: downloads/audio/*.mp3, to_unbookmark.csv
"""

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ============== CONFIG ==============
VIDEO_DIR = Path("downloads/video")
AUDIO_DIR = Path("downloads/audio")
UNBOOKMARK_FILE = "to_unbookmark.csv"  # CSV for Excel/clickable links
AUDIO_TIMEOUT = 120
# =====================================


def ensure_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("❌ FFmpeg not found. Install it first:")
        print("   macOS:   brew install ffmpeg")
        print("   Linux:   sudo apt install ffmpeg")
        sys.exit(1)


def load_metadata(json_path):
    """Load gallery-dl metadata sidecar JSON."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  ⚠️  Could not read metadata: {e}")
        return None


def extract_tweet_url(metadata):
    """Extract tweet URL from gallery-dl metadata (checks multiple possible fields)."""
    if not metadata or not isinstance(metadata, dict):
        return None

    # gallery-dl stores tweet URL in various fields depending on version/config
    for key in ("tweet_url", "url", "source", "_tweet_url"):
        url = metadata.get(key)
        if url and "status" in str(url):
            return url

    # Try to reconstruct from tweet_id and uploader
    tweet_id = metadata.get("tweet_id") or metadata.get("id")
    uploader = metadata.get("uploader") or metadata.get("username") or metadata.get("user")
    if tweet_id and uploader:
        return f"https://x.com/{uploader}/status/{tweet_id}"

    return None


def find_video_files():
    """Find all video files in the video directory."""
    if not VIDEO_DIR.exists():
        print(f"❌ Video directory not found: {VIDEO_DIR}")
        print("   Run scrape_bookmarks.py first to download videos")
        sys.exit(1)

    extensions = ("*.mp4", "*.webm", "*.m4v", "*.mkv")
    videos = []
    for ext in extensions:
        videos.extend(VIDEO_DIR.rglob(ext))  # Recursive search

    # Filter out .json files that might match *.mp4.json etc
    videos = [v for v in videos if v.suffix in (".mp4", ".webm", ".m4v", ".mkv")]
    return sorted(videos)


def extract_mp3(video_path, metadata):
    """
    Extract audio to 320kbps MP3 for Akai MPC sampler compatibility.
    MPC supports WAV, MP3, AIFF, FLAC, OGG (NOT AAC/M4A).
    Source is 128kbps AAC; 320kbps MP3 provides transparent transcode with no audible loss.
    Returns (mp3_path, error).
    """
    if not video_path or not os.path.exists(video_path):
        return None, "Video file not found"

    # Build output filename in User-ID format from folder structure
    # gallery-dl saves as: downloads/video/twitter/[User]/[TweetID].mp4
    username = video_path.parent.name
    if username == "video" or username == "twitter":
        # Fallback if not in expected folder structure
        safe_name = video_path.stem
    else:
        # Clean up _1, _2 suffixes gallery-dl sometimes adds
        clean_stem = video_path.stem
        if clean_stem.endswith("_1") or clean_stem.endswith("_2"):
            clean_stem = clean_stem.rsplit("_", 1)[0]
        safe_name = f"{username}-{clean_stem}"
    
    mp3_path = AUDIO_DIR / f"{safe_name}.mp3"

    # Skip if MP3 already exists (resume capability)
    if mp3_path.exists():
        return str(mp3_path), None

    # Re-encode to MP3 320kbps at 44.1kHz (MPC standard sample rate)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", "320k",
        "-ar", "44100",
        str(mp3_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=AUDIO_TIMEOUT)
        if result.returncode == 0 and mp3_path.exists():
            return str(mp3_path), None
        stderr_tail = result.stderr[-300:] if result.stderr else "unknown"
        return None, f"FFmpeg MP3 encoding failed: {stderr_tail}"
    except subprocess.TimeoutExpired:
        return None, "Audio extraction timeout"
    except Exception as e:
        return None, str(e)


def get_video_duration(video_path):
    """Get video duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            seconds = float(result.stdout.strip())
            if seconds >= 3600:
                return f"{int(seconds // 3600)}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"
            return f"{int(seconds // 60)}:{int(seconds % 60):02d}"
    except Exception:
        pass
    return "Unknown"


def main():
    ensure_ffmpeg()

    # Create audio directory
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Find all video files
    videos = find_video_files()
    if not videos:
        print(f"❌ No video files found in {VIDEO_DIR}/")
        print("   Run scrape_bookmarks.py first to download videos")
        sys.exit(1)

    print(f"📋 Found {len(videos)} video files\n")

    # Initialize results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total": len(videos),
        "successful": [],
        "video_only": [],
        "failed": [],
        "skipped": [],
    }

    # Process each video
    for i, video_path in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] {video_path.name}")

        # Find matching metadata sidecar (.json with same base name)
        json_path = video_path.with_suffix(".json")
        if not json_path.exists():
            # Try alternative: some gallery-dl versions use .json extension appended
            alt_json = Path(str(video_path) + ".json")
            if alt_json.exists():
                json_path = alt_json

        metadata = None
        if json_path.exists():
            metadata = load_metadata(json_path)
        else:
            print(f"  ⚠️  No metadata sidecar found ({json_path.name})")

        # Extract tweet URL from metadata
        tweet_url = extract_tweet_url(metadata) if metadata else None

        if not tweet_url:
            print(f"  ❌ Could not extract tweet URL from metadata")
            results["failed"].append({
                "video_file": str(video_path),
                "error": "No tweet URL found in metadata",
                "timestamp": datetime.now().isoformat(),
            })
            continue

        # Extract metadata fields
        uploader = metadata.get("uploader") or metadata.get("username") or "Unknown" if metadata else "Unknown"
        title = metadata.get("title") or metadata.get("content") or metadata.get("description") or "Untitled"
        # Clean up title (remove newlines, truncate)
        title = str(title).replace("\n", " ").strip()[:100]
        description = metadata.get("content") or metadata.get("description") or "" if metadata else ""
        description = str(description).replace("\n", " ").strip()[:300]

        # Get duration
        duration = get_video_duration(video_path)

        print(f"  URL: {tweet_url}")
        print(f"  From: @{uploader}")

        # Extract MP3
        mp3_path, mp3_error = extract_mp3(video_path, metadata)

        if mp3_path:
            print(f"  ✅ MP3 extracted (320kbps)")
        else:
            print(f"  ⚠️  MP3 extraction failed: {mp3_error}")

        # Build result entry
        entry = {
            "url": tweet_url,
            "title": title,
            "uploader": uploader,
            "description": description,
            "duration": duration,
            "video_file": str(video_path),
            "audio_file": mp3_path,
            "timestamp": datetime.now().isoformat(),
        }

        if mp3_path:
            results["successful"].append(entry)
        else:
            entry["audio_error"] = mp3_error
            results["video_only"].append(entry)

    # Export cross-reference file for unbookmarking (CSV format)
    all_processed = results["successful"] + results["video_only"]
    if all_processed:
        with open(UNBOOKMARK_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["URL", "Video File", "Audio File", "Title", "Uploader"])
            for item in all_processed:
                writer.writerow([
                    item["url"],
                    item.get("video_file", ""),
                    item.get("audio_file", "") or "(extraction failed)",
                    item.get("title", "Unknown"),
                    item.get("uploader", "Unknown")
                ])

    # Summary
    print(f"\n{'=' * 60}")
    print(f"📊 COMPLETE")
    print(f"{'=' * 60}")
    print(f"✅ Video + MP3:  {len(results['successful'])}")
    print(f"📹 Video only:   {len(results['video_only'])}")
    print(f"❌ Failed:       {len(results['failed'])}")
    print(f"\n📄 File created:")
    if all_processed:
        print(f"   Unbookmark list: {UNBOOKMARK_FILE}")


if __name__ == "__main__":
    main()
