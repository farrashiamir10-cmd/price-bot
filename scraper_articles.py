"""
استخراج آخرین مقالات از اسلایدر بالای صفحه اصلی gheimatonline.com
(بخش .single-hero-slider که لینک و تیتر مقالات رو نشون میده)

برای خلاصه‌سازی از تگ استاندارد سئوی og:description در <head> صفحه‌ی
خود مقاله استفاده می‌کنیم (بدون نیاز به هوش مصنوعی و بدون نیاز به دونستن
ساختار دقیق بدنه مقاله).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from scraper_prices import HOME_URL, HEADERS


@dataclass
class Article:
    title: str
    link: str
    summary: str = ""


def fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_latest_articles(html: str, limit: int = 5) -> list[Article]:
    soup = BeautifulSoup(html, "lxml")
    articles: list[Article] = []
    seen_links: set[str] = set()

    for a in soup.select("a.single-hero-slider"):
        href = a.get("href", "").strip()
        if not href or href in seen_links:
            continue
        if "/article/" not in href:
            continue

        # عنوان کامل (نسخه دسکتاپ، غیرکوتاه‌شده)
        title_tag = a.select_one("h3.d-none.d-md-block") or a.select_one("h3")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        seen_links.add(href)
        articles.append(Article(title=title, link=href))

        if len(articles) >= limit:
            break

    return articles


def fetch_summary(article_url: str, timeout: int = 15) -> str:
    """خلاصه ساده: خواندن og:description از هد صفحه مقاله."""
    try:
        html = fetch_html(article_url, timeout=timeout)
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(html, "lxml")

    meta = soup.select_one('meta[property="og:description"]') or soup.select_one(
        'meta[name="description"]'
    )
    if meta and meta.get("content"):
        return meta["content"].strip()

    # اگر متایی نبود، اولین پاراگراف معنادار محتوا را برمی‌داریم
    for p in soup.select("p"):
        text = p.get_text(strip=True)
        if len(text) > 40:
            return text[:250] + ("..." if len(text) > 250 else "")

    return ""


def get_latest_article_candidates(limit: int = 10) -> list[Article]:
    """لیست آخرین مقالات رو بدون خلاصه برمی‌گردونه (سریع، بدون درخواست اضافه)."""
    html = fetch_html(HOME_URL)
    return parse_latest_articles(html, limit=limit)


def get_latest_articles(limit: int = 5, with_summary: bool = True, delay: float = 1.0) -> list[Article]:
    articles = get_latest_article_candidates(limit=limit)

    if with_summary:
        for art in articles:
            art.summary = fetch_summary(art.link)
            time.sleep(delay)  # فشار کمتر روی سرور سایت

    return articles


if __name__ == "__main__":
    for art in get_latest_articles(limit=5):
        print(f"\n{art.title}\n{art.link}\n{art.summary}")
