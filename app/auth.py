"""
Gets an access token from Microsoft using the Client Credentials flow
(Tenant ID + Client ID + Client Secret -> access token).

The token is cached in memory and automatically refreshed a little before
it actually expires, so the rest of the app never has to think about this.
"""

import os
import time
import httpx

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

# Simple in-memory cache: { "token": str, "expires_at": epoch_seconds }
_token_cache: dict = {"token": None, "expires_at": 0}


async def get_access_token() -> str:
    """Return a valid access token, fetching a new one only if needed."""
    now = time.time()

    # Reuse the cached token if it still has more than 60 seconds of life left
    if _token_cache["token"] and _token_cache["expires_at"] - now > 60:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )

    response.raise_for_status()
    data = response.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)

    return _token_cache["token"]
