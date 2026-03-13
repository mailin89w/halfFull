# HalfFull — Frontend

Energy assessment interface built with **Next.js 16**, **React 19**, and **Tailwind CSS v4**.

---

## What you'll see

The app is a linear 5-step flow:

| Route | Description |
|---|---|
| `/start` | Landing page — intro and call to action |
| `/assessment` | Step-by-step questionnaire (21 questions on the full path, 15 on the hybrid path). Optional lab PDF/image upload on question 2. |
| `/clarify` | 3 MedGemma-generated follow-up questions, each tagged with the hypothesis being explored (e.g. 🔍 Iron deficiency) |
| `/processing` | Triggers deep analysis via MedGemma; auto-redirects to `/results` when done |
| `/results` | Personalised energy report — spectrum, diagnosis cards, AI summary, doctor kit, PDF download |

The root `/` redirects to `/start`.

Progress is stored in **localStorage** under `halffull_assessment_v1`; MedGemma results are cached in **sessionStorage** so navigating back doesn't re-trigger inference.

---

## Running locally

**Requirements:** Node ≥ 18

```bash
# 1. From the repo root, go into the frontend folder
cd frontend

# 2. Install dependencies (first time only)
npm install

# 3. Start the dev server
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** — the assessment starts immediately.

---

## Other scripts

```bash
npm run build   # Production build
npm run start   # Serve the production build (run build first)
npm run lint    # ESLint check
```

---

## Key files

```
frontend/
├── app/
│   ├── start/page.tsx            # Landing page
│   ├── assessment/page.tsx       # Question-by-question flow
│   ├── clarify/page.tsx          # MedGemma follow-up questions (hypothesis-tagged)
│   ├── processing/page.tsx       # Deep analysis loader, redirects to /results
│   ├── results/page.tsx          # Full energy report + PDF download
│   └── api/
│       ├── extract-labs/         # PDF/image → MedGemma lab text extraction
│       ├── analyze/              # Basic MedGemma insights (fallback)
│       ├── generate-followup/    # Hypothesis-driven clarifying questions
│       └── deep-analyze/         # Full report: summary, doctor kit, next steps
├── src/
│   ├── components/
│   │   ├── QuestionCard.tsx      # Renders a single assessment question
│   │   ├── AnswerSingle.tsx      # Binary / categorical / ordinal answers
│   │   ├── AnswerMultiple.tsx    # Multi-select checkboxes
│   │   ├── AnswerScale.tsx       # 1–10 numeric slider
│   │   ├── AnswerFreeText.tsx    # Open text input
│   │   ├── AnswerFileUpload.tsx  # Lab PDF / image upload with extraction status
│   │   └── results/
│   │       ├── EnergySpectrum.tsx   # "Where you are vs your potential" bar
│   │       ├── DiagnosisCard.tsx    # Per-area card with tests + recovery outlook
│   │       └── DoctorPriority.tsx   # Prioritised specialist referral list
│   ├── hooks/
│   │   └── useAssessment.ts      # Assessment state, routing, localStorage persistence
│   └── lib/
│       ├── questions.ts          # All questions + conditional path logic
│       ├── mockResults.ts        # Scores answers → diagnosis signals
│       ├── formatAnswers.ts      # Converts answer IDs → human-readable text for prompts
│       ├── medgemma.ts           # API fetch helpers, sessionStorage cache, types
│       └── types.ts              # Shared TypeScript interfaces
```

---

## How the assessment paths work

The very first question (`q0.0`) asks whether the user has recent lab results:

- **No lab results (`lab_no`)** → **Full path** — 21 questions across 6 modules: pre-assessment, sleep, nutrition, hormonal, activity, mental health
- **Lab results available (`lab_yes`)** → **Hybrid path** — 15 questions (skips nutrition and hormonal modules; instead uploads a lab PDF or image which MedGemma reads directly)

Several questions are conditional and only appear based on earlier answers (e.g. the restless-legs follow-up only shows if RLS was selected in the sleep issues question).

After the assessment, `/clarify` shows 3 AI-generated questions. Each question is linked to a specific diagnostic hypothesis MedGemma is trying to confirm or rule out — e.g. if iron deficiency is suspected, it asks about periods and red meat intake; if hypothyroidism, it asks about cold intolerance and weight change.

---

## MedGemma AI — running the backend

The app uses **MedGemma 1.5-4b-it** for three things: hypothesis-driven clarifying questions (`/clarify`), deep analysis & doctor kit (`/processing → /results`), and lab PDF interpretation. MedGemma runs on a free Google Colab T4 GPU and is exposed to your local frontend via a Cloudflare tunnel.

### Prerequisites

- Google account with access to [Google Colab](https://colab.research.google.com)
- Hugging Face account — you must **accept the model licence** at
  [huggingface.co/google/medgemma-1.5-4b-it](https://huggingface.co/google/medgemma-1.5-4b-it) before the model will load
- A Hugging Face token with **"Make calls to Inference Providers"** scope —
  [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

### Environment variables

Create `frontend/.env.local` (never commit this file):

```env
# Hugging Face token
HF_API_TOKEN=hf_your_token_here

# Updated each Colab session — see step 3 below
HF_ENDPOINT_URL=https://your-tunnel.trycloudflare.com
```

---

### Colab notebook — 3 cells to run in order

Open a new Colab notebook at [colab.research.google.com](https://colab.research.google.com).
Make sure the runtime is set to **T4 GPU**: Runtime → Change runtime type → T4 GPU.

---

#### Cell 1 — Download cloudflared (~10 seconds)

```python
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
!chmod +x cloudflared
print("✅ Ready")
```

---

#### Cell 2 — Load MedGemma (~5 min on first run, ~1 min after that)

```python
import os, torch
from transformers import pipeline
from huggingface_hub import get_token

