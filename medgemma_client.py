"""
MedGemma client stub.
In production this hits the Colab/Cloudflare tunnel endpoint.
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

ENDPOINT_URL = os.environ.get("MEDGEMMA_ENDPOINT_URL", "http://localhost:8080")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")


def query(prompt: str, timeout: int = 30) -> str:
    """
    Send a prompt to MedGemma and return the raw text response.

    Args:
        prompt: The full prompt string to send.
        timeout: Request timeout in seconds.

    Returns:
        Raw text response from MedGemma.

    Raises:
        requests.exceptions.RequestException: On network or HTTP errors.
    """
    headers = {
        "Content-Type": "application/json",
    }
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.1,
            "do_sample": False,
        },
    }

    logger.debug("Querying MedGemma at %s", ENDPOINT_URL)
    response = requests.post(
        f"{ENDPOINT_URL}/generate",
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    # HuggingFace inference endpoint returns [{"generated_text": "..."}]
    if isinstance(data, list) and data:
        return data[0].get("generated_text", "")
    if isinstance(data, dict):
        return data.get("generated_text", str(data))
    return str(data)
