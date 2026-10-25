import base64
import io
import os

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image

app = FastAPI(title="Image Caption/Crop API", version="1.0.0")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@app.get("/")
def root():
    return {
        "service": "image-caption-crop-api",
        "endpoints": {
            "POST /caption": "multipart form field 'image' -> {caption: str}",
            "POST /crop": "multipart form field 'image' + left/top/right/bottom (or width/height for center crop) -> cropped image bytes",
        },
    }


@app.post("/caption")
async def caption(image: UploadFile = File(...)):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty image upload")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="not a valid image")

    mime = image.content_type or "image/jpeg"
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in one or two concise sentences, as a real caption for the exact contents of the image. Be specific about objects, people, colors, and setting visible in the image.",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 500,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenRouter error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        message = data["choices"][0]["message"]
        text = message.get("content")
        if not text:
            # some reasoning models put the final answer in `reasoning` when
            # `content` comes back empty/null (e.g. truncated at max_tokens)
            text = message.get("reasoning")
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail=f"unexpected OpenRouter response: {data}")

    if not text:
        raise HTTPException(status_code=502, detail=f"no caption text in OpenRouter response: {data}")

    return JSONResponse({"caption": text.strip(), "model": OPENROUTER_MODEL})


@app.post("/crop")
async def crop(
    image: UploadFile = File(...),
    left: int = Form(None),
    top: int = Form(None),
    right: int = Form(None),
    bottom: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
):
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty image upload")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise HTTPException(status_code=400, detail="not a valid image")

    img_w, img_h = img.size

    if None not in (left, top, right, bottom):
        box = (left, top, right, bottom)
    elif width is not None and height is not None:
        # center crop to requested width/height
        if width > img_w or height > img_h:
            raise HTTPException(
                status_code=400,
                detail=f"requested crop {width}x{height} exceeds source image {img_w}x{img_h}",
            )
        cx, cy = img_w // 2, img_h // 2
        left_c = max(0, cx - width // 2)
        top_c = max(0, cy - height // 2)
        box = (left_c, top_c, left_c + width, top_c + height)
    else:
        raise HTTPException(
            status_code=400,
            detail="provide either left/top/right/bottom or width/height form fields",
        )

    l, t, r, b = box
    if l < 0 or t < 0 or r > img_w or b > img_h or r <= l or b <= t:
        raise HTTPException(status_code=400, detail=f"crop box {box} invalid for image size {img_w}x{img_h}")

    cropped = img.crop(box)

    out = io.BytesIO()
    fmt = (img.format or "PNG")
    save_fmt = "JPEG" if fmt.upper() in ("JPG", "JPEG") else "PNG"
    if save_fmt == "JPEG" and cropped.mode in ("RGBA", "P"):
        cropped = cropped.convert("RGB")
    cropped.save(out, format=save_fmt)
    out.seek(0)

    media_type = "image/jpeg" if save_fmt == "JPEG" else "image/png"
    return Response(
        content=out.getvalue(),
        media_type=media_type,
        headers={
            "X-Crop-Width": str(cropped.width),
            "X-Crop-Height": str(cropped.height),
            "X-Source-Width": str(img_w),
            "X-Source-Height": str(img_h),
        },
    )
