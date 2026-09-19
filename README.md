# Email Auto-Reply Bot (Draft Mode)

Reads emails from selected mailboxes, drafts an AI-generated reply using Groq,
and saves it in the mailbox's **Drafts** folder — nothing is ever sent
automatically. You review and hit Send yourself in Outlook.

## 1. Setup

```bash
cd email-responder
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your real values:

```bash
cp .env.example .env
```

```
TENANT_ID=...
CLIENT_ID=...
CLIENT_SECRET=...
GROQ_API_KEY=...
```

(`PUBLIC_BASE_URL` and `WEBHOOK_CLIENT_STATE` aren't needed yet — only once you deploy this and set up live webhooks. See "Going live" below.)

### Option: run with Docker instead (skip the venv/pip steps above)

If you have Docker installed, you can skip the `venv`/`pip install` steps
entirely:

```bash
cp .env.example .env     # fill in your real values first
docker compose up --build
```

The server will be running at `http://localhost:8000` — same as the manual
method. Your `config/mailboxes.json` is mounted into the container, so
editing it on your machine (or via the API) takes effect right away, and
your mailbox list survives container restarts.

To stop it: `docker compose down`
To rebuild after changing code: `docker compose up --build`

This is also the same image you'd deploy to a hosting platform later
(Render, Railway, Azure App Service, etc. — most accept a Dockerfile
directly).

## 2. Add your first mailbox

Edit `config/mailboxes.json` directly, or start the server (next step) and use the API.

```json
{
  "mailboxes": [
    "saif@neuratechltd.com"
  ]
}
```

⚠️ **Important — before this works, your admin (your boss) needs to have granted
"Admin consent" for these Application permissions in Azure Portal
(Entra ID → App registrations → your app → API permissions):**
- `Mail.Read`
- `Mail.Send`

Without that, every request below will fail with a permissions error —
that's expected and not a bug in this code.

## 3. Run the server

```bash
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`. Open `http://localhost:8000/docs`
for an interactive page where you can try every endpoint from your browser
— no Postman needed.

## 4. Test it

**Check your token/connection works — peek at the newest email:**
```
GET http://localhost:8000/test/latest-email?mailbox=saif@neuratechltd.com
```

**Full test — read latest email, generate AI reply, save as draft:**
```
POST http://localhost:8000/test/draft-reply?mailbox=saif@neuratechltd.com
```
Then open Outlook (web or app) for that mailbox → Drafts folder → you should
see the AI-written reply sitting there, ready to review and send.

## 5. Managing which mailboxes are allowed (your "5 mailboxes, adjustable" requirement)

This is controlled entirely by `config/mailboxes.json` — no code changes needed.

**Option A — edit the file directly:**
```json
{
  "mailboxes": [
    "saif@neuratechltd.com",
    "boss@neuratechltd.com",
    "sales@neuratechltd.com",
    "support@neuratechltd.com",
    "hr@neuratechltd.com"
  ]
}
```

**Option B — use the API (handy once deployed, or from the `/docs` page):**
```
GET    /mailboxes                          -> see current list
POST   /mailboxes   {"email": "x@y.com"}   -> add one
DELETE /mailboxes/x@y.com                  -> remove one
```

There's no hard limit coded in — add or remove as many as you like, any time.

## 6. Going live (later — not needed for initial testing)

Right now, you have to manually call `/test/draft-reply` to trigger a reply.
To make it fully automatic (reply drafted the moment an email arrives,
with no manual trigger), two more things are needed:

1. **Deploy this app somewhere with a public HTTPS URL** (Render, Railway,
   Azure App Service, etc.) — Microsoft Graph can't send webhook
   notifications to `localhost`.
2. **Create a Graph subscription** per mailbox, pointing at your deployed
   `/webhook/email` URL, using `graph_client.create_subscription(...)`.
   Subscriptions expire (~60 minutes for messages) and must be renewed on
   a schedule — a small background job (e.g. a scheduled task that runs
   every 30 minutes) should call `create_subscription` again for each
   mailbox before the old one expires.
3. In `main.py`'s `webhook_email` function, the `resource` field tells you
   *which* mailbox the notification is for — you'll need to map that back
   to a plain email address (Graph gives you a user ID, not the address
   directly) and confirm it's in your allowed list before generating a reply.

## 7. Security notes

- Never commit your `.env` file — it holds real secrets.
- If a Client Secret is ever accidentally shared/exposed, regenerate it in
  Azure Portal immediately (Entra ID → App registrations → your app →
  Certificates & secrets).
- This app currently has no authentication on its own endpoints (e.g.
  anyone who can reach `/mailboxes` could add/remove mailboxes). That's
  fine for local testing, but before deploying this publicly, add an API
  key or similar check on these routes.
