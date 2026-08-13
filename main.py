"""
اسکریپت اصلی ربات «قیمت آنلاین».

هر بار اجرا فقط یک «نوع» پست می‌فرسته (نه هر دو با هم)، بر اساس ساعت
فعلی (به وقت تهران) و برنامه‌ی زمانی تعریف‌شده در scheduler.py:

    09:00 -> قیمت (6 پست جدا: دسته‌های اصلی)
    11:00 -> مقاله (1 پست)
    13:00 -> مقاله (1 پست)
    15:00 -> قیمت (5 پست جدا)
    17:00 -> مقاله (1 پست)
    19:00 -> قیمت (5 پست جدا)
    21:00 -> مقاله (1 پست)

نکته‌ی مهم: هر دسته‌بندی قیمت، پست تلگرام مستقل خودش رو داره (نه یک
پیام ترکیبی). در طول یک روز، هر ۱۶ دسته (۶ دسته اصلی + ۱۰ دسته‌ی
صفحه‌های اختصاصی) دقیقاً یک‌بار پوشش داده می‌شن و هیچ‌کدوم تکرار
نمی‌شن. این کار با تقسیم ثابت لیست ALL_CATEGORIES به ۳ بخش (بر اساس
اینکه این اجرا اولین/دومین/سومین اسلات قیمتِ امروزه) انجام میشه.

اجرای دستی (برای تست):
    TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=@your_channel python3 main.py

اجرای دستی با انتخاب نوع پست (بدون توجه به ساعت فعلی سیستم):
    FORCE_SLOT=price python3 main.py
    FORCE_SLOT=article python3 main.py

اجرای دستی با انتخاب دستیِ اسلات قیمت روز (0، 1 یا 2):
    FORCE_SLOT=price FORCE_PRICE_SLOT_INDEX=1 python3 main.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime

from scraper_prices import get_price_boxes, PriceBox
from scraper_articles import get_latest_article_candidates, fetch_summary, Article
from scraper_categories import CATEGORY_PAGES, get_category_products
from telegram_notifier import send_long_message
from scheduler import (
    TEHRAN_TZ,
    get_current_slot,
    get_price_slot_index,
    get_posted_links_today,
    mark_article_posted,
)

SITE_NAME = "قیمت آنلاین"
SITE_URL = "https://gheimatonline.com/"

CHANGE_ARROW = {"up": "🟢▲", "down": "🔴▼", "flat": "⚪️"}

# فاصله بین ارسال پست‌های پیاپی (برای رعایت محدودیت نرخ ارسال تلگرام)
DELAY_BETWEEN_POSTS_SECONDS = 1.5

# 6 دسته‌ی اصلی که مستقیماً از صفحه اصلی سایت استخراج می‌شن
CORE_CATEGORIES: list[str] = [
    "ارز",
    "ارز دیجیتال",
    "فلزات گرانبها",
    "گوشی موبایل",
    "کالاهای اساسی",
    "لوازم یدکی",
]

# نام نمایشی + ایموجی هر دسته در تیتر پست تلگرام
CATEGORY_INFO: dict[str, tuple[str, str]] = {
    # دسته اصلی: (عنوان نمایشی, ایموجی)
    "ارز": ("قیمت ارز", "💵"),
    "ارز دیجیتال": ("قیمت ارز دیجیتال", "🪙"),
    "فلزات گرانبها": ("قیمت فلزات گرانبها", "🥇"),
    "گوشی موبایل": ("قیمت موبایل", "📱"),
    "کالاهای اساسی": ("قیمت کالاهای اساسی", "🛒"),
    "لوازم یدکی": ("قیمت لوازم یدکی خودرو", "🚗"),
    # دسته‌های صفحه‌ی اختصاصی (نام کلید باید دقیقاً با CATEGORY_PAGES یکی باشه)
    "لپ‌تاپ": ("قیمت لپ‌تاپ", "💻"),
    "موبایل": ("قیمت موبایل (لیست کامل)", "📲"),
    "پوشاک": ("قیمت پوشاک", "👕"),
    "هایپرمارکت": ("قیمت هایپرمارکت", "🏬"),
    "لوازم فروشگاهی": ("قیمت لوازم فروشگاهی", "🏪"),
    "صوتی و تصویری": ("قیمت صوتی و تصویری", "🎧"),
    "تجهیزات کافی‌شاپ": ("قیمت تجهیزات کافی‌شاپ", "☕"),
    "کوهنوردی": ("قیمت لوازم کوهنوردی", "⛰️"),
    "سفر و کمپینگ": ("قیمت لوازم سفر و کمپینگ", "🏕️"),
    "لوازم خانه و آشپزخانه": ("قیمت لوازم خانه و آشپزخانه", "🍳"),
}

# ترتیب ثابت همه‌ی 16 دسته: 6 دسته اصلی + 10 دسته صفحه‌ی اختصاصی.
# هر روز این لیست بین 3 اسلات قیمت (09:00 / 15:00 / 19:00) تقسیم میشه:
#   اسلات 0 (09:00) -> 6 دسته اول (همون 6 دسته اصلی)
#   اسلات 1 (15:00) -> 5 دسته بعدی
#   اسلات 2 (19:00) -> 5 دسته آخر
ALL_CATEGORIES: list[str] = CORE_CATEGORIES + list(CATEGORY_PAGES.keys())

PRICE_SLOT_CHUNK_SIZES: list[int] = [6, 5, 5]  # جمعشون باید برابر len(ALL_CATEGORIES) باشه
assert sum(PRICE_SLOT_CHUNK_SIZES) == len(ALL_CATEGORIES), "جمع بخش‌ها باید برابر تعداد کل دسته‌ها باشه"

PRODUCTS_PER_CATEGORY = 6
ARTICLE_CANDIDATES_LIMIT = 10  # چند مقاله اخیر بررسی بشه تا اولین «پست‌نشده» پیدا بشه


def get_todays_categories() -> list[str]:
    forced = os.environ.get("FORCE_PRICE_SLOT_INDEX")
    idx = int(forced) if forced is not None else get_price_slot_index()

    start = sum(PRICE_SLOT_CHUNK_SIZES[:idx])
    size = PRICE_SLOT_CHUNK_SIZES[idx]
    return ALL_CATEGORIES[start : start + size]


def build_core_category_message(box: PriceBox) -> str:
    display_name, emoji = CATEGORY_INFO.get(box.category, (box.category, "📊"))
    now_str = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M")

    lines = [f"{emoji} <b>{display_name}</b>", f"🕐 بروزرسانی: {now_str}", ""]

    for item in box.items:
        arrow = CHANGE_ARROW.get(item.change_dir, "⚪️")
        price_part = f"{item.price} {item.unit}".strip()
        change_part = f" ({item.change_text})" if item.change_text else ""
        lines.append(f"• {item.title}: <b>{price_part}</b> {arrow}{change_part}")

    lines.append("")
    lines.append(f'🔗 <a href="{SITE_URL}">مشاهده در {SITE_NAME}</a>')
    return "\n".join(lines)


def build_extra_category_message(category_name: str, products: list) -> str:
    display_name, emoji = CATEGORY_INFO.get(category_name, (category_name, "📊"))
    now_str = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M")
    page_url = CATEGORY_PAGES.get(category_name, SITE_URL)

    lines = [f"{emoji} <b>{display_name}</b>", f"🕐 بروزرسانی: {now_str}", ""]

    for p in products:
        arrow = CHANGE_ARROW.get(p.trend_dir, "⚪️")
        price_part = f"{p.price} {p.unit}".strip()
        title_short = p.title if len(p.title) <= 65 else p.title[:62] + "..."
        lines.append(f"• {title_short}: <b>{price_part}</b> {arrow}")

    lines.append("")
    lines.append(f'🔗 <a href="{page_url}">مشاهده همه محصولات این دسته</a>')
    return "\n".join(lines)


def build_article_message(article: Article) -> str:
    lines = [f"📰 <b>{article.title}</b>", ""]
    if article.summary:
        lines.append(article.summary)
        lines.append("")
    lines.append(f'<a href="{article.link}">ادامه مطلب →</a>')
    return "\n".join(lines)


def post_prices() -> None:
    todays_categories = get_todays_categories()
    print(f"دسته‌های امروزِ این اسلات: {todays_categories}")

    core_wanted = [c for c in todays_categories if c in CORE_CATEGORIES]
    extra_wanted = [c for c in todays_categories if c in CATEGORY_PAGES]

    # --- دسته‌های اصلی: یک درخواست به صفحه اصلی، بعد پست جدا برای هرکدوم ---
    boxes_by_category: dict[str, PriceBox] = {}
    if core_wanted:
        print("در حال دریافت قیمت‌های اصلی از صفحه اصلی...")
        boxes = get_price_boxes()
        boxes_by_category = {b.category: b for b in boxes}

    posted_count = 0
    for category in todays_categories:
        if category in CORE_CATEGORIES:
            box = boxes_by_category.get(category)
            if not box or not box.items:
                print(f"دسته «{category}» در صفحه اصلی پیدا نشد یا خالی بود؛ رد شد.")
                continue
            msg = build_core_category_message(box)

        elif category in CATEGORY_PAGES:
            print(f"در حال دریافت دسته «{category}»...")
            try:
                products = get_category_products(category, limit=PRODUCTS_PER_CATEGORY)
            except Exception as exc:  # noqa: BLE001 - یک دسته‌ی خراب نباید بقیه رو متوقف کنه
                print(f"خطا در دریافت دسته «{category}»: {exc}")
                continue

            if not products:
                print(f"دسته «{category}» محصولی نداشت؛ رد شد.")
                continue
            msg = build_extra_category_message(category, products)

        else:
            print(f"دسته‌ی ناشناخته: {category}")
            continue

        print(f"\n----- پست: {category} -----")
        print(msg)
        send_long_message(msg)
        posted_count += 1
        time.sleep(DELAY_BETWEEN_POSTS_SECONDS)

    print(f"\n✅ {posted_count} پست قیمت (از {len(todays_categories)} دسته) ارسال شد.")


def post_article() -> None:
    print("در حال بررسی مقالات...")
    already_posted = set(get_posted_links_today())
    candidates = get_latest_article_candidates(limit=ARTICLE_CANDIDATES_LIMIT)

    next_article = next((a for a in candidates if a.link not in already_posted), None)

    if next_article is None:
        print("همه مقالات اخیر امروز قبلا پست شده‌اند؛ پستی ارسال نشد.")
        return

    next_article.summary = fetch_summary(next_article.link)
    msg = build_article_message(next_article)
    print(msg)
    send_long_message(msg)
    mark_article_posted(next_article.link)
    print("پست مقاله ارسال شد.")


def main() -> None:
    slot = os.environ.get("FORCE_SLOT") or get_current_slot()
    print(f"نوع پست تعیین‌شده برای این اجرا: {slot}")

    if slot == "price":
        post_prices()
    elif slot == "article":
        post_article()
    else:
        raise ValueError(f"نوع اسلات نامعتبر: {slot}")


if __name__ == "__main__":
    main()
