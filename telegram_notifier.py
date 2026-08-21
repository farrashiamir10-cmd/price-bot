"""
ارسال پیام به کانال تلگرام از طریق Bot API.
توکن و آیدی کانال از متغیرهای محیطی خوانده می‌شوند:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID   (مثلاً @your_channel یا -100xxxxxxxxxx)
"""

from __future__ import annotations

import os
import time
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_API_PHOTO = "https://api.telegram.org/bot{token}/sendPhoto"

MAX_LEN = 4000  # کمی کمتر از سقف واقعی تلگرام (4096) برای پیام‌های متنی
CAPTION_MAX_LEN = 1000  # کمی کمتر از سقف واقعی تلگرام (1024) برای کپشن عکس


def _post(token: str, chat_id: str, text: str, disable_preview: bool = True) -> None:
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    resp = requests.post(url, data=payload, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"Telegram error {resp.status_code}: {resp.text}")


def _post_photo(token: str, chat_id: str, photo_url: str, caption: str = "") -> None:
    url = TELEGRAM_API_PHOTO.format(token=token)
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "parse_mode": "HTML",
    }
    if caption:
        payload["caption"] = caption

    resp = requests.post(url, data=payload, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"Telegram sendPhoto error {resp.status_code}: {resp.text}")


def send_photo(
    photo_url: str,
    caption: str = "",
    token: str | None = None,
    chat_id: str | None = None,
) -> None:
    """
    یک پست عکس‌دار به کانال می‌فرسته. اگه caption بیشتر از سقف مجاز تلگرام
    (1024 کاراکتر) باشه، خودش کوتاهش می‌کنه تا خطا نده.
    """
    token = token or os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]

    if len(caption) > CAPTION_MAX_LEN:
        caption = caption[: CAPTION_MAX_LEN - 1] + "…"

    _post_photo(token, chat_id, photo_url, caption)


def send_long_message(text: str, token: str | None = None, chat_id: str | None = None) -> None:
    """پیام طولانی را در صورت نیاز به چند بخش تقسیم و ارسال می‌کند."""
    token = token or os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]

    if len(text) <= MAX_LEN:
        _post(token, chat_id, text)
        return

    # تقسیم بر اساس خطوط خالی تا وسط یک آیتم قطع نشود
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        if len(current) + len(block) + 2 > MAX_LEN:
            parts.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        parts.append(current)

    for part in parts:
        _post(token, chat_id, part)
        time.sleep(1)  # جلوگیری از rate-limit تلگرام
