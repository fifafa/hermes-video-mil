# 军事视频搬运工坊 (Military Video Pipeline)

自动从 YouTube/X 下载军事/装备分析视频，用于二次创作。

## 源账号

### YouTube (5频道)
- @PerunAU — 国防经济学
- @CovertCabal — 军事分析
- @Binkov — 军力对比
- @Taskandpurpose — 军事科技
- @WardCarroll — 军事航空 (前F-14 RIO)

### X/Twitter (5账号)
- @Osinttechnical — OSINT/战场分析
- @RALee85 — 俄军装备
- @UAWeapons — 武器分析
- @oryxspioenkop — 装备损失追踪
- @COUPSURE — 国防科技

## 脚本

| 脚本 | 用途 |
|------|------|
| `yt_download.py` | YouTube 增量下载 (n-sig绕过) |
| `x_download.py` | X 视频下载 |
| `x_scraper.py` | X Playwright 抓取 |

## 运行

```bash
# YouTube
python3 yt_download.py --since-hours 24

# X (Twitter)
python3 x_download.py --since-hours 24

# 试运行 (不下载)
python3 yt_download.py --dry-run
```

## 注意

- YouTube 需要 `node` 运行时绕过 n-sig 签名
- Cookie 文件路径硬编码，部署时需调整
