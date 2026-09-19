"""
Email auto-reply bot (draft mode).

Endpoints:
  GET  /mailboxes                 -> list currently allowed mailboxes
  POST /mailboxes                 -> add a mailbox  {"email": "x@company.com"}
  DELETE /mailboxes/{email}       -> remove a mailbox
  GET  /test/latest-email         -> peek at the newest email (no reply made)
  POST /test/draft-reply          -> read latest email -> ONE AI reply -> save as draft
  POST /test/draft-reply-variations -> same, but generates 2-5 reply options,
                                        each saved as its own draft for you to pick from
  POST /webhook/email             -> receives live notifications from Microsoft Graph
                                      (only works once this app is deployed with a public URL)

Run locally with:
  uvicorn app.main:app --reload
"""

import os
from dotenv import load_dotenv

load_dotenv()  # loads variables from a local .env file, if present

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from app import config
from app import graph_client
from app import llm

app = FastAPI(title="Email Auto-Reply Bot")

WEBHOOK_CLIENT_STATE = os.environ.get("WEBHOOK_CLIENT_STATE", "change-this")


# ---------- Mailbox management ----------

class MailboxIn(BaseModel):
    email: str


@app.get("/mailboxes")
def list_mailboxes():
    """See which mailboxes are currently enabled for auto-reply."""
    return {"mailboxes": config.get_mailboxes()}


@app.post("/mailboxes")
def add_mailbox(payload: MailboxIn):
    """Add a mailbox to the enabled list (this is how you 'increase the number of 5')."""
    mailboxes = config.add_mailbox(payload.email)
    return {"mailboxes": mailboxes}


@app.delete("/mailboxes/{email}")
def remove_mailbox(email: str):
    """Remove a mailbox from the enabled list (this is how you 'decrease the number')."""
    mailboxes = config.remove_mailbox(email)
    return {"mailboxes": mailboxes}


# ---------- Manual testing (no webhook/public URL needed) ----------

@app.get("/test/latest-email")
async def test_latest_email(mailbox: str = Query(..., description="e.g. saif@neuratechltd.com")):
    """Just fetch the newest email in a mailbox, to confirm the connection works."""
    _check_allowed(mailbox)
    messages = await graph_client.list_recent_messages(mailbox, top=1)
    if not messages:
        return {"message": "No emails found."}
    return messages[0]


@app.post("/test/draft-reply")
async def test_draft_reply(mailbox: str = Query(..., description="e.g. saif@neuratechltd.com")):
    """
    Full pipeline test, run manually (safe to call as many times as you like):
      1. Get the newest email in the mailbox
      2. Generate an AI reply with Groq
      3. Save that reply as a DRAFT (does not send)
    """
    _check_allowed(mailbox)

    messages = await graph_client.list_recent_messages(mailbox, top=1)
    if not messages:
        return {"message": "No emails found to reply to."}

    latest = messages[0]
    message_id = latest["id"]

    # Fetch the full message so we get the complete body, not just a short preview
    full_message = await graph_client.get_message(mailbox, message_id)
    subject = full_message.get("subject", "")
    body_content = graph_client.extract_plain_text(full_message)

    reply_text = await llm.generate_reply(subject, body_content)
    draft = await graph_client.create_draft_reply(mailbox, message_id, reply_text)

    return {
        "replied_to_subject": subject,
        "ai_generated_reply": reply_text,
        "draft_created": True,
        "draft_id": draft.get("id"),
    }


@app.post("/test/draft-reply-variations")
async def test_draft_reply_variations(
    mailbox: str = Query(..., description="e.g. saif@neuratechltd.com"),
    count: int = Query(3, ge=2, le=5, description="How many reply options to generate (2-5)"),
):
    """
    Same as /test/draft-reply, but generates several different reply options
    and saves EACH ONE as its own separate draft. Open Outlook's Drafts
    folder, read through them, pick the one you like best, send it, and
    delete the other unused drafts.
    """
    _check_allowed(mailbox)

    messages = await graph_client.list_recent_messages(mailbox, top=1)
    if not messages:
        return {"message": "No emails found to reply to."}

    latest = messages[0]
    message_id = latest["id"]

    full_message = await graph_client.get_message(mailbox, message_id)
    subject = full_message.get("subject", "")
    body_content = graph_client.extract_plain_text(full_message)

    variations = await llm.generate_reply_variations(subject, body_content, count=count)

    created_drafts = []
    for i, reply_text in enumerate(variations, start=1):
        # Label each draft so they're distinguishable in the Drafts folder —
        # remove this label line yourself before actually sending the chosen one
        labeled_text = f"[Option {i} of {len(variations)} — AI draft, review before sending]\n\n{reply_text}"
        draft = await graph_client.create_draft_reply(mailbox, message_id, labeled_text)
        created_drafts.append({"option": i, "reply_text": reply_text, "draft_id": draft.get("id")})

    return {
        "replied_to_subject": subject,
        "drafts_created": len(created_drafts),
        "options": created_drafts,
    }


# ---------- Webhook (for later, once deployed with a public URL) ----------

@app.post("/webhook/email")
async def webhook_email(request: Request):
    """
    Microsoft Graph calls this automatically when a new email arrives,
    IF a subscription has been created pointing here. Not usable on
    localhost — needs a real public HTTPS URL once deployed.
    """
    # Step 1: Graph sends a one-time validation request when the subscription
    # is first created — it expects the validationToken echoed back as plain text.
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(validation_token)

    # Step 2: Normal notification — process each changed message
    payload = await request.json()
    for notification in payload.get("value", []):
        if notification.get("clientState") != WEBHOOK_CLIENT_STATE:
            continue  # ignore notifications that don't match our secret

        resource = notification.get("resource", "")
        # resource looks like: users/{mailbox-id}/messages/{message-id}
        # Parsing the real mailbox address out of this reliably needs the
        # mailbox's Graph user ID, which is a detail to wire up once you're
        # ready to deploy this — see README "Going live" section.

    return {"status": "received"}


def _check_allowed(mailbox: str) -> None:
    if mailbox not in config.get_mailboxes():
        raise HTTPException(
            status_code=403,
            detail=f"'{mailbox}' is not in the allowed mailboxes list. "
                   f"Add it first via POST /mailboxes.",
        )
    