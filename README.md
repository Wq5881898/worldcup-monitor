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

Create a local match config from the example:

```powershell
Copy-Item config.example.json match.local.json
```

Fill `summary_curl`, `detail_curl`, `home_team`, and `away_team`.

Telegram credentials can be provided in the match config, by environment variables, or through an existing qmonitor config file.

Environment variables:

```powershell
$env:TELEGRAM_TOKEN = "123:abc"
$env:TELEGRAM_CHAT_IDS = "111,222"
```

## Run

```powershell
.\.venv\Scripts\python.exe -m worldcup_monitor run --config match.local.json
```

The monitor runs until Ctrl+C, match-end detection, or the configured TTL expires.
