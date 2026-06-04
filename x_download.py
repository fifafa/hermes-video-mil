#!/usr/bin/env python3
"""
军事视频搬运 — X (Twitter) 增量下载脚本
用法: python3 x_download.py [--since-hours 24]
"""

import os, sys, json, re, argparse, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 配置 ──
COOKIE_FILE = "/root/.hermes/cookies/X_cookies.txt"
ARCHIVE_FILE = "/root/hermes_video/.x_archive.txt"
OUTPUT_DIR = "/root/hermes_video/X"
LOG_FILE = "/root/hermes_video/.x_log.json"

# 5 个军事/装备分析头部账号
ACCOUNTS = [
    "Osinttechnical",      # OSINT / 战场分析
    "RALee85",             # 俄军装备
    "UAWeapons",           # 武器分析
    "oryxspioenkop",       # 装备损失追踪
    "COUPSURE",            # 国防科技
]

YTDLP = "yt-dlp"
SINCE_HOURS = 24
MAX_VIDEOS_PER_ACCOUNT = 3  # 每次每个账号最多下载3条

# ── 工具函数 ──
def run(cmd, timeout=120):
    """运行shell命令，返回 (stdout, stderr, exit_code)"""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def load_archive():
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_archive(archive_set):
    os.makedirs(os.path.dirname(ARCHIVE_FILE), exist_ok=True)
    with open(ARCHIVE_FILE, "w") as f:
        for vid in sorted(archive_set):
            f.write(f"{vid}\n")

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {"runs": []}

def save_log(log):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

def log_entry(status, account, title="", url="", filename=""):
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "account": account,
        "title": title,
        "url": url,
        "filename": filename,
    }

# ── 扫描账号 ──
def scan_account(account, since_hours):
    """用 yt-dlp 扫描账号最近推文中的视频，返回视频URL列表"""
    url = f"https://x.com/{account}"
    cmd = (
        f'{YTDLP} --cookies {COOKIE_FILE} '
        f'--flat-playlist --dump-json '
        f'--dateafter now-{since_hours}hours '
        f'--playlist-end 30 '
        f'"{url}"'
    )
    out, err, code = run(cmd, timeout=60)
    if code != 0:
        if "login" in err.lower() or "unauthorized" in err.lower():
            return [], "cookie_expired"
        return [], err[:200]
    
    entries = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            entries.append(entry)
        except json.JSONDecodeError:
            pass
    
    # 筛选视频推文
    videos = []
    for e in entries:
        eid = e.get("id", "")
        duration = e.get("duration") or 0
        # X 推文有视频如果 duration > 0 或 formats 存在
        if duration > 0 or e.get("_type") == "video":
            videos.append({
                "id": eid,
                "url": f"https://x.com/{account}/status/{eid}",
                "title": (e.get("title") or e.get("description") or f"@{account}_{eid}")[:120],
                "duration": duration,
                "timestamp": e.get("timestamp"),
            })
    
    return videos, None

# ── 下载 ──
def download_video(video, archive_set):
    """下载单条视频，返回 (filename, success)"""
    vid = video["id"]
    if vid in archive_set:
        return None, "skipped"
    
    account = video["url"].split("/")[3]  # x.com/ACCOUNT/status/ID
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', video["title"])[:80]
    template = f"{OUTPUT_DIR}/%(uploader)s_%(id)s_{safe_title}.%(ext)s"
    
    cmd = (
        f'{YTDLP} --cookies {COOKIE_FILE} '
        f'-f "best[height<=1080]" '
        f'--download-archive {ARCHIVE_FILE} '
        f'-o "{template}" '
        f'--no-playlist '
        f'--max-filesize 500M '
        f'"{video["url"]}"'
    )
    out, err, code = run(cmd, timeout=300)
    
    if code == 0:
        # 找到下载的文件名
        for line in (out + err).split("\n"):
            if "[download] Destination:" in line:
                filename = line.split("Destination:")[-1].strip()
                return filename, "downloaded"
            if "has already been recorded" in line:
                return None, "skipped"
        # 兜底找文件
        recent = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if recent:
            return str(recent[0]), "downloaded"
        return None, "unknown"
    else:
        return None, f"error: {err[:150]}"

# ── 主流程 ──
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=SINCE_HOURS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    archive = load_archive()
    log_data = load_log()
    
    run_entries = []
    total_downloaded = 0
    total_scanned = 0
    
    print(f"🪖 军事视频X源扫描 | 回溯 {args.since_hours}h | {datetime.now().strftime('%H:%M')}")
    print(f"   账号数: {len(ACCOUNTS)} | 存量: {len(archive)} 条\n")
    
    for account in ACCOUNTS:
        print(f"  🔍 @{account} ...", end=" ", flush=True)
        videos, err = scan_account(account, args.since_hours)
        
        if err:
            print(f"❌ {err[:60]}")
            run_entries.append(log_entry("scan_error", account, title=err[:200]))
            continue
        
        print(f"{len(videos)} 条")
        total_scanned += len(videos)
        
        for v in videos[:MAX_VIDEOS_PER_ACCOUNT]:
            if args.dry_run:
                print(f"    🎬 {v['title'][:60]}")
                continue
            
            print(f"    ⬇ {v['title'][:60]} ...", end=" ", flush=True)
            filename, status = download_video(v, archive)
            
            if status == "downloaded":
                archive.add(v["id"])
                total_downloaded += 1
                print(f"✅ {(os.path.basename(filename) if filename else 'OK')}")
            elif status == "skipped":
                print("⏭ 已存在")
            else:
                print(f"❌ {status}")
            
            run_entries.append(log_entry(status, account, title=v["title"], url=v["url"], filename=filename or ""))
    
    save_archive(archive)
    log_data["runs"].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "since_hours": args.since_hours,
        "scanned": total_scanned,
        "downloaded": total_downloaded,
        "archive_size": len(archive),
        "entries": run_entries,
    })
    save_log(log_data)
    
    print(f"\n✅ 完成 | 扫描 {total_scanned} | 下载 {total_downloaded} | 存量 {len(archive)}")

if __name__ == "__main__":
    main()
