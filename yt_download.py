#!/usr/bin/env python3
"""
军事视频搬运 — YouTube 增量下载脚本
策略: 先试 web+cookie, 失败则退到 android client (绕过n-sig)
"""

import os, sys, json, re, argparse, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

COOKIE_FILE = "/root/.hermes/cookies/youtube_cookies.txt"
ARCHIVE_FILE = "/root/hermes_video/.yt_archive.txt"
OUTPUT_DIR = "/root/hermes_video/YouTube"
LOG_FILE = "/root/hermes_video/.yt_log.json"

# 5 个军事/装备分析头部频道
CHANNELS = [
    "https://www.youtube.com/@PerunAU",              # 国防经济学
    "https://www.youtube.com/@CovertCabal",          # 军事分析
    "https://www.youtube.com/@Binkov",               # 军力对比
    "https://www.youtube.com/@Taskandpurpose",       # 军事科技
    "https://www.youtube.com/@WardCarroll",          # 军事航空 (前F-14 RIO)
]

YTDLP = "yt-dlp --js-runtime node --remote-components ejs:github"
SINCE_HOURS = 24
MAX_VIDEOS_PER_CHANNEL = 3

def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_archive(s):
    os.makedirs(os.path.dirname(ARCHIVE_FILE), exist_ok=True)
    with open(ARCHIVE_FILE, "w") as f:
        for vid in sorted(s):
            f.write(f"{vid}\n")

def scan_channel(url, since_hours):
    """扫描频道最近视频"""
    from datetime import datetime, timedelta
    since_date = (datetime.now() - timedelta(hours=since_hours)).strftime("%Y%m%d")
    cmd = (
        f"{YTDLP} --flat-playlist --dump-json "
        f"--dateafter {since_date} "
        f"--playlist-end 20 "
        f'"{url}/videos"'
    )
    out, err, code = run(cmd, timeout=60)
    if code != 0:
        return [], err[:200]
    
    videos = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            dur = e.get("duration") or 0
            if dur > 60:  # >1分钟
                videos.append({
                    "id": e.get("id", ""),
                    "url": e.get("webpage_url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                    "title": (e.get("title") or "")[:150],
                    "duration": dur,
                    "channel": e.get("channel") or e.get("uploader") or "",
                })
        except json.JSONDecodeError:
            pass
    return videos, None

def download_video(video, archive_set):
    """下载: web+cookie → 失败 → android 绕过"""
    vid = video["id"]
    if vid in archive_set:
        return None, "skipped"
    
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', video["title"])[:80]
    
    # 策略1: web client + cookies
    template = f"{OUTPUT_DIR}/%(channel)s_%(id)s_{safe_title}.%(ext)s"
    cmd1 = (
        f'{YTDLP} --cookies {COOKIE_FILE} '
        f'-f "best[height<=1080]" '
        f'--download-archive {ARCHIVE_FILE} '
        f'-o "{template}" '
        f'--max-filesize 1G '
        f'--no-playlist '
        f'"{video["url"]}"'
    )
    out, err, code = run(cmd1, timeout=300)
    
    if code == 0:
        for line in (out + err).split("\n"):
            if "[download] Destination:" in line:
                return line.split("Destination:")[-1].strip(), "downloaded"
        recent = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)
        return (str(recent[0]), "downloaded") if recent else (None, "unknown")
    
    # 策略2: android client (绕过 n-sig)
    cmd2 = (
        f'{YTDLP} '
        f'--extractor-args "youtube:player_client=android" '
        f'-f "best[height<=1080]" '
        f'--download-archive {ARCHIVE_FILE} '
        f'-o "{template}" '
        f'--max-filesize 1G '
        f'--no-playlist '
        f'"{video["url"]}"'
    )
    out2, err2, code2 = run(cmd2, timeout=300)
    
    if code2 == 0:
        for line in (out2 + err2).split("\n"):
            if "[download] Destination:" in line:
                return line.split("Destination:")[-1].strip(), "downloaded"
        recent = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)
        return (str(recent[0]), "downloaded_fallback") if recent else (None, "unknown")
    
    return None, f"both methods failed: {err[:150]}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=SINCE_HOURS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    archive = load_archive()
    
    total_down = 0
    total_scan = 0
    print(f"🎬 YouTube 军事频道扫描 | 回溯 {args.since_hours}h\n")
    
    for url in CHANNELS:
        name = url.split("@")[-1][:25]
        print(f"  🔍 {name} ...", end=" ", flush=True)
        videos, err = scan_channel(url, args.since_hours)
        
        if err:
            print(f"❌ {err[:60]}")
            continue
        
        print(f"{len(videos)} 条")
        total_scan += len(videos)
        
        for v in videos[:MAX_VIDEOS_PER_CHANNEL]:
            if args.dry_run:
                print(f"    🎬 {v['title'][:60]}")
                continue
            
            print(f"    ⬇ {v['title'][:50]} ...", end=" ", flush=True)
            filename, status = download_video(v, archive)
            
            if status.startswith("downloaded"):
                archive.add(v["id"])
                total_down += 1
                print(f"✅ {'(fallback)' if 'fallback' in status else ''}")
            elif status == "skipped":
                print("⏭ 已存在")
            else:
                print(f"❌ {status[:60]}")
    
    save_archive(archive)
    print(f"\n✅ 完成 | 扫描 {total_scan} | 下载 {total_down} | 存量 {len(archive)}")

if __name__ == "__main__":
    main()
