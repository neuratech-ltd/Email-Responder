"""
Thin wrapper around the Microsoft Graph API calls this project needs:
- list recent messages in a mailbox
- get one message's full content
- create a DRAFT reply (never auto-sends)
- create / renew a webhook subscription (used later, once deployed publicly)
"""

import re
import httpx
from app.auth import get_access_token

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def extract_plain_text(message: dict) -> str:
    """
    Graph returns the email body as HTML by default. Strip tags down to
    plain text before sending it to the LLM (keeps prompts cleaner/shorter).
    """
    body = message.get("body", {})
    content = body.get("content", "") or message.get("bodyPreview", "")

    if body.get("contentType") == "html":
        content = re.sub(r"<[^>]+>", " ", content)  # strip HTML tags
        content = re.sub(r"\s+", " ", content).strip()

    return content


async def _headers() -> dict:
    token = await get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def list_recent_messages(mailbox: str, top: int = 5) -> list[dict]:
    """Get the most recent messages in a mailbox's inbox."""
    url = f"{GRAPH_BASE}/users/{mailbox}/mailFolders/Inbox/messages"
    params = {"$top": top, "$orderby": "receivedDateTime desc"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=await _headers(), params=params)
    response.raise_for_status()
    return response.json().get("value", [])


async def get_message(mailbox: str, message_id: str) -> dict:
    """Get one message's full content by its ID."""
    url = f"{GRAPH_BASE}/users/{mailbox}/messages/{message_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=await _headers())
    response.raise_for_status()
    return response.json()


async def create_draft_reply(mailbox: str, message_id: str, reply_text: str) -> dict:
    """
    Create a DRAFT reply to a message (does NOT send it).
    The draft appears in the mailbox's Drafts folder, ready for a human to
    review, edit, and send manually from Outlook.
    """
    url = f"{GRAPH_BASE}/users/{mailbox}/messages/{message_id}/createReply"
    body = {"comment": reply_text}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=await _headers(), json=body)
    response.raise_for_status()
    return response.json()


async def create_subscription(mailbox: str, notification_url: str, client_state: str) -> dict:
    """
    Ask Microsoft Graph to notify our webhook whenever a new email arrives
    in this mailbox. Only usable once this app has a real public URL.
    Subscriptions expire and must be renewed (max ~4230 minutes for messages).
    """
    from datetime import datetime, timedelta, timezone

    url = f"{GRAPH_BASE}/subscriptions"
    expiration = (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat()

    body = {
        "changeType": "created",
        "notificationUrl": notification_url,
        "resource": f"/users/{mailbox}/mailFolders('Inbox')/messages",
        "expirationDateTime": expiration,
        "clientState": client_state,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=await _headers(), json=body)

       
    response.raise_for_status()
    return response.json()
