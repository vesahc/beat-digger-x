#!/usr/bin/env python3
"""
Generate a browsable HTML list of all downloaded videos with clickable tweet links,
comments, keep/delete/sampled checkboxes, local file links, and import/export.
Scans downloads/video/ for .mp4 files and their .json metadata sidecars.
"""

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

VIDEO_DIR = Path("downloads/video")
OUTPUT_FILE = "video_list.html"


def extract_tweet_url(metadata):
    if not metadata or not isinstance(metadata, dict):
        return None
    for key in ("tweet_url", "url", "source"):
        url = metadata.get(key)
        if url and "status" in str(url):
            return url
    tweet_id = metadata.get("tweet_id") or metadata.get("id")
    uploader = metadata.get("uploader") or metadata.get("username")
    if tweet_id and uploader:
        return f"https://x.com/{uploader}/status/{tweet_id}"
    if tweet_id:
        return f"https://x.com/i/status/{tweet_id}"
    return None


def main():
    if not VIDEO_DIR.exists():
        print(f"No downloads found at {VIDEO_DIR}")
        return

    videos = []
    for ext in ("*.mp4", "*.webm", "*.m4v"):
        videos.extend(VIDEO_DIR.rglob(ext))
    videos = [v for v in videos if v.suffix in (".mp4", ".webm", ".m4v")]
    videos.sort()

    if not videos:
        print("No video files found")
        return

    print(f"Found {len(videos)} video files")

    entries = []
    for v in videos:
        json_path = v.with_suffix(".json")
        if not json_path.exists():
            json_path = Path(str(v) + ".json")

        url = None
        username = v.parent.name if v.parent.name != "video" else "unknown"
        tweet_id = v.stem
        description = ""
        date_str = "Unknown"

        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                url = extract_tweet_url(meta)
                username = meta.get("uploader") or meta.get("username") or username
                description = meta.get("content") or meta.get("description") or ""
                description = str(description).replace("\n", " ").strip()[:200]
                
                # Extract date
                raw_date = meta.get("date") or meta.get("upload_date")
                if raw_date:
                    if isinstance(raw_date, (int, float)):
                        date_str = datetime.fromtimestamp(raw_date, tz=timezone.utc).strftime('%Y-%m-%d')
                    elif isinstance(raw_date, str):
                        # Handle YYYYMMDD format or ISO format
                        clean_date = raw_date.split("T")[0].split(" ")[0]
                        if clean_date.isdigit() and len(clean_date) == 8:
                            date_str = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}"
                        else:
                            date_str = clean_date
            except Exception:
                pass

        if not url:
            if username and username not in ("video", "twitter"):
                url = f"https://x.com/{username}/status/{tweet_id}"
            else:
                url = f"https://x.com/i/status/{tweet_id}"

        abs_path = v.resolve()

        entries.append({
            "url": url,
            "username": username,
            "tweet_id": tweet_id,
            "filename": v.name,
            "path": str(abs_path),
            "size_mb": round(v.stat().st_size / 1024 / 1024, 1),
            "description": description,
            "date": date_str,
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Downloaded Twitter Videos</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
h1 {{ color: #e94560; }}
.stats {{ color: #aaa; margin-bottom: 15px; }}
.stats span {{ color: #eee; font-weight: bold; }}
.toolbar {{ margin-bottom: 15px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.btn {{ background: #16213e; color: #e94560; border: 1px solid #e94560; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
.btn:hover {{ background: #e94560; color: #fff; }}
.btn.active {{ background: #e94560; color: #fff; }}
.btn-delete {{ border-color: #ff4444; color: #ff4444; }}
.btn-delete:hover {{ background: #ff4444; color: #fff; }}
.btn-delete.active {{ background: #ff4444; color: #fff; }}
.btn-sampled {{ border-color: #00cc66; color: #00cc66; }}
.btn-sampled:hover {{ background: #00cc66; color: #fff; }}
.btn-sampled.active {{ background: #00cc66; color: #fff; }}
.btn-import {{ border-color: #4da6ff; color: #4da6ff; }}
.btn-import:hover {{ background: #4da6ff; color: #fff; }}
table {{ border-collapse: separate; border-spacing: 0; width: 100%; table-layout: fixed; }}
th {{ background: #16213e; padding: 10px; text-align: left; position: sticky; top: 0; z-index: 10; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 60px; cursor: pointer; user-select: none; }}
th:hover {{ background: #1a1a2e; }}
td {{ padding: 8px; border-bottom: 1px solid #333; vertical-align: top; overflow: hidden; text-overflow: ellipsis; }}
tr:hover {{ background: #16213e; }}
a {{ color: #e94560; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.size {{ color: #aaa; font-size: 0.9em; }}
.user {{ color: #0f3460; background: #e94560; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; white-space: nowrap; }}
.desc {{ color: #888; font-size: 0.85em; }}
.comment {{ width: 100%; background: #16213e; color: #eee; border: 1px solid #333; border-radius: 4px; padding: 4px 6px; font-size: 13px; box-sizing: border-box; }}
.comment:focus {{ border-color: #e94560; outline: none; }}
.keep {{ width: 20px; height: 20px; cursor: pointer; accent-color: #e94560; }}
.del {{ width: 20px; height: 20px; cursor: pointer; accent-color: #ff4444; }}
.sampled {{ width: 20px; height: 20px; cursor: pointer; accent-color: #00cc66; }}
.row-kept {{ background: rgba(233, 69, 96, 0.08); }}
.row-deleted {{ opacity: 0.65; }}
.row-deleted:hover {{ background: rgba(255, 68, 68, 0.08); }}
.row-sampled {{ background: rgba(0, 204, 102, 0.08); }}
.col-resizer {{ position: absolute; right: 0; top: 0; height: 100%; width: 5px; cursor: col-resize; user-select: none; z-index: 11; }}
.col-resizer:hover {{ background: #e94560; }}
</style>
</head>
<body>
<h1>Downloaded Twitter Videos ({len(entries)} total)</h1>
<p class="stats">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | <span id="keptCount">0</span> kept | <span id="sampledCount">0</span> sampled | <span id="deletedCount">0</span> deleted</p>

<div class="toolbar">
  <button class="btn active" onclick="filterRows('all')" id="btn-all">All</button>
  <button class="btn" onclick="filterRows('kept')" id="btn-kept">Kept</button>
  <button class="btn btn-sampled" onclick="filterRows('sampled')" id="btn-sampled">Sampled</button>
  <button class="btn btn-delete" onclick="filterRows('deleted')" id="btn-deleted">Deleted</button>
  <button class="btn" onclick="filterRows('unkept')" id="btn-unkept">Unsorted</button>
  <input type="text" id="searchInput" onkeyup="filterRows(currentFilter)" placeholder="Search user, file, description..." style="background: #16213e; color: #eee; border: 1px solid #333; border-radius: 6px; padding: 8px 12px; font-size: 14px; width: 250px;">
  <button class="btn" onclick="exportData()">Export JSON</button>
  <button class="btn btn-import" onclick="document.getElementById('importFile').click()">Import JSON</button>
  <input type="file" id="importFile" accept=".json" style="display:none" onchange="importData(event)">
</div>

<table id="videoTable">
<tr>
  <th style="width:50px" draggable="true" onclick="sortTable(this.cellIndex)">Keep</th>
  <th style="width:50px" draggable="true" onclick="sortTable(this.cellIndex)">Del</th>
  <th style="width:50px" draggable="true" onclick="sortTable(this.cellIndex)">Done</th>
  <th style="width:50px" draggable="true" onclick="sortTable(this.cellIndex)">#</th>
  <th style="width:120px" draggable="true" onclick="sortTable(this.cellIndex)">User</th>
  <th style="width:100px" draggable="true" onclick="sortTable(this.cellIndex)">Date</th>
  <th style="width:200px" draggable="true" onclick="sortTable(this.cellIndex)">File</th>
  <th style="width:120px" draggable="true" onclick="sortTable(this.cellIndex)">Tweet</th>
  <th style="width:300px" draggable="true" onclick="sortTable(this.cellIndex)">Description</th>
  <th style="width:80px" draggable="true" onclick="sortTable(this.cellIndex)">Size</th>
  <th style="width:200px" draggable="true" onclick="sortTable(this.cellIndex)">Comments</th>
</tr>
""")

        for i, e in enumerate(entries, 1):
            safe_id = html.escape(e["tweet_id"])
            f.write(f"""<tr id="row-{safe_id}" data-kept="false" data-deleted="false" data-sampled="false">
<td style="text-align:center;"><input type="checkbox" class="keep" id="keep-{safe_id}" onchange="toggleKeep('{safe_id}')"></td>
<td style="text-align:center;"><input type="checkbox" class="del" id="del-{safe_id}" onchange="toggleDelete('{safe_id}')"></td>
<td style="text-align:center;"><input type="checkbox" class="sampled" id="sampled-{safe_id}" onchange="toggleSampled('{safe_id}')"></td>
<td>{i}</td>
<td><span class="user">@{html.escape(e['username'])}</span></td>
<td class="size">{html.escape(e['date'])}</td>
<td><a href="file://{html.escape(e['path'])}" title="{html.escape(e['path'])}">{html.escape(e['filename'])}</a></td>
<td><a href="{html.escape(e['url'])}" target="_blank">{safe_id}</a></td>
<td class="desc">{html.escape(e['description'])}</td>
<td class="size">{e['size_mb']} MB</td>
<td><input type="text" class="comment" id="comment-{safe_id}" placeholder="Add note..." oninput="saveComment('{safe_id}')"></td>
</tr>\n""")

        f.write("""</table>

<script>
function loadState() {
  try { return JSON.parse(localStorage.getItem('mpcVideoState') || '{}'); }
  catch(e) { return {}; }
}
function saveState(state) {
  localStorage.setItem('mpcVideoState', JSON.stringify(state));
}

let state = loadState();
let currentFilter = 'all';

function applyState() {
  let k=0, s=0, d=0;
  
  document.querySelectorAll('.keep').forEach(cb => {
    const id = cb.id.replace('keep-','');
    const v = (state[id] && state[id].kept) || false;
    cb.checked = v;
    const r = document.getElementById('row-'+id);
    if (r) {
      if (v) { k++; r.classList.add('row-kept'); r.setAttribute('data-kept','true'); }
      else { r.classList.remove('row-kept'); r.setAttribute('data-kept','false'); }
    }
  });
  
  document.querySelectorAll('.sampled').forEach(cb => {
    const id = cb.id.replace('sampled-','');
    const v = (state[id] && state[id].sampled) || false;
    cb.checked = v;
    const r = document.getElementById('row-'+id);
    if (r) {
      if (v) { s++; r.classList.add('row-sampled'); r.setAttribute('data-sampled','true'); }
      else { r.classList.remove('row-sampled'); r.setAttribute('data-sampled','false'); }
    }
  });
  
  document.querySelectorAll('.del').forEach(cb => {
    const id = cb.id.replace('del-','');
    const v = (state[id] && state[id].deleted) || false;
    cb.checked = v;
    const r = document.getElementById('row-'+id);
    if (r) {
      if (v) { d++; r.classList.add('row-deleted'); r.setAttribute('data-deleted','true'); }
      else { r.classList.remove('row-deleted'); r.setAttribute('data-deleted','false'); }
    }
  });
  
  document.querySelectorAll('.comment').forEach(input => {
    const id = input.id.replace('comment-','');
    if (state[id] && state[id].comment) input.value = state[id].comment;
  });
  
  document.getElementById('keptCount').textContent = k;
  document.getElementById('sampledCount').textContent = s;
  document.getElementById('deletedCount').textContent = d;
}

function toggleKeep(id) {
  if(!state[id]) state[id]={};
  state[id].kept = document.getElementById('keep-'+id).checked;
  if(state[id].kept && state[id].deleted) {
    state[id].deleted=false;
    document.getElementById('del-'+id).checked=false;
    const r=document.getElementById('row-'+id);
    r.classList.remove('row-deleted'); r.setAttribute('data-deleted','false');
  }
  saveState(state);
  const r=document.getElementById('row-'+id);
  if(state[id].kept){r.classList.add('row-kept');r.setAttribute('data-kept','true');}
  else{r.classList.remove('row-kept');r.setAttribute('data-kept','false');}
  updateCounts(); filterRows(currentFilter);
}

function toggleDelete(id) {
  if(!state[id]) state[id]={};
  state[id].deleted = document.getElementById('del-'+id).checked;
  if(state[id].deleted && state[id].kept) {
    state[id].kept=false;
    document.getElementById('keep-'+id).checked=false;
    const r=document.getElementById('row-'+id);
    r.classList.remove('row-kept'); r.setAttribute('data-kept','false');
  }
  saveState(state);
  const r=document.getElementById('row-'+id);
  if(state[id].deleted){r.classList.add('row-deleted');r.setAttribute('data-deleted','true');}
  else{r.classList.remove('row-deleted');r.setAttribute('data-deleted','false');}
  updateCounts(); filterRows(currentFilter);
}

function toggleSampled(id) {
  if(!state[id]) state[id]={};
  state[id].sampled = document.getElementById('sampled-'+id).checked;
  saveState(state);
  const r=document.getElementById('row-'+id);
  if(state[id].sampled){r.classList.add('row-sampled');r.setAttribute('data-sampled','true');}
  else{r.classList.remove('row-sampled');r.setAttribute('data-sampled','false');}
  updateCounts(); filterRows(currentFilter);
}

function updateCounts() {
  document.getElementById('keptCount').textContent = Object.values(state).filter(s=>s.kept).length;
  document.getElementById('sampledCount').textContent = Object.values(state).filter(s=>s.sampled).length;
  document.getElementById('deletedCount').textContent = Object.values(state).filter(s=>s.deleted).length;
}

function saveComment(id) {
  if(!state[id]) state[id]={};
  state[id].comment = document.getElementById('comment-'+id).value;
  saveState(state);
}

function filterRows(mode) {
  currentFilter = mode;
  document.querySelectorAll('.toolbar .btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('btn-'+mode);
  if(btn) btn.classList.add('active');
  
  const searchText = document.getElementById('searchInput').value.toLowerCase();
  
  document.querySelectorAll('#videoTable tr').forEach(row => {
    if(row.id && row.id.startsWith('row-')) {
      const kept = row.getAttribute('data-kept')==='true';
      const deleted = row.getAttribute('data-deleted')==='true';
      const sampled = row.getAttribute('data-sampled')==='true';
      
      // Check filter mode
      let modeMatch = true;
      if(mode==='all') modeMatch = true;
      else if(mode==='kept') modeMatch = kept;
      else if(mode==='sampled') modeMatch = sampled;
      else if(mode==='deleted') modeMatch = deleted;
      else if(mode==='unkept') modeMatch = (!kept && !deleted && !sampled);
      
      // Check search text
      let searchMatch = true;
      if (searchText) {
        searchMatch = row.textContent.toLowerCase().includes(searchText);
      }
      
      // Show row only if both filter and search match
      row.style.display = (modeMatch && searchMatch) ? '' : 'none';
    }
  });
}

function exportData() {
  const data = [];
  Object.entries(state).forEach(([id,s]) => {
    if(s.kept||s.deleted||s.sampled||s.comment)
      data.push({tweet_id:id,kept:s.kept||false,deleted:s.deleted||false,sampled:s.sampled||false,comment:s.comment||''});
  });
  const blob = new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'video_selections.json';
  a.click();
}

function importData(event) {
  const file = event.target.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const data = JSON.parse(e.target.result);
      data.forEach(item => {
        if(!state[item.tweet_id]) state[item.tweet_id] = {};
        state[item.tweet_id].kept = item.kept || false;
        state[item.tweet_id].deleted = item.deleted || false;
        state[item.tweet_id].sampled = item.sampled || false;
        state[item.tweet_id].comment = item.comment || '';
      });
      saveState(state);
      applyState();
      alert('Imported successfully!');
    } catch(err) {
      alert('Import failed: ' + err.message);
    }
  };
  reader.readAsText(file);
}

// Column resizer
document.querySelectorAll('th').forEach(function(th) {
  const resizer = document.createElement('div');
  resizer.className = 'col-resizer';
  th.appendChild(resizer);
  let startX, startWidth;
  resizer.addEventListener('mousedown', function(e) {
    startX = e.clientX;
    startWidth = th.offsetWidth;
    document.addEventListener('mousemove', resize);
    document.addEventListener('mouseup', stopResize);
    e.preventDefault();
    e.stopPropagation();
  });
  function resize(e) {
    const newWidth = Math.max(50, startWidth + (e.clientX - startX));
    th.style.width = newWidth + 'px';
    th.style.minWidth = newWidth + 'px';
    th.style.maxWidth = newWidth + 'px';
  }
  function stopResize() {
    document.removeEventListener('mousemove', resize);
    document.removeEventListener('mouseup', stopResize);
  }
});

// Sort table by column
let sortDir = {};
function sortTable(colIdx) {
  const table = document.getElementById('videoTable');
  const rows = Array.from(table.querySelectorAll('tr')).slice(1);
  
  // Toggle direction. Default to descending for Date(5), Size(9), #(3)
  if (sortDir[colIdx] === undefined) {
    sortDir[colIdx] = (colIdx === 3 || colIdx === 5 || colIdx === 9) ? false : true;
  } else {
    sortDir[colIdx] = !sortDir[colIdx];
  }
  const dir = sortDir[colIdx];
  
  rows.sort((a, b) => {
    let aVal = a.cells[colIdx].innerText.trim();
    let bVal = b.cells[colIdx].innerText.trim();
    
    // Size column (contains 'MB')
    if (aVal.includes('MB') && bVal.includes('MB')) {
      const aNum = parseFloat(aVal);
      const bNum = parseFloat(bVal);
      return dir ? aNum - bNum : bNum - aNum;
    }
    
    // Numeric sort (for # column)
    if (!isNaN(aVal) && !isNaN(bVal) && aVal !== '' && bVal !== '') {
      return dir ? parseFloat(aVal) - parseFloat(bVal) : parseFloat(bVal) - parseFloat(aVal);
    }
    
    // String sort (explicit comparison for reliable YYYY-MM-DD sorting)
    if (dir) {
      return aVal < bVal ? -1 : (aVal > bVal ? 1 : 0);
    } else {
      return aVal < bVal ? 1 : (aVal > bVal ? -1 : 0);
    }
  });
  
  rows.forEach(r => table.appendChild(r));
}

// Column drag-and-drop reordering
let dragColIdx = null;
document.querySelectorAll('th').forEach(function(th) {
  th.addEventListener('dragstart', function(e) {
    dragColIdx = th.cellIndex;
    e.dataTransfer.effectAllowed = 'move';
  });
  th.addEventListener('dragover', function(e) {
    e.preventDefault();
  });
  th.addEventListener('drop', function(e) {
    e.preventDefault();
    const targetIdx = th.cellIndex;
    if (dragColIdx !== null && dragColIdx !== targetIdx) {
      const table = document.getElementById('videoTable');
      const rows = table.querySelectorAll('tr');
      rows.forEach(function(row) {
        const cells = row.querySelectorAll('td, th');
        if (cells.length > Math.max(dragColIdx, targetIdx)) {
          const draggedCell = cells[dragColIdx];
          const targetCell = cells[targetIdx];
          // Swap cells
          const temp = document.createElement('td');
          row.insertBefore(temp, draggedCell);
          row.insertBefore(draggedCell, targetCell);
          row.insertBefore(targetCell, temp);
          row.removeChild(temp);
        }
      });
    }
    dragColIdx = null;
  });
});

applyState();
</script>
</body>
</html>""")

    print(f"Generated {OUTPUT_FILE} with {len(entries)} videos")
    print(f"Features: Keep/Delete/Sampled checkboxes, comments, file links, filters, import/export, column resize")


if __name__ == "__main__":
    main()
""