# Recommended: add your HF token in Colab → Secrets (🔑 icon, left sidebar)
# Name it HF_TOKEN and enable "Notebook access"
hf_token = get_token() or os.environ.get("HF_TOKEN")
if not hf_token:
    from huggingface_hub import login
    login()
    hf_token = get_token()

pipe = pipeline(
    "image-text-to-text",
    model="google/medgemma-1.5-4b-it",
    token=hf_token,
    device_map="auto",
    dtype=torch.bfloat16,   # halves VRAM: ~4.5 GB instead of ~9 GB
)
print("✅ MedGemma loaded")
```

> **Why bfloat16?** Full float32 uses ~9 GB and leaves no room for inference — the kernel crashes with OOM. bfloat16 uses ~4.5 GB and fits comfortably on a T4.

---

#### Cell 3 — Start Flask server + open Cloudflare tunnel

```python
import os, re, threading, time, subprocess, base64, io
from flask import Flask, request, jsonify
from PIL import Image
import torch

os.system("fuser -k 8000/tcp 2>/dev/null; true")
time.sleep(1)

app = Flask(__name__)

def clean_response(text: str) -> str:
    """Strip MedGemma 1.5 thinking tokens (<unused94>thought\n...) from output."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<unused\d+>thought\n.*?\n\n', '', text, flags=re.DOTALL)
    text = re.sub(r'<unused\d+>[^\n]*\n?', '', text)
    return text.strip()

@app.route("/v1/chat/completions", methods=["POST"])
def chat():
    try:
        body = request.get_json()
        messages = body.get("messages", [])
        max_tokens = min(int(body.get("max_tokens", 400)), 500)  # hard cap — prevents OOM

        hf_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts, images = [], []
                for part in content:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        if url.startswith("data:image"):
                            b64 = url.split(",", 1)[1]
                            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                            images.append(img)
                hf_content = [{"type": "image", "image": img} for img in images]
                if text_parts:
                    hf_content.append({"type": "text", "text": " ".join(text_parts)})
                hf_messages.append({"role": role, "content": hf_content})
            else:
                hf_messages.append({"role": role, "content": content})

        try:
            output = pipe(hf_messages, max_new_tokens=max_tokens, do_sample=False)
        finally:
            torch.cuda.empty_cache()   # free KV-cache after every call — critical

        last = output[0]["generated_text"]
        if isinstance(last, list):
            last = last[-1]
        raw_text = last.get("content", "") if isinstance(last, dict) else str(last)

        return jsonify({
            "choices": [{"message": {"role": "assistant", "content": clean_response(raw_text)}}]
        })

    except Exception as e:
        torch.cuda.empty_cache()
        return jsonify({"error": str(e), "choices": [{"message": {"role": "assistant", "content": ""}}]}), 500

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=8000, use_reloader=False),
    daemon=True,
).start()
time.sleep(2)
print("✅ Flask server running on port 8000")

def run_tunnel():
    proc = subprocess.Popen(
        ["./cloudflared", "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    for line in iter(proc.stdout.readline, b""):
        decoded = line.decode("utf-8", errors="replace")
        if "trycloudflare.com" in decoded:
            url = [w for w in decoded.split() if "trycloudflare.com" in w][0]
            print(f"\n🌐 Tunnel URL: {url}\n")
            print("👉 Copy into frontend/.env.local → HF_ENDPOINT_URL")
            print("   Then restart: npm run dev\n")

threading.Thread(target=run_tunnel, daemon=True).start()
time.sleep(6)
```

---

### Connecting tunnel → frontend (after every Colab session)

1. Copy the URL printed by Cell 3, e.g. `https://word-word-word-word.trycloudflare.com`
2. Paste into `frontend/.env.local`:
   ```env
   HF_ENDPOINT_URL=https://word-word-word-word.trycloudflare.com
   ```
3. Restart the dev server (`Ctrl+C` then `npm run dev`)

> **The tunnel URL changes every time Cell 3 runs.** Each team member runs their own Colab session and updates `.env.local` locally. There is no shared persistent endpoint.

---

### T4 GPU limits — why the caps exist

| Constraint | Reason |
|---|---|
| `max_new_tokens` hard-capped at **500** | MedGemma 1.5-4b-it is a thinking model — it generates ~200 hidden reasoning tokens before the visible answer. Exceeding ~500 total triggers OOM kernel crashes on the T4's 15 GB VRAM. |
| `do_sample=False` | Greedy decoding uses less peak memory than sampling |
| `torch.cuda.empty_cache()` after every call | Releases the KV-cache between requests — without this, VRAM fills after 2–3 calls |
| `dtype=torch.bfloat16` | Required — float32 won't fit (~9 GB vs ~4.5 GB) |

---

### What works without Colab

PDF text extraction and the rule-based scoring work entirely offline. The app gracefully falls back to non-AI content when the tunnel is down.

| Feature | Needs Colab? |
|---|---|
| Assessment questionnaire | No |
| Lab PDF / image upload (text extraction) | No |
| Personalised clarifying questions | Yes |
| Deep analysis, doctor kit, next steps | Yes |
| PDF summary download | No (uses cached result) |
