"""Minimal Anthropic Messages transport for structured image extraction."""

from __future__ import annotations

import base64
import copy
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

API_URL = "https://api.anthropic.com/v1/messages"


class ProviderError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def image_block(path: str | Path) -> dict[str, Any]:
    image = Path(path)
    media_type = mimetypes.guess_type(image.name)[0]
    if media_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise ProviderError(f"Unsupported image type: {image}")
    return {
        "type": "image",
        "source": {
            "type": "base64", "media_type": media_type,
            "data": base64.b64encode(image.read_bytes()).decode("ascii"),
        },
    }


def build_request(*, model: str, image_path: str | Path, prompt: str, tool: Mapping[str, Any], max_tokens: int, system: str) -> dict[str, Any]:
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": [image_block(image_path), {"type": "text", "text": prompt}]}],
        "tools": [copy.deepcopy(dict(tool))],
        "tool_choice": {"type": "tool", "name": tool["name"]},
    }


def tool_input(response: Mapping[str, Any], expected_name: str) -> dict[str, Any]:
    blocks = [block for block in response.get("content", []) if block.get("type") == "tool_use"]
    if len(blocks) != 1 or blocks[0].get("name") != expected_name or not isinstance(blocks[0].get("input"), dict):
        raise ProviderError(f"Expected exactly one {expected_name} tool call")
    return copy.deepcopy(blocks[0]["input"])


class AnthropicClient:
    def __init__(self, api_key: str | None = None, *, timeout: float = 120, retries: int = 2):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is required for live extraction")
        self.timeout = timeout
        self.retries = retries

    def create_message(self, request: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(request, ensure_ascii=False).encode("utf-8")
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(
                API_URL, data=body, method="POST",
                headers={"content-type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    value = json.loads(response.read().decode("utf-8"))
                if not isinstance(value, dict):
                    raise ProviderError("Provider response root is not an object")
                return value
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.retries:
                    raise ProviderError(f"Anthropic HTTP {exc.code}: {detail[:500]}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= self.retries:
                    raise ProviderError(f"Anthropic request failed: {exc}") from exc
            time.sleep(min(2**attempt, 8))
        raise ProviderError("Anthropic request failed")
