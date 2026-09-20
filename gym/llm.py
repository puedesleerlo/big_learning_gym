"""Role routing and provider adapters. Credentials never enter prompts or persisted traces."""

import json
import os
import time
from pathlib import Path

import httpx
from sqlalchemy import func, insert, select, update

from .store import digest, llm_calls, now, uid


class ModelError(ValueError):
    pass


class Router:
    def __init__(self, store, config_path=None, transport=None):
        self.store = store
        self.config_path = Path(config_path or os.getenv("GYM_MODELS_CONFIG", "config/models.json"))
        self.transport = transport

    def config(self):
        return json.loads(self.config_path.read_text())

    def describe(self):
        config = self.config()
        return {
            "roles": config["roles"],
            "providers": {
                k: {
                    "adapter": v["adapter"],
                    "configured": not v.get("api_key_env") or bool(os.getenv(v["api_key_env"])),
                }
                for k, v in config["providers"].items()
            },
            "limits": config["limits"],
        }

    def complete(self, role, system, prompt, json_output=True):
        config = self.config()
        route = config["roles"][role]
        provider = config["providers"][route["provider"]]
        limits = config["limits"]
        key = os.getenv(provider.get("api_key_env") or "", "")
        if provider.get("api_key_env") and not key:
            raise ModelError(f"Set {provider['api_key_env']} on the server to use the {role} role")
        if len(system) + len(prompt) > limits["max_input_characters"]:
            raise ModelError("Source context exceeds the configured input budget; select fewer sources")
        call_id = uid("llm_")
        with self.store.tx() as c:
            count = c.execute(
                select(func.count()).select_from(llm_calls).where(llm_calls.c.created_at >= now()[:10])
            ).scalar_one()
            if count >= limits["max_calls_per_day"]:
                raise ModelError("Daily model-call limit reached. Adjust config/models.json if needed.")
            c.execute(
                insert(llm_calls).values(
                    id=call_id,
                    role=role,
                    provider=route["provider"],
                    model=route["model"],
                    config_hash=digest(config),
                    prompt_hash=digest([system, prompt]),
                    status="running",
                    usage={},
                    created_at=now(),
                )
            )
        headers = {"Content-Type": "application/json"}
        if provider["adapter"] == "anthropic":
            url = provider["base_url"].rstrip("/") + "/messages"
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
            payload = {
                "model": route["model"],
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": route["max_tokens"],
            }
        else:
            url = provider["base_url"].rstrip("/") + "/chat/completions"
            if key:
                headers["Authorization"] = "Bearer " + key
            payload = {
                "model": route["model"],
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                provider.get("token_parameter", "max_tokens"): route["max_tokens"],
            }
            if route.get("reasoning_effort"):
                payload["reasoning_effort"] = route["reasoning_effort"]
            if json_output:
                payload["response_format"] = {"type": "json_object"}
        start = time.monotonic()
        usage = {}
        status = "failed"
        try:
            with httpx.Client(
                timeout=limits["timeout_seconds"], transport=self.transport, follow_redirects=False
            ) as client:
                for attempt in range(limits["max_retries"] + 1):
                    try:
                        response = client.post(url, headers=headers, json=payload)
                    except httpx.TransportError:
                        if attempt < limits["max_retries"]:
                            time.sleep(2**attempt)
                            continue
                        raise ModelError(
                            f"{route['provider']} connection failed; no output was saved"
                        ) from None
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < limits["max_retries"]:
                        time.sleep(2**attempt)
                        continue
                    if response.status_code >= 400:
                        # Do not propagate arbitrary upstream text that could contain credentials or inputs.
                        raise ModelError(
                            f"{route['provider']} returned HTTP {response.status_code} for {route['model']}"
                        )
                    result = response.json()
                    usage = result.get("usage", {})
                    if provider["adapter"] == "anthropic":
                        content = "".join(
                            p.get("text", "") for p in result.get("content", []) if p.get("type") == "text"
                        )
                        truncated = result.get("stop_reason") == "max_tokens"
                    else:
                        choice = result["choices"][0]
                        content = choice["message"].get("content") or ""
                        truncated = choice.get("finish_reason") == "length"
                    if truncated:
                        raise ModelError("Model output was truncated; raise this role's token limit")
                    if not content.strip():
                        raise ModelError("Model returned no final answer")
                    if json_output:
                        cleaned = content.strip()
                        if cleaned.startswith("```"):
                            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
                        try:
                            content = json.loads(cleaned)
                        except json.JSONDecodeError:
                            raise ModelError("Model output failed JSON validation") from None
                    status = "succeeded"
                    return content, {
                        "call_id": call_id,
                        "role": role,
                        "provider": route["provider"],
                        "model": route["model"],
                        "config_hash": digest(config),
                        "prompt_version": "gym-v1",
                    }
            raise ModelError("Provider retries exhausted")
        finally:
            with self.store.tx() as c:
                c.execute(
                    update(llm_calls)
                    .where(llm_calls.c.id == call_id)
                    .values(status=status, usage=usage, elapsed_seconds=round(time.monotonic() - start, 2))
                )
