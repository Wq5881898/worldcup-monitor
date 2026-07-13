from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi import requests as curl_requests


TOURNAMENT_URL = "https://www.flashscoreusa.com/soccer/world/world-championship/"
RESULTS_URL = f"{TOURNAMENT_URL}results/"
FIXTURES_URL = f"{TOURNAMENT_URL}fixtures/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"


@dataclass(frozen=True)
class MatchCandidate:
    title: str
    url: str
    source: str
    score_hint: str = ""


@dataclass(frozen=True)
class MatchPageInfo:
    event_id: str
    feed_sign: str
    home_team: str
    away_team: str
    page_title: str
    url: str


@dataclass(frozen=True)
class EncodedMatch:
    event_id: str
    home_team: str
    away_team: str
    home_id: str
    away_id: str
    home_slug: str
    away_slug: str
    tournament_label: str = ""

    @property
    def match_url(self) -> str:
        return (
            "https://www.flashscoreusa.com/game/soccer/"
            f"{self.away_slug}-{self.away_id}/{self.home_slug}-{self.home_id}/"
        )


def http_get_text(url: str) -> str:
    resp = curl_requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        impersonate="chrome120",
        timeout=20,
    )
    resp.raise_for_status()
    return resp.text


def normalize_name(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def extract_team_terms(query: str) -> list[str]:
    normalized = normalize_name(query)
    for sep in (" vs ", " v ", " versus ", " against ", " and ", " - "):
        if sep.strip() in normalized and sep in f" {normalized} ":
            parts = [part.strip() for part in normalized.split(sep) if part.strip()]
            if len(parts) >= 2:
                return parts[:2]
    tokens = [token for token in normalized.split() if token not in {"world", "cup", "score", "scores", "monitor", "current", "live", "match", "game"}]
    if len(tokens) >= 2:
        midpoint = max(1, len(tokens) // 2)
        return [" ".join(tokens[:midpoint]), " ".join(tokens[midpoint:])]
    return [normalized] if normalized else []


def build_summary_curl(event_id: str, feed_sign: str) -> str:
    return (
        f'curl ^"https://global.flashscore.ninja/130/x/feed/g_1_{event_id}^" ^\n'
        f'  -H ^"sec-ch-ua-platform: ^\\^"Windows^\\^"^" ^\n'
        f'  -H ^"Referer: https://www.flashscoreusa.com/^" ^\n'
        f'  -H ^"User-Agent: {USER_AGENT}^" ^\n'
        f'  -H ^"sec-ch-ua: ^\\^"Google Chrome^\\^";v=^\\^"149^\\^", ^\\^"Chromium^\\^";v=^\\^"149^\\^", ^\\^"Not)A;Brand^\\^";v=^\\^"24^\\^"^" ^\n'
        f'  -H ^"sec-ch-ua-mobile: ?0^" ^\n'
        f'  -H ^"x-fsign: {feed_sign}^"'
    )


def parse_match_page_info(page_url: str, html_text: str) -> MatchPageInfo:
    event_match = re.search(r'"event_id_c":"([^"]+)"', html_text)
    feed_sign_match = re.search(r'"feed_sign":"([^"]+)"', html_text)
    title_match = re.search(r"<title>([^<]+)</title>", html_text, re.IGNORECASE)
    if not event_match or not feed_sign_match:
        raise ValueError("could not extract event_id_c or feed_sign from match page")
    page_title = html.unescape(title_match.group(1).strip()) if title_match else page_url
    prefix = page_title.split("|", 1)[0].strip()
    teams_part = re.sub(r"\s+\d{2}/\d{2}/\d{4}\s*$", "", prefix).strip()
    if " v " in teams_part:
        home_team, away_team = [part.strip() for part in teams_part.split(" v ", 1)]
    elif " - " in teams_part:
        home_team, away_team = [part.strip() for part in teams_part.split(" - ", 1)]
    else:
        home_team, away_team = "", ""
    return MatchPageInfo(
        event_id=event_match.group(1),
        feed_sign=feed_sign_match.group(1),
        home_team=home_team,
        away_team=away_team,
        page_title=page_title,
        url=page_url,
    )


def parse_tournament_candidates(html_text: str) -> list[MatchCandidate]:
    pattern = re.compile(r'<a href="(?P<url>/game/soccer/[^"]+/)"[^>]*>(?P<label>[^<]+)</a>')
    seen: set[str] = set()
    candidates: list[MatchCandidate] = []
    for match in pattern.finditer(html_text):
        url = urljoin("https://www.flashscoreusa.com", html.unescape(match.group("url")))
        if url in seen:
            continue
        seen.add(url)
        label = html.unescape(match.group("label")).strip()
        candidates.append(MatchCandidate(title=label, url=url, source="tournament"))
    return candidates


def parse_encoded_matches(html_text: str) -> list[EncodedMatch]:
    matches: list[EncodedMatch] = []
    current_tournament = ""
    for block in html_text.split("~"):
        if "ZA÷WORLD:" in block:
            label_match = re.search(r"ZA÷([^¬]+)", block)
            if label_match:
                current_tournament = label_match.group(1).strip()
            continue
        if not block.startswith("AA÷"):
            continue

        fields: dict[str, str] = {}
        for part in block.split("¬"):
            if "÷" not in part:
                continue
            key, value = part.split("÷", 1)
            if key not in fields:
                fields[key] = html.unescape(value)

        if not fields.get("AA") or not fields.get("AE") or not fields.get("AF"):
            continue
        if not fields.get("PX") or not fields.get("PY") or not fields.get("WU") or not fields.get("WV"):
            continue

        matches.append(
            EncodedMatch(
                event_id=fields["AA"],
                home_team=fields["AE"],
                away_team=fields["AF"],
                home_id=fields["PX"],
                away_id=fields["PY"],
                home_slug=fields["WU"],
                away_slug=fields["WV"],
                tournament_label=current_tournament,
            )
        )
    return matches


def encoded_match_to_candidate(match: EncodedMatch, source: str) -> MatchCandidate:
    title = f"{match.home_team} - {match.away_team}"
    if match.tournament_label:
        title = f"{title} [{match.tournament_label}]"
    return MatchCandidate(title=title, url=match.match_url, source=source)


def candidate_score(candidate: MatchCandidate, terms: list[str]) -> tuple[int, int]:
    haystack = normalize_name(f"{candidate.title} {candidate.url}")
    matches = sum(1 for term in terms if term and term in haystack)
    return matches, len(haystack)


def choose_best_candidate(query: str, candidates: list[MatchCandidate]) -> MatchCandidate:
    if not candidates:
        raise ValueError(f"no FlashScore match candidates found for query: {query}")
    terms = extract_team_terms(query)
    ranked = sorted(candidates, key=lambda item: candidate_score(item, terms), reverse=True)
    best = ranked[0]
    if candidate_score(best, terms)[0] == 0:
        raise ValueError(f"could not match query to a FlashScore match: {query}")
    return best


def page_info_score(page_info: MatchPageInfo, terms: list[str]) -> tuple[int, int]:
    haystack = normalize_name(f"{page_info.home_team} {page_info.away_team} {page_info.page_title} {page_info.url}")
    matches = sum(1 for term in terms if term and term in haystack)
    exact_teams = 0
    for team_name in (page_info.home_team, page_info.away_team):
        normalized_team = normalize_name(team_name)
        if any(term == normalized_team for term in terms):
            exact_teams += 1
    return matches, exact_teams


def resolve_match_page(query: str) -> tuple[MatchCandidate, MatchPageInfo]:
    candidates: list[MatchCandidate] = []
    encoded_matches: dict[str, EncodedMatch] = {}

    for source, url in (
        ("tournament", TOURNAMENT_URL),
        ("results", RESULTS_URL),
        ("fixtures", FIXTURES_URL),
    ):
        html_text = http_get_text(url)
        candidates.extend(parse_tournament_candidates(html_text))
        for match in parse_encoded_matches(html_text):
            encoded_matches.setdefault(match.event_id, match)
            candidates.append(encoded_match_to_candidate(match, source))

    if not candidates:
        raise ValueError(f"no FlashScore match candidates found for query: {query}")

    terms = extract_team_terms(query)
    ranked = sorted(candidates, key=lambda item: candidate_score(item, terms), reverse=True)

    best_candidate: MatchCandidate | None = None
    best_page_info: MatchPageInfo | None = None
    best_score = (-1, -1)
    for candidate in ranked[:12]:
        page_html = ""
        try:
            page_html = http_get_text(candidate.url)
            page_info = parse_match_page_info(candidate.url, page_html)
        except Exception:
            event_match = re.search(r"/game/soccer/[^/]+/[^/]+/?$", candidate.url)
            if not event_match:
                continue
            encoded_match = next(
                (match for match in encoded_matches.values() if match.match_url == candidate.url),
                None,
            )
            if not encoded_match:
                continue
            if not page_html:
                continue
            event_id_match = re.search(r'"event_id_c":"([^"]+)"', page_html)
            feed_sign_match = re.search(r'"feed_sign":"([^"]+)"', page_html)
            if not event_id_match or not feed_sign_match:
                continue
            page_info = MatchPageInfo(
                event_id=event_id_match.group(1),
                feed_sign=feed_sign_match.group(1),
                home_team=encoded_match.home_team,
                away_team=encoded_match.away_team,
                page_title=f"{encoded_match.home_team} v {encoded_match.away_team}",
                url=candidate.url,
            )
        score = page_info_score(page_info, terms)
        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_page_info = page_info

    if not best_candidate or not best_page_info or best_score[0] <= 0:
        raise ValueError(f"could not resolve FlashScore match page for query: {query}")
    return best_candidate, best_page_info


def configure_query_match(config_path: str, query: str) -> MatchPageInfo:
    config_file = Path(config_path)
    raw = json.loads(config_file.read_text(encoding="utf-8-sig"))
    base_dir = config_file.resolve().parent

    _, page_info = resolve_match_page(query)

    summary_curl = build_summary_curl(page_info.event_id, page_info.feed_sign)

    summary_curl_file = str(raw.get("summary_curl_file") or "summary.curl")
    summary_path = (base_dir / summary_curl_file).resolve()
    summary_path.write_text(summary_curl + "\n", encoding="utf-8")

    raw["name"] = f"{page_info.home_team} vs {page_info.away_team}".strip(" vs ")
    raw["home_team"] = page_info.home_team
    raw["away_team"] = page_info.away_team
    raw["summary_curl"] = ""
    raw["summary_curl_file"] = summary_curl_file
    config_file.write_text(json.dumps(raw, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    return page_info
