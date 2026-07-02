from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlsplit, urlunsplit


@dataclass(frozen=True)
class CurlRequest:
    method: str
    url: str
    params: list[tuple[str, str]]
    headers: dict[str, str]
    cookies: dict[str, str]
    data: str
    json_data: object | None


def normalize_cmd_curl(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"\^\s*\r?\n", " ", text)
    text = re.sub(r"\^(.)", r"\1", text)
    return " ".join(text.split())


def parse_cookie_header(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies


def parse_curl(raw_curl: str) -> CurlRequest:
    normalized = normalize_cmd_curl(raw_curl)
    tokens = shlex.split(normalized, posix=True)
    if not tokens or tokens[0].lower() != "curl":
        raise ValueError("curl command must start with curl")

    method = "GET"
    raw_url = ""
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    data = ""

    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
            continue
        if token in ("-H", "--header") and i + 1 < len(tokens):
            header = tokens[i + 1]
            if ":" in header:
                key, value = header.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key.lower() == "cookie":
                    cookies.update(parse_cookie_header(value))
                else:
                    headers[key] = value
            i += 2
            continue
        if token in ("-b", "--cookie") and i + 1 < len(tokens):
            cookies.update(parse_cookie_header(tokens[i + 1]))
            i += 2
            continue
        if token in ("--data", "--data-raw", "--data-binary", "--data-urlencode", "-d") and i + 1 < len(tokens):
            data = tokens[i + 1]
            if method == "GET":
                method = "POST"
            i += 2
            continue
        if token == "--url" and i + 1 < len(tokens):
            raw_url = tokens[i + 1]
            i += 2
            continue
        if token.startswith(("http://", "https://")):
            raw_url = token
            i += 1
            continue
        i += 1

    if not raw_url:
        raise ValueError("curl command does not contain a URL")

    parsed = urlsplit(raw_url)
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    params = parse_qsl(parsed.query, keep_blank_values=True)
    json_data = None
    if data:
        try:
            json_data = json.loads(data)
        except json.JSONDecodeError:
            json_data = None

    return CurlRequest(
        method=method,
        url=url,
        params=params,
        headers=headers,
        cookies=cookies,
        data=data,
        json_data=json_data,
    )


def derive_df_sui_request(summary: CurlRequest) -> CurlRequest:
    match = re.search(r"/feed/g_1_([^/?#]+)$", summary.url)
    if not match:
        raise ValueError("cannot derive df_sui URL from summary URL")
    detail_url = summary.url[: match.start()] + f"/feed/df_sui_1_{match.group(1)}"
    headers = {k: v for k, v in summary.headers.items() if k.lower() != "x-signature"}
    return replace(summary, url=detail_url, headers=headers)
