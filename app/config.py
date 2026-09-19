"""
Manages the list of mailboxes the bot is allowed to read/reply to.

This is deliberately kept as a simple JSON file (not a database) so it's
easy to open and edit by hand, or update through the API endpoints in main.py.
"""

import json
import os

# Path to the config file, relative to this file's location
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "mailboxes.json",
)


def get_mailboxes() -> list[str]:
    """Return the current list of allowed mailboxes."""
    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)
    return data.get("mailboxes", [])


def add_mailbox(email: str) -> list[str]:
    """Add a mailbox to the allowed list (does nothing if it already exists)."""
    mailboxes = get_mailboxes()
    email = email.strip().lower()
    if email not in mailboxes:
        mailboxes.append(email)
        _save(mailboxes)
    return mailboxes


def remove_mailbox(email: str) -> list[str]:
    """Remove a mailbox from the allowed list."""
    mailboxes = get_mailboxes()
    email = email.strip().lower()
    if email in mailboxes:
        mailboxes.remove(email)
        _save(mailboxes)
    return mailboxes


def _save(mailboxes: list[str]) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump({"mailboxes": mailboxes}, f, indent=2)
