#!/usr/bin/env python3
"""
军事视频搬运 — X (Twitter) 下载脚本 v2.0
使用 gallery-dl 替代 yt-dlp（yt-dlp 2026.03 已移除 Twitter extractor）
"""
import os, sys, re, json, argparse, subprocess, glob
from datetime import datetime, timedelta, timezone
from pathlib import Path

COOKIE_FILE = "/root/.hermes/cookies/X_cookies.txt"
ARCHIVE_FILE = "/root/hermes_video/.x_archive.txt"
OUTPUT_DIR = "/root/hermes_video/X"
GALLERY_CACHE = "/root/hermes_video/.gallery-dl-cache"

ACCOUNTS = [
    "Osinttechnical",
    "RALee85",
    "UAWeapons",
    "oryxspioenkop",
    "COUPSURE",
]

MAX_PER_ACCOUNT = 3
SINCE_HOURS = 24


def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def load_archive():
    """加载已下载 tweet ID 集合"""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE) as f:
            return set(line.strip().split()[0] for line in f if line.strip())
    return set()


def save_archive(archive_set):
    os.makedirs(os.path.dirname(ARCHIVE_FILE), exist_ok=True)
    with open(ARCHIVE_FILE, "w") as f:
        for tid in sorted(archive_set):
            f.write(f"{tid}\n")


def scan_and_download(account, archive, max_items=MAX_PER_ACCOUNT):
    """
    用 gallery-dl 扫描并下载账号 media timeline
    gallery-dl 自动处理认证、限流、下载
    
    文件命名: {OUTPUT_DIR}/twitter/{account}/{tweet_id}_{index}.mp4
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GALLERY_CACHE, exist_ok=True)
    
    cmd = (
        f"gallery-dl --cookies {COOKIE_FILE} "
        f"-d {OUTPUT_DIR} "
        f"--cache-dir {GALLERY_CACHE} "
        f"--range 1-{max_items * 3} "  # 多取一些，视频混在图片里
        f'"https://x.com/{account}/media"'
    )
    
    out, err, code = run(cmd, timeout=120)
    
    # gallery-dl 下载文件到: {OUTPUT_DIR}/twitter/{account}/{tweet_id}_{idx}.{ext}
    dl_dir = os.path.join(OUTPUT_DIR, "twitter", account)
    
    downloaded = []
    if os.path.exists(dl_dir):
        for f in sorted(Path(dl_dir).glob("*.mp4"), key=os.path.getmtime, reverse=True):
            fname = f.name
            # 解析 tweet_id: {id}_{index}.mp4
            parts = fname.split("_")
            tid = parts[0] if parts else ""
            
            if tid and tid not in archive:
                archive.add(tid)
                downloaded.append({
                    "id": tid,
                    "filename": str(f),
                    "account": account,
                })
    
    # 清理图片（只保留视频）
    for img in Path(dl_dir).glob("*.jpg"):
        try:
            img.unlink()
        except:
            pass
    for img in Path(dl_dir).glob("*.png"):
        try:
            img.unlink()
        except:
            pass
    
    return downloaded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=SINCE_HOURS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    archive = load_archive()
    
    total_downloaded = 0
    print(f"🪖 X 军事视频下载 v2.0 (gallery-dl)")
    print(f"   回溯 {args.since_hours}h | 存量 {len(archive)} 条\n")
    
    for account in ACCOUNTS:
        if args.dry_run:
            print(f"  🔍 @{account} — dry-run 跳过")
            continue
        
        print(f"  🔍 @{account} ...", end=" ", flush=True)
        
        try:
            downloaded = scan_and_download(account, archive, MAX_PER_ACCOUNT)
        except Exception as e:
            print(f"❌ {str(e)[:60]}")
            continue
        
        if downloaded:
            print(f"✅ {len(downloaded)} 条")
            for d in downloaded:
                fsize = os.path.getsize(d["filename"]) / 1024 / 1024
                print(f"    🎬 {d['id']} ({fsize:.1f}MB)")
                total_downloaded += 1
        else:
            print("0 条新视频")
    
    save_archive(archive)
    print(f"\n✅ 完成 | 下载 {total_downloaded} | 存量 {len(archive)}")


if __name__ == "__main__":
    main()
