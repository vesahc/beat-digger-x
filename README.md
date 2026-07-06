# Beat Digger X 🎧⛏️

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A complete toolkit to mass-download videos from your Twitter/X bookmarks, extract the audio, and browse them through an interactive, sortable HTML catalog designed for music producers and sample diggers.

Originally built for sampling into hardware like the **Akai MPC**, it preserves the original video files while providing workflow tools to tag, sort, and manage your collection.

---

## ✨ Features

- **Direct Bookmark Scraping**: Uses `gallery-dl` to download all videos from your private Twitter bookmarks in one go.
- **Audio Extraction**: Converts video audio to high-quality 320kbps MP3 (or preferred format) for easy loading into samplers.
- **Interactive HTML Catalog**: Generates a sleek, dark-mode web page to browse your downloads.
  - Keep / Delete / Sampled checkboxes with mutual exclusion.
  - Clickable links to original tweets and local video files.
  - Real-time search, column sorting, and drag-and-drop column reordering.
  - Resizable columns and sticky headers.
  - Import/Export your tags and comments via JSON.
- **Bookmark Management**: Generate a cross-reference CSV of downloaded tweets and optionally clear them from your Twitter account.
- **Safe Resumption**: Checkpointing and file-skip logic allow you to stop and resume downloads without losing progress.

---

## 📦 Installation

### Prerequisites

| Tool | Install Command / Link |
|------|-----------------------|
| **Python 3.8+** | [python.org](https://python.org) |
| **FFmpeg** | macOS: `brew install ffmpeg` • Linux: `sudo apt install ffmpeg` |

### Setup

```bash
# Clone the repo
git clone https://github.com/vesahc/beat-digger-x.git
cd beat-digger-x

# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Usage

### 1. Export Cookies
Twitter bookmarks are private. You need to authenticate with cookies.

1. Install the [Get cookies.txt Locally](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) Chrome extension.
2. Log into `x.com` in your browser.
3. Click the extension and export cookies for the current domain.
4. Save the file as `cookies.txt` in the project directory.
5. Secure it: `chmod 600 cookies.txt`

### 2. Scrape & Download Videos

```bash
python3 scrape_bookmarks.py
```
Downloads all video media from your bookmarks to `downloads/video/twitter/[User]/`. Skips files you already have.

### 3. Generate the Interactive Catalog

```bash
python3 list_videos.py
```
Generates `video_list.html`. Open it in your browser to browse, tag, and manage your videos.

### 4. Extract Audio (Optional)

```bash
python3 download_bookmarks.py
```
Extracts audio from downloaded videos to `downloads/audio/` as 320kbps MP3s (MPC-compatible).

### 5. Clear Bookmarks (Optional)

```bash
python3 clear_bookmarks.py
```
Reads your cross-reference file and opens tweet URLs in browser batches for manual unbookmarking.

---

## 🔐 Security & Risk Notes

- **Treat `cookies.txt` like a password.** It grants full access to your account. It is included in `.gitignore` and should never be committed.
- **Ban Risk**: Scraping private bookmarks violates Twitter's ToS. This tool includes rate-limiting, but there is always a risk of temporary account locks. Use at your own discretion.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
