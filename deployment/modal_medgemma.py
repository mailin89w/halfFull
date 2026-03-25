"""
Modal deployment for MedGemma.

This replaces the Colab notebook's local Flask server + Cloudflare tunnel with
an always-deployable HTTPS endpoint that matches the existing app contract:

    POST /v1/chat/completions

The frontend can keep using:
    HF_ENDPOINT_URL=https://<your-modal-app>.modal.run

Expected secret in Modal:
    modal secret create huggingface HF_TOKEN=hf_xxx

Deploy:
    modal deploy deployment/modal_medgemma.py
"""

import base64
import io
import os
import re
from typing import Any

import modal


app = modal.App("halffull-medgemma")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.115.0",
        "pillow>=10.0.0",
        "torch>=2.3.0",
        "transformers>=4.55.0",
        "accelerate>=0.33.0",
        "huggingface_hub>=0.24.0",
    )
)

_pipe = None


def clean_response(text: str) -> str:
    """Strip MedGemma reasoning/thinking tokens from output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<unused\d+>thought\n.*?\n\n", "", text, flags=re.DOTALL)
    text = re.sub(r"<unused\d+>[^\n]*\n?", "", text)
    return text.strip()


def get_pipeline():
    global _pipe
    if _pipe is not None:
        return _pipe

    import torch
    from transformers import pipeline

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN is not set. Add it as a Modal secret, e.g. "
            "`modal secret create huggingface HF_TOKEN=hf_xxx`."
        )

    _pipe = pipeline(
        "image-text-to-text",
        model="google/medgemma-1.5-4b-it",
        token=hf_token,
        device_map="auto",
        dtype=torch.bfloat16,
    )
    return _pipe


def to_hf_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from PIL import Image

    hf_messages: list[dict[str, Any]] = []

    for msg in messages:
        raw_content = msg.get("content", "")
        if isinstance(raw_content, str):
            raw_content = [{"type": "text", "text": raw_content}]

        hf_content: list[dict[str, Any]] = []
        for part in raw_content:
            part_type = part.get("type")
            if part_type == "image_url":
                url = part.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    _, data = url.split(",", 1)
                    img = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
                    hf_content.append({"type": "image", "image": img})
                elif url:
                    hf_content.append({"type": "image", "url": url})
            elif part_type == "text":
                hf_content.append({"type": "text", "text": part.get("text", "")})

        hf_messages.append({"role": msg.get("role", "user"), "content": hf_content})

    return hf_messages


@app.function(
    image=image,
    gpu="T4",
    timeout=900,
    scaledown_window=300,
    min_containers=0,   # scale to zero when idle; cold-start on the next real request
    secrets=[modal.Secret.from_name("huggingface")],
)
@modal.asgi_app()
def api():
    from fastapi import FastAPI, HTTPException, Request

    web_app = FastAPI(title="HalfFull MedGemma API")

    @web_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @web_app.post("/v1/chat/completions")
    async def chat(request: Request) -> dict[str, Any]:
        data = await request.json()
        messages = data.get("messages", [])
        max_tokens = min(int(data.get("max_tokens") or 400), 500)
        if not messages:
            raise HTTPException(status_code=422, detail="messages field is required")
        try:
            pipe = get_pipeline()
            # Convert system messages to user turn — Gemma chat template
            # doesn't support the system role; fold it into the first user message
            hf_messages = to_hf_messages(messages)
            system_text = ""
            filtered = []
            for m in hf_messages:
                if m.get("role") == "system":
                    parts = m.get("content", [])
                    system_text = " ".join(
                        p.get("text", "") for p in parts
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                else:
                    filtered.append(m)
            if system_text and filtered:
                first_content = filtered[0].get("content", [])
                if first_content and isinstance(first_content, list):
                    first_content.insert(0, {"type": "text", "text": system_text + "\n\n"})
            hf_messages = filtered

            output = pipe(hf_messages, max_new_tokens=max_tokens,
                          do_sample=True, temperature=0.3)

            generated = output[0]["generated_text"]
            last = generated[-1]["content"] if isinstance(generated, list) else generated

            if isinstance(last, list):
                last = " ".join(
                    part.get("text", "")
                    for part in last
                    if isinstance(part, dict) and part.get("type") == "text"
                )

            content = clean_response(str(last))
            return {"choices": [{"message": {"role": "assistant", "content": content}}]}
        except Exception as exc:
            import traceback
            raise HTTPException(status_code=500, detail=f"{exc}\n{traceback.format_exc()}") from exc

    return web_app
