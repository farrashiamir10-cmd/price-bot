"""
استخراج محصولات از صفحات دسته‌بندی سایت (مثل لپ‌تاپ، موبایل، پوشاک و ...).
همه‌ی این صفحات از یک قالب مشترک (کلاس .hb-pcard) استفاده می‌کنن، پس
همین یک تابع برای هر تعداد صفحه‌ی دسته‌بندی کار می‌کنه.

ساختار HTML هدف:
    <div class="hb-products-grid">
        <div class="hb-pcol">
            <a class="hb-pcard" href="..." title="عنوان کامل محصول">
                <div class="hb-pcard-media">...</div>
                <div class="hb-pcard-body">
                    <h3 class="hb-pcard-title">عنوان کوتاه‌شده...</h3>
                    <div class="hb-pcard-meta">
                        <span class="hb-trend-chip up|down|flat">...</span>
                    </div>
                    <div class="hb-pcard-price">
                        <strong>110,000,000</strong><small>تومان</small>
                    </div>
                </div>
            </a>
        </div>
        ...
    </div>
"""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

from scraper_prices import fetch_home_html as _fetch_html_base  # reuse headers/session logic
import requests
from scraper_prices import HEADERS


# صفحات دسته‌بندی که قراره قیمت‌هاشون پست بشه
# (نام نمایشی -> آدرس صفحه)
CATEGORY_PAGES: dict[str, str] = {
    "لپ‌تاپ": "https://gheimatonline.com/Digital-appliances/laptop",
    "موبایل": "https://gheimatonline.com/Digital-appliances/mobile",
    "پوشاک": "https://gheimatonline.com/Fashion-clothing",
    "هایپرمارکت": "https://gheimatonline.com/Hypermarket",
    "لوازم فروشگاهی": "https://gheimatonline.com/Shop-supplies",
    "صوتی و تصویری": "https://gheimatonline.com/Audio-and-video/Audio-and-video-systems",
    "تجهیزات کافی‌شاپ": "https://gheimatonline.com/Coffee-shop-equipment",
    "کوهنوردی": "https://gheimatonline.com/Travel-camping-supplies/Climbing-equipment",
    "سفر و کمپینگ": "https://gheimatonline.com/Travel-camping-supplies",
    "لوازم خانه و آشپزخانه": "https://gheimatonline.com/Home-and-kitchen-appliances",
}


@dataclass
class CategoryProduct:
    title: str
    price: str
    unit: str
    trend_dir: str  # up | down | flat
    trend_text: str
    link: str


def fetch_category_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_category_products(html: str, limit: int | None = None) -> list[CategoryProduct]:
    soup = BeautifulSoup(html, "lxml")
    grid = soup.select_one(".hb-products-grid") or soup

    products: list[CategoryProduct] = []
    for card in grid.select("a.hb-pcard"):
        # عنوان کامل از attribute «title» می‌آد (نسخه‌ی h3 معمولاً کوتاه‌شده‌ست)
        title = card.get("title", "").strip()
        if not title:
            title_el = card.select_one(".hb-pcard-title")
            title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        price_el = card.select_one(".hb-pcard-price strong")
        unit_el = card.select_one(".hb-pcard-price small")
        price = price_el.get_text(strip=True) if price_el else ""
        unit = unit_el.get_text(strip=True) if unit_el else ""

        trend_el = card.select_one(".hb-trend-chip")
        trend_text = trend_el.get_text(strip=True) if trend_el else ""
        trend_dir = "flat"
        if trend_el:
            classes = trend_el.get("class", [])
            if "up" in classes:
                trend_dir = "up"
            elif "down" in classes:
                trend_dir = "down"

        link = card.get("href", "")

        products.append(
            CategoryProduct(
                title=title,
                price=price,
                unit=unit,
                trend_dir=trend_dir,
                trend_text=trend_text,
                link=link,
            )
        )

        if limit and len(products) >= limit:
            break

    return products


def get_category_products(category_name: str, limit: int = 8) -> list[CategoryProduct]:
    url = CATEGORY_PAGES[category_name]
    html = fetch_category_html(url)
    return parse_category_products(html, limit=limit)


if __name__ == "__main__":
    for name in CATEGORY_PAGES:
        print(f"\n=== {name} ===")
        for p in get_category_products(name, limit=5):
            arrow = {"up": "🟢▲", "down": "🔴▼", "flat": "⚪️"}[p.trend_dir]
            print(f"{p.title[:60]}: {p.price} {p.unit} {arrow}")
