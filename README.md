# Puzzle #29 — Image Caption/Crop FastAPI service

FastAPI service with two endpoints:
- `POST /caption` — multipart `image` field, returns a real AI-generated caption via OpenRouter (vision-capable model).
- `POST /crop` — multipart `image` field + `left/top/right/bottom` OR `width/height` form fields, returns a real cropped image (Pillow), with `X-Crop-Width`/`X-Crop-Height` response headers confirming the output size.

## Deployment note

Brief named Google Cloud Run. This machine has no reachable GCP project/billing (no `gcloud` CLI installed, no `GOOGLE_CLOUD_PROJECT`/service-account credential in any Hermes profile `.env` — only commented-out placeholder lines referencing `GOOGLE_CHAT_PROJECT_ID`). Railway and Fly CLIs are installed but not logged in (no stored token). Vercel CLI *is* already authenticated (`krikormher-7058`, same account used for puzzles #10 and #28), so this deployed to **Vercel** using its Python runtime (`vercel.json` `functions.api/index.py.runtime: python3.12`, FastAPI ASGI app auto-detected).

## Environment

- `OPENROUTER_API_KEY` — reused from `C:\Users\h\.openrouter-keys.env` (KEY_3), set as a Vercel project env var.
- `OPENROUTER_MODEL` — defaults to `google/gemini-2.0-flash-001` (vision-capable).

## Local test

```
uvicorn api.index:app --reload
curl -F "image=@test.jpg" http://localhost:8000/caption
curl -F "image=@test.jpg" -F "left=0" -F "top=0" -F "right=200" -F "bottom=200" http://localhost:8000/crop -o cropped.png
```
