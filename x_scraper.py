#!/usr/bin/env python3
"""
X (Twitter) 军事视频抓取 — Playwright + yt-dlp
服务器在美国西海岸 X 直通，用 Playwright 模拟浏览器+登录态即可
"""
import os, sys, json, re, asyncio, argparse, subprocess
from datetime import datetime, timedelta
from pathlib import Path

COOKIE_NETSCAPE = "/root/.hermes/cookies/X_cookies.txt"
ARCHIVE_FILE = "/root/hermes_video/.x_archive.txt"
OUTPUT_DIR = "/root/hermes_video/X"

ACCOUNTS = [
    "Osinttechnical", "RALee85", "UAWeapons",
    "oryxspioenkop", "COUPSURE",
]
MAX_PER = 2

def load_cookies_txt(path):
    """Netscape → Playwright cookie 格式"""
    cookies = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies.append({
                    "name": parts[5], "value": parts[6],
                    "domain": parts[0], "path": parts[2],
                    "httpOnly": False, "secure": parts[3] == "TRUE",
                    "sameSite": "Lax",
                })
    return cookies

async def scrape_account(account, max_tweets=10):
    """Playwright 抓账号 media 时间线"""
    from playwright.async_api import async_playwright
    
    cookies = load_cookies_txt(COOKIE_NETSCAPE)
    tweets = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        
        try:
            # 先验证登录状态
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)
            
            # 跳转 media 页
            await page.goto(f"https://x.com/{account}/media", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
            
            # 滚动加载
            for _ in range(4):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)
            
            # 提取推文链接并清洗
            links = await page.evaluate("""() => {
                const seen = new Set();
                document.querySelectorAll('a[href*="/status/"]').forEach(a => {
                    const href = a.getAttribute('href');
                    if (href && href.includes('/status/')) {
                        let clean = href.split('?')[0].split('#')[0];
                        // 去掉 /video/N, /photo/N 等后缀
                        clean = clean.replace(/\/(video|photo|analytics)\/\d+$/, '');
                        if (clean.match(/\/status\/\d+$/)) {
                            // 补齐协议
                            if (clean.startsWith('//')) clean = 'https:' + clean;
                            else if (clean.startsWith('/')) clean = 'https://x.com' + clean;
                            seen.add(clean);
                        }
                    }
                });
                return [...seen].slice(0, 10);
            }""")
            tweets = links
            
        except Exception as e:
            print(f"      ⚠ {e}")
        finally:
            await browser.close()
    
    return tweets

def download(url, archive):
    tid = url.split("/status/")[-1]
    if tid in archive:
        return None, "skipped"
    
    tmpl = f"{OUTPUT_DIR}/%(uploader)s_%(id)s.%(ext)s"
    r = subprocess.run(
        f'yt-dlp --cookies {COOKIE_NETSCAPE} -f "best[height<=1080]" --download-archive {ARCHIVE_FILE} -o "{tmpl}" --max-filesize 500M --no-playlist "{url}"',
        shell=True, capture_output=True, text=True, timeout=300
    )
    if r.returncode == 0:
        for line in (r.stdout + r.stderr).split("\n"):
            if "[download] Destination:" in line:
                return line.split("Destination:")[-1].strip(), "ok"
        return None, "ok"
    if "already been recorded" in r.stdout + r.stderr:
        return None, "skipped"
    return None, f"err: {(r.stderr or '')[:80]}"

async def scrape_account_safe(account, max_tweets=10, timeout=30):
    """带超时保护的抓取"""
    try:
        return await asyncio.wait_for(scrape_account(account, max_tweets), timeout=timeout)
    except asyncio.TimeoutError:
        print("⏰超时", end=" ")
        return []
    except Exception as e:
        print(f"⚠{str(e)[:40]}", end=" ")
        return []

# ... (main 中使用 scrape_account_safe)

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    arch = set()
    if os.path.exists(ARCHIVE_FILE):
        arch = set(open(ARCHIVE_FILE).read().splitlines())
    
    total = 0
    print(f"🪖 X 军事视频 | {datetime.now():%H:%M}\n")
    
    for acc in ACCOUNTS:
        print(f"  @{acc} ...", end=" ", flush=True)
        urls = await scrape_account_safe(acc, timeout=35)
        print(f"{len(urls)} tweets")
        
        for url in urls[:MAX_PER]:
            print(f"    {url[-50:]}")
            fname, status = download(url, arch)
            if status == "ok":
                arch.add(url.split("/status/")[-1])
                total += 1
                print(f"      ✅ {Path(fname).name if fname else 'OK'}")
            elif status == "skipped":
                print("      ⏭")
            else:
                print(f"      ❌ {status}")
    
    with open(ARCHIVE_FILE, "w") as f:
        for v in sorted(arch):
            f.write(f"{v}\n")
    print(f"\n✅ 下载 {total} | 存量 {len(arch)}")

if __name__ == "__main__":
    asyncio.run(main())
