#!/usr/bin/env python3
"""Minimal helpers for talking to the local KMS API."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request

DEFAULT_BASE_URL = "http://127.0.0.1:49153"
DEFAULT_TIMEOUT_SECONDS = 30.0


def build_url(base_url: str, path: str) -> str:
    normalized = base_url.rstrip("/")
    return f"{normalized}{path}"


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> dict[str, Any]:
    data: bytes | None = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    req = request.Request(url=url, data=data, method=method, headers=headers)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} when calling {url}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Failed to reach KMS API at {url}: {exc.reason}. "
            "Start the service first if it is not running."
        ) from exc

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON returned by {url}: {raw}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Unexpected response shape from {url}: {parsed!r}")

    return parsed


def print_json(title: str, payload: dict[str, Any]) -> None:
    print(f"{title}:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
