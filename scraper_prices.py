"""
استخراج قیمت‌های لحظه‌ای (طلا، ارز، ارز دیجیتال، گوشی، لوازم یدکی و ...)
از بخش «ویترین زنده بازار» صفحه اصلی gheimatonline.com

ساختار HTML هدف:
  <div class="hb-box">
      <h3 class="hb-box-title">طلا و ارز</h3>
      <div class="hb-viewport">
        <div class="hb-track">
          <div class="hb-set">                <!-- فقط اولین hb-set (بدون aria-hidden) -->
             <a class="hb-card" href="...">
                <div class="hb-card-top">
                    <img ...>
                    <div class="hb-card-title">دلار</div>
                    <span class="hb-badge up|down|flat">...</span>
                </div>
                <div class="hb-card-price"><span>187,800</span><small>تومان</small></div>
             </a>
          </div>
        </div>
      </div>
  </div>
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass

HOME_URL = "https://gheimatonline.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class PriceItem:
    title: str
    price: str
    unit: str
    change_text: str
    change_dir: str  # up | down | flat
    link: str | None


@dataclass
class PriceBox:
    category: str
    items: list[PriceItem]


def fetch_home_html(timeout: int = 20) -> str:
    resp = requests.get(HOME_URL, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_price_boxes(html: str) -> list[PriceBox]:
    soup = BeautifulSoup(html, "lxml")
    boxes: list[PriceBox] = []

    for hb_box in soup.select("div.hb-box"):
        title_tag = hb_box.select_one("h3.hb-box-title")
        if not title_tag:
            continue
        category = title_tag.get_text(strip=True)

        # فقط اولین hb-set واقعی (نه نسخه تکراری aria-hidden برای انیمیشن)
        first_set = hb_box.select_one("div.hb-set:not([aria-hidden])")
        if not first_set:
            first_set = hb_box.select_one("div.hb-set")
        if not first_set:
            continue

        items: list[PriceItem] = []
        for card in first_set.select(".hb-card"):
            title_el = card.select_one(".hb-card-title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            price_el = card.select_one(".hb-card-price span")
            unit_el = card.select_one(".hb-card-price small")
            price = price_el.get_text(strip=True) if price_el else ""
            unit = unit_el.get_text(strip=True) if unit_el else ""

            badge_el = card.select_one(".hb-badge")
            change_text = badge_el.get_text(strip=True) if badge_el else ""
            change_dir = "flat"
            if badge_el:
                classes = badge_el.get("class", [])
                if "up" in classes:
                    change_dir = "up"
                elif "down" in classes:
                    change_dir = "down"

            link = card.get("href") if card.name == "a" else None

            items.append(
                PriceItem(
                    title=title,
                    price=price,
                    unit=unit,
                    change_text=change_text,
                    change_dir=change_dir,
                    link=link,
                )
            )

        if items:
            boxes.append(PriceBox(category=category, items=items))

    return boxes


def split_gold_currency_box(boxes: list[PriceBox]) -> list[PriceBox]:
    """
    دسته‌ی «طلا و ارز» (که در صفحه اصلی ترکیبی از ارز و فلزات گرانبهاست)
    رو بر اساس لینک آیتم‌ها به دو دسته‌ی مجزا تفکیک می‌کنه:
        - ارز          (لینک شامل /currency/)
        - فلزات گرانبها  (لینک شامل /metal/)
    خروجی: همون لیست boxes با این تفاوت که دسته‌ی «طلا و ارز» با دو دسته‌ی
    «ارز» و «فلزات گرانبها» جایگزین می‌شه؛ سایر دسته‌ها دست‌نخورده باقی می‌مونن.
    """
    result: list[PriceBox] = []

    for box in boxes:
        if box.category != "طلا و ارز":
            result.append(box)
            continue

        currency_items = [it for it in box.items if it.link and "/currency/" in it.link]
        metal_items = [it for it in box.items if it.link and "/metal/" in it.link]
        other_items = [
            it for it in box.items
            if it not in currency_items and it not in metal_items
        ]

        if currency_items:
            result.append(PriceBox(category="ارز", items=currency_items))
        if metal_items:
            result.append(PriceBox(category="فلزات گرانبها", items=metal_items))
        if other_items:
            result.append(PriceBox(category="طلا و ارز", items=other_items))

    return result


def get_price_boxes() -> list[PriceBox]:
    html = fetch_home_html()
    boxes = parse_price_boxes(html)
    return split_gold_currency_box(boxes)


if __name__ == "__main__":
    for box in get_price_boxes():
        print(f"\n=== {box.category} ===")
        for it in box.items:
            arrow = {"up": "🟢▲", "down": "🔴▼", "flat": "⚪️"}[it.change_dir]
            print(f"{it.title}: {it.price} {it.unit} {arrow} {it.change_text}")
