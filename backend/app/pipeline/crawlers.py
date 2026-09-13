"""采集器：RSS 关键词监控 + 网页剪藏。A 级政务站点一期走后台导入（半自动）。"""

import hashlib
import time
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import settings


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def _headers() -> dict:
    return {"User-Agent": settings.crawl_user_agent, "Accept-Language": "zh-CN,zh;q=0.9"}


def fetch_page_meta(url: str) -> dict:
    """抓取网页标题/发布者/摘要/发布时间，供剪藏预填。失败返回最小信息。"""
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=_headers()) as client:
            r = client.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:  # noqa: BLE001
        return {"title": url, "publisher": None, "summary": None, "published_at": None, "error": str(e)}

    soup = BeautifulSoup(html, "lxml")

    def meta(*names: str) -> str | None:
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    title = meta("og:title", "twitter:title") or (soup.title.string.strip() if soup.title and soup.title.string else url)
    publisher = meta("og:site_name", "publisher", "author")
    summary = meta("og:description", "description")
    if not summary:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 30)
        summary = text[:300] or None
    published = meta("article:published_time", "pubdate", "publishdate", "og:updated_time")
    published_at = None
    if published:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                published_at = datetime.strptime(published[:25], fmt)
                break
            except ValueError:
                continue
    return {"title": title[:500], "publisher": publisher, "summary": summary, "published_at": published_at, "error": None}


def rss_urls_for(keywords: list[str], explicit: list[str]) -> list[str]:
    urls = list(explicit or [])
    templates = [t.strip() for t in settings.news_rss_templates.split(",") if t.strip()]
    for kw in keywords or []:
        for t in templates:
            urls.append(t.replace("{keyword}", quote(kw)))
    return urls


def fetch_rss(url: str) -> list[dict]:
    feed = feedparser.parse(url, request_headers=_headers())
    items = []
    for e in feed.entries[:50]:
        link = e.get("link")
        if not link:
            continue
        published = None
        if e.get("published_parsed"):
            published = datetime.fromtimestamp(time.mktime(e.published_parsed), tz=timezone.utc)
        items.append(
            {
                "url": link,
                "title": (e.get("title") or link)[:500],
                "summary": BeautifulSoup(e.get("summary", ""), "lxml").get_text(" ", strip=True)[:500] or None,
                "publisher": (feed.feed.get("title") or None),
                "published_at": published,
            }
        )
    return items
