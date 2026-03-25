# Modal MedGemma

This deploys `google/medgemma-1.5-4b-it` on Modal and exposes the same API
shape your frontend already expects:

- `POST /v1/chat/completions`
- `GET /health`

## 1. Install Modal locally

```bash
pip install modal
modal setup
```

## 2. Create the Hugging Face secret in Modal

```bash
modal secret create huggingface HF_TOKEN=hf_your_token_here
```

## 3. Deploy

```bash
modal deploy deployment/modal_medgemma.py
```

Modal will print a public base URL. Copy it.

## 4. Wire it into Vercel

Set this in your Vercel project:

```text
HF_ENDPOINT_URL=https://your-modal-url.modal.run
HF_API_TOKEN=hf_your_token_here
```

Your existing Next routes append `/v1/chat/completions`, so `HF_ENDPOINT_URL`
must be the base URL only.

## 5. Test

```bash
curl https://your-modal-url.modal.run/health
```

If that works, the frontend AI routes should start using Modal instead of the
temporary Colab tunnel.

## Notes

- The script uses a `T4`, matching the Colab setup that already worked.
- `min_containers=0` means Modal scales to zero when idle, so you only pay when the app is actually being used.
- `scaledown_window=300` keeps the container warm for up to 5 minutes after a request, which helps with short bursts of traffic.
- Cold starts are expected after longer idle periods.
