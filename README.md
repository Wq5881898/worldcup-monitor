# worldcup-monitor

Fast Flashscore goal monitor for World Cup matches.

This first version is a command-line tool optimized for low-latency goal alerts. It polls the Flashscore summary feed, follows `CD` changes into the `df_sui` event feed, and sends Telegram messages for new `IK=Goal` events.

See [docs/requirements.md](docs/requirements.md) for the business and technical baseline.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configure

For real matches, copy the template and edit the local file:

```powershell
Copy-Item match.json match.local.json
```

Edit `match.local.json`:

- Paste the `g_1_*` cURL into `summary.curl` exactly as copied from Chrome.
- Leave `detail_curl` empty unless auto-derivation fails.
- Fill `telegram_token` and `telegram_chat_ids`.
- `home_team` and `away_team` can stay empty. The monitor tries to infer team names from `df_sui` event text during initialization.

The default local config points at `summary.curl`, so this works without escaping quotes or newlines:

```powershell
notepad .\summary.curl
```

Telegram credentials can also be provided by environment variables or through an existing qmonitor config file.

Environment variables:

```powershell
$env:TELEGRAM_TOKEN = "123:abc"
$env:TELEGRAM_CHAT_IDS = "111,222"
```

## Run

```powershell
.\.venv\Scripts\python.exe -m worldcup_monitor run
```

The command reads `match.local.json` when it exists. This keeps real Telegram tokens out of git.

The monitor runs until Ctrl+C, match-end detection, or the configured TTL expires.
