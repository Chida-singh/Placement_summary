# Placement_summary

This project helps monitor Telegram group messages for placement/event/deadline info.

Secrets and API credentials are intentionally not committed. Instead, provide your own Telegram API credentials using environment variables.

Setup
1. Create a local `.env` file (optional) or set environment variables in your shell.
	- Copy `.env.example` to `.env` and fill in your values, or set these variables directly in your environment:
	  - `TELEGRAM_API_ID` (required)
	  - `TELEGRAM_API_HASH` (required)
	  - `TELEGRAM_GROUP_NAME` (optional)

2. Install optional dependency `python-dotenv` if you want the `.env` file to be auto-loaded:
	- pip install python-dotenv

3. Run the app you want:
	- `python bot.py` (CLI listener)
	- `python placer_widget.py` (Tkinter GUI)

Notes
- The repo no longer includes `apikeys.txt`. Add your keys locally or use environment variables.
- Session files (e.g., `*.session`) are ignored by `.gitignore`. If you switch accounts, remove local session files.
