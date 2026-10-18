"""feed-watch-agent: watch RSS/Atom feeds and email a digest only when something new appears.

How a run works:
  1. First run: remember everything that already exists and send nothing (seed).
  2. Later runs: keep only the items not seen before (and matching the keywords, if any).
  3. No news -> no email. News -> one email, and the state is saved only if it was sent,
     so a failed send never loses items.

Secrets come from environment variables, never from the repository:
  SMTP_USER, SMTP_PASSWORD   the account used to send the email
  RECIPIENTS                 comma-separated list of addresses that receive it
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feeds import fetch_feed, matches_keywords  # noqa: E402
from notify import build_digest, send_email  # noqa: E402
from state import load_state, save_state  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
STATE_PATH = BASE_DIR / "state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("feed-watch")


def find_new_items(config: dict, state: dict) -> tuple[list[dict], set[str]]:
    """Return (new matching items, ids of every item currently in the feeds)."""
    keywords = config.get("keywords") or []
    seen = set(state["seen_ids"])
    current_ids: set[str] = set()
    new_items: list[dict] = []
    for feed in config.get("feeds", []):
        for item in fetch_feed(feed):
            if item["id"] in current_ids:
                continue
            current_ids.add(item["id"])
            if item["id"] not in seen and matches_keywords(item, keywords):
                new_items.append(item)
    return new_items, current_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Email digest of new items from RSS/Atom feeds")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the email instead of sending it; state is not saved")
    args = parser.parse_args()

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    state = load_state(STATE_PATH)
    new_items, current_ids = find_new_items(config, state)

    if not state["initialized"]:
        logger.info("First run: remembering %s existing item(s), no email sent.", len(current_ids))
        if not args.dry_run:
            save_state(STATE_PATH, {"initialized": True, "seen_ids": sorted(current_ids)})
        return 0

    if not new_items:
        logger.info("No news.")
        return 0

    max_items = config.get("max_items_per_email", 30)
    shown = new_items[:max_items]
    subject, html, text = build_digest(shown, date.today(), config.get("title", "Feed watch"))

    if args.dry_run:
        print(f"SUBJECT: {subject}\n\n{text}")
        return 0

    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    recipients = [r.strip() for r in os.environ.get("RECIPIENTS", "").split(",") if r.strip()]
    if not (user and password and recipients):
        logger.error("Set SMTP_USER, SMTP_PASSWORD and RECIPIENTS (see README).")
        return 1

    smtp = config.get("smtp", {})
    try:
        send_email(smtp.get("host", "smtp.gmail.com"), smtp.get("port", 587),
                   user, password, recipients, subject, html, text)
    except Exception as exc:  # noqa: BLE001 - network/SMTP boundary, report cleanly
        logger.error("Sending failed, state not updated: %s", exc)
        return 1

    save_state(STATE_PATH, {"initialized": True,
                            "seen_ids": sorted(set(state["seen_ids"]) | current_ids)})
    logger.info("Sent %s item(s); state updated.", len(shown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
