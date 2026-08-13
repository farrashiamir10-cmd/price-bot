"""
تعیین می‌کنه که در هر اجرا (بر اساس ساعت فعلی به وقت تهران) باید
«قیمت» پست بشه یا «مقاله»، و همچنین حافظه‌ی مقالات پست‌شده‌ی امروز
رو نگه می‌داره تا مقاله تکراری پست نشه.

برنامه روزانه (هر ۲ ساعت، ۹ صبح تا ۹ شب):
    09:00 -> قیمت (6 پست جدا: دسته‌های اصلی)
    11:00 -> مقاله
    13:00 -> مقاله
    15:00 -> قیمت (5 پست جدا: دسته‌های دیگر)
    17:00 -> مقاله
    19:00 -> قیمت (5 پست جدا: باقی دسته‌ها)
    21:00 -> مقاله
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

# ساعت (به وقت تهران) -> نوع پست
SCHEDULE: dict[int, str] = {
    9: "price",
    11: "article",
    13: "article",
    15: "price",
    17: "article",
    19: "price",
    21: "article",
}

# ساعت (به وقت تهران) اسلات‌های قیمت، به ترتیب در طول روز.
# اندیس هر ساعت در این لیست تعیین می‌کنه کدوم بخش از دسته‌بندی‌ها
# (از main.py -> ALL_CATEGORIES) در اون اسلات پست میشه.
PRICE_SLOT_HOURS: list[int] = [9, 15, 19]

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


def get_current_slot(now: datetime | None = None) -> str:
    """نزدیک‌ترین اسلات زمانی تعریف‌شده رو بر می‌گردونه (price یا article)."""
    now = now or datetime.now(TEHRAN_TZ)
    hour = now.hour

    if hour in SCHEDULE:
        return SCHEDULE[hour]

    # اگر دقیقاً روی ساعت تعریف‌شده نبود (مثلاً به‌خاطر تاخیر اجرای cron)
    # نزدیک‌ترین ساعت تعریف‌شده رو انتخاب کن
    closest_hour = min(SCHEDULE.keys(), key=lambda h: abs(h - hour))
    return SCHEDULE[closest_hour]


def get_price_slot_index(now: datetime | None = None) -> int:
    """
    اندیس این اسلات قیمت در بین اسلات‌های امروز (0، 1 یا 2) رو برمی‌گردونه.
    برای تقسیم دسته‌بندی‌ها بین پست‌های قیمت روز استفاده میشه تا هیچ
    دسته‌ای دوبار در یک روز نمایش داده نشه.
    """
    now = now or datetime.now(TEHRAN_TZ)
    hour = now.hour

    if hour in PRICE_SLOT_HOURS:
        return PRICE_SLOT_HOURS.index(hour)

    closest_hour = min(PRICE_SLOT_HOURS, key=lambda h: abs(h - hour))
    return PRICE_SLOT_HOURS.index(closest_hour)


def _today_str(now: datetime | None = None) -> str:
    now = now or datetime.now(TEHRAN_TZ)
    return now.strftime("%Y-%m-%d")


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"date": _today_str(), "posted_article_links": []}

    with open(STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)

    if state.get("date") != _today_str():
        state = {"date": _today_str(), "posted_article_links": []}

    return state


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def mark_article_posted(link: str) -> None:
    state = load_state()
    if link not in state["posted_article_links"]:
        state["posted_article_links"].append(link)
    save_state(state)


def get_posted_links_today() -> list[str]:
    return load_state()["posted_article_links"]
