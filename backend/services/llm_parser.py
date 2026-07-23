"""
llm_parser.py

Uses the Mistral API's chat completions endpoint to extract structured
fields from free-text dispute evidence submissions, including
signature_confirmation and policy_compliance -- used by the resolve
pipeline's feature-vector construction (with a keyword-based fallback in
evidence_signals.py when these come back null, e.g. because the LLM isn't
configured or couldn't parse the response).

Requires MISTRAL_API_KEY to be set, either as an environment variable or in
a .env file in the current working directory (loaded via python-dotenv).
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"

SYSTEM_PROMPT = (
    "You are a data extraction engine. Extract the following fields from the "
    "dispute evidence text: date, amount, tracking_number, delivery_status, "
    "invoice_present (bool), refund_policy_match (bool), signature_confirmation "
    "(bool -- true only if the text indicates a signature or delivery "
    "confirmation was actually obtained/on file; false if it explicitly says "
    "no signature was obtained; null if not mentioned), policy_compliance "
    "(bool -- true only if the text indicates the merchant complied with its "
    "own stated policy, e.g. return/refund policy; false if it indicates a "
    "policy violation; null if not mentioned). If a field cannot be found, "
    "return null for it. Return ONLY a valid JSON object, no explanation, no "
    "markdown formatting, no code fences."
)

JSON_ONLY_REMINDER = "Return valid JSON only, nothing else."


def _call_mistral(messages: list[dict]) -> str:
    """Send a chat completion request to the Mistral API and return the
    raw text content of the model's reply."""

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY is not set. Add it to your environment or to a "
            ".env file in the working directory."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
    }

    response = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _try_parse_json(text: str):
    """Return the parsed dict, or None if `text` isn't valid JSON."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def parse_evidence(raw_text: str) -> dict:
    """
    Extract structured fields (date, amount, tracking_number,
    delivery_status, invoice_present, refund_policy_match,
    signature_confirmation, policy_compliance) from raw dispute evidence
    text using the Mistral API.

    Retries once with an added JSON-only reminder if the first response
    isn't valid JSON. If it still isn't valid JSON, returns
    {"parse_error": True, "raw_response": <the text>}.
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]

    content = _call_mistral(messages)
    parsed = _try_parse_json(content)
    if parsed is not None:
        return parsed

    # Retry once with an added reminder to return JSON only.
    retry_messages = messages + [
        {"role": "assistant", "content": content},
        {"role": "user", "content": JSON_ONLY_REMINDER},
    ]
    retry_content = _call_mistral(retry_messages)
    parsed = _try_parse_json(retry_content)
    if parsed is not None:
        return parsed

    return {"parse_error": True, "raw_response": retry_content}


if __name__ == "__main__":
    sample_text = (
        "Order #4521 shipped on March 3rd for $89.99. Tracking number "
        "1Z999AA10123456784. Package marked delivered. No signature on file."
    )

    print("Input evidence text:")
    print(f"  {sample_text}\n")

    try:
        result = parse_evidence(sample_text)
        print("Parsed result:")
        print(json.dumps(result, indent=2))
    except RuntimeError as e:
        print(f"Could not call Mistral API: {e}")
