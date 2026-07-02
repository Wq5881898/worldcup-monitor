# Worldcup Monitor Requirements Baseline

This document is the baseline for business and technical decisions. Update it whenever the monitoring behavior changes.

## Goal

Detect World Cup goals as fast as possible from Flashscore feed endpoints and send Telegram notifications.

Speed is the primary goal. UI polish, dashboards, and generic monitoring features are secondary.

## Confirmed Feed Model

Each match has at least two useful endpoints:

- Summary feed: `https://global.flashscore.ninja/130/x/feed/g_1_<match_id>`
- Event detail feed: `https://global.flashscore.ninja/130/x/feed/df_sui_1_<match_id>`

The summary feed returns compact module hashes:

```text
CA÷...¬CD÷...¬CE÷...¬CF÷...¬...¬A1÷...¬~
```

Confirmed mapping for goal monitoring:

- `CD` changes when the full event list changes.
- `df_sui_1_<match_id>` returns the full event list.
- The event detail response `A1` should equal the summary feed `CD` for the same version.
- `CA` is useful for match status / score confirmation, but it is not the main goal trigger.
- `CF` is not the main goal trigger for the confirmed samples.

The event detail feed contains records such as:

```text
III÷h2HRzOZH¬IA÷1¬IB÷45'¬IE÷3¬INX÷1¬IOX÷0¬IF÷Balogun F.¬ICT÷...¬IK÷Goal¬IM÷rVZLmUsU¬~
```

Goal detection fields:

- `III`: stable event id for de-duplication.
- `IB`: match minute.
- `IA`: team side (`1` home, `2` away).
- `IF`: player name.
- `IK`: event type. Goal events use `Goal`.
- `INX`: home score after the event.
- `IOX`: away score after the event.
- `ICT`: optional event description.

## Runtime Workflow

Initialization:

1. Request the summary feed.
2. Parse and store initial `CD`.
3. Request the event detail feed.
4. Parse all existing `IK=Goal` events.
5. Store their `III` values in `seen_goal_ids`.
6. Initialize current score from the latest goal, if available.
7. Send a Telegram startup message with current score, phase, minute if available, and `CD`.

Loop:

1. Poll the summary feed every `interval_seconds` seconds, default `1`.
2. If `CD` has not changed, stay quiet except optional heartbeat logging.
3. If `CD` changes, request the event detail feed.
4. If detail `A1` does not equal the new `CD`, retry briefly and do not update `last_cd`.
5. Parse all `IK=Goal` events.
6. For every unseen goal `III`, send Telegram immediately.
7. Update current score and `seen_goal_ids`.
8. Write new goal events to a local JSONL log.
9. Set `last_cd` only after detail handling succeeds.
10. Stop when manually interrupted, match-end text is detected, or `ttl_seconds` expires.

## Notification

First version notification format:

```text
GOAL 45' USA 1-0 Bosnia
Balogun F.
```

Team names are inferred from `df_sui` event text when possible. The parser maps `IA=1/2` to team names found inside event text parentheses, for example `Folarin Balogun (USA)`. Configured `home_team` and `away_team` are only fallbacks.

Startup notification format:

```text
MONITOR STARTED
USA 0-0 Bosnia & Herzegovina
Phase: 1st Half
Minute: unknown
CD: abc
```

Parser notes:

- Some `df_sui` responses include the version as `~~A1÷...`; this must be normalized to `A1`.
- If the first summary request returns `204` and no `CD`, initialization may use the detail response `A1` as the initial `last_cd`.

Do not wait for VAR confirmation. The program is optimized for fastest notification.

Goal notifications are repeated by default:

- `goal_repeat_count`: `10`
- `goal_repeat_interval_seconds`: `3.0`

Only goal notifications repeat. Startup notifications are sent once.

## Match End

The first version uses:

- Manual stop with Ctrl+C.
- `ttl_seconds`, default `7200`.
- Conservative text matching for `Full Time`, `Finished`, `After Pen.`, or `Match Finished` if these appear in fetched responses.

## cURL Inputs

The program must accept Chrome DevTools `Copy as cURL (cmd)` format.

The user may provide:

- Both summary and detail cURL commands, or
- Only the summary cURL command when the detail URL can be derived.

Detail URL derivation:

- `.../feed/g_1_<match_id>` -> `.../feed/df_sui_1_<match_id>`

If derivation fails, a detail cURL is required.

## Telegram

Telegram messages are sent to all configured chat IDs.

Goal events are also appended to a local JSONL file, default `logs/goals.jsonl`.

Configuration lookup order:

1. Match config file values.
2. Environment variables.
3. Optional existing qmonitor `config.json`.

Secrets must not be committed to the repository.

For single-match operation, `python -m worldcup_monitor run` reads `match.local.json` if it exists, otherwise `match.json`.

`match.json` is a committed template. Real tokens should go into `match.local.json`, which is ignored by git.

For easiest operation, `summary_curl_file` can point to a text file such as `summary.curl`. The user can paste Chrome DevTools `Copy as cURL (cmd)` into that file with its original line breaks and quotes. This avoids JSON escaping problems. `detail_curl_file` is also supported, but normally unnecessary because `df_sui_1_<match_id>` can be derived from `g_1_<match_id>`.

## Non-Goals For First Version

- No web dashboard.
- No generic JSON alert engine.
- No rich Telegram formatting.
- No VAR correction workflow.
- No multi-match server process unless added later.
