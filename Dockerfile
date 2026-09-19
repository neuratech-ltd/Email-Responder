# Small, fast base image with Python
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching — only reinstalls if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# The mailboxes config needs to be writable (add/remove mailboxes via the API
# writes to this file) — see docker-compose.yml for how it's mounted as a
# volume so your edits survive container restarts.

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
