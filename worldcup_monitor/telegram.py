from __future__ import annotations

from curl_cffi import requests as curl_requests


def _safe_chat_id(chat_id: str) -> str:
    chat_id = str(chat_id)
    if len(chat_id) <= 4:
        return "***"
    return f"***{chat_id[-4:]}"


def send_message(token: str, chat_ids: list[str], text: str) -> bool:
    if not token or not chat_ids or not text:
        print("telegram skipped: missing token, chat id, or text", flush=True)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for chat_id in chat_ids:
        try:
            resp = curl_requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=20)
            if resp.status_code != 200:
                ok = False
                print(
                    f"telegram failed chat={_safe_chat_id(chat_id)} HTTP {resp.status_code}: {resp.text[:200]}",
                    flush=True,
                )
            else:
                print(f"telegram sent chat={_safe_chat_id(chat_id)}", flush=True)
        except Exception as exc:
            ok = False
            print(f"telegram failed chat={_safe_chat_id(chat_id)}: {exc}", flush=True)
    return ok
