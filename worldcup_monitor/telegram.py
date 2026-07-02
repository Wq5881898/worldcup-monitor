from __future__ import annotations

from curl_cffi import requests as curl_requests


def send_message(token: str, chat_ids: list[str], text: str) -> None:
    if not token or not chat_ids or not text:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in chat_ids:
        try:
            curl_requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=20)
        except Exception as exc:
            print(f"telegram failed for chat {chat_id}: {exc}")
