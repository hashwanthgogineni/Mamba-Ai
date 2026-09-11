#!/usr/bin/env python3
"""
Verify the DeepSeek API is reachable and that the configured model works.

Run from the repo root (needs DEEPSEEK_API_KEY in core/.env or the environment):

    python core/scripts/check_deepseek.py

Checks, in order:
  1. Which model IDs the account can actually list
  2. The configured model answers a trivial prompt
  3. Thinking mode returns reasoning_content alongside content
  4. The retired deepseek-chat name is in fact dead
  5. Both base URL forms (with and without /v1) resolve
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
OK, FAIL, WARN = f"{GREEN}PASS{RESET}", f"{RED}FAIL{RESET}", f"{YELLOW}WARN{RESET}"


def load_api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    env_path = ROOT / "core" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


async def list_models(client: httpx.AsyncClient) -> None:
    print("\n[1] Models the account can list")
    try:
        r = await client.get("/models")
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", [])]
        print(f"    {OK}  {', '.join(ids) or '(none returned)'}")
    except Exception as e:
        print(f"    {FAIL}  {type(e).__name__}: {e}")


async def try_completion(client: httpx.AsyncClient, model: str, thinking: bool) -> dict | None:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 2048 if thinking else 32,
        "temperature": 0,
    }
    if thinking:
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = os.getenv("DEEPSEEK_REASONING_EFFORT", "high")

    r = await client.post("/chat/completions", json=payload)
    if r.status_code != 200:
        detail = r.text[:180].replace("\n", " ")
        raise RuntimeError(f"HTTP {r.status_code} — {detail}")
    data = r.json()
    choice = data["choices"][0]
    return {
        "content": (choice["message"].get("content") or "").strip(),
        "reasoning": (choice["message"].get("reasoning_content") or "").strip(),
        "model": data.get("model"),
        "finish_reason": choice.get("finish_reason"),
        "tokens": data.get("usage", {}).get("total_tokens"),
    }


async def main() -> int:
    api_key = load_api_key()
    if not api_key or api_key.startswith("sk-your"):
        print(f"{RED}No DEEPSEEK_API_KEY found.{RESET}")
        print("Set it in core/.env or export it, then re-run.")
        return 2

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(180.0, connect=30.0)

    print(f"{DIM}base_url = {base}{RESET}")
    print(f"{DIM}model    = {model}{RESET}")

    failures = 0

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=timeout) as client:
        await list_models(client)

        print(f"\n[2] '{model}' answers a trivial prompt (no thinking)")
        try:
            res = await try_completion(client, model, thinking=False)
            print(f"    {OK}  content={res['content']!r} "
                  f"served_by={res['model']} finish={res['finish_reason']} tokens={res['tokens']}")
        except Exception as e:
            print(f"    {FAIL}  {e}")
            failures += 1

        print(f"\n[3] '{model}' with thinking enabled")
        try:
            res = await try_completion(client, model, thinking=True)
            has_reasoning = bool(res["reasoning"])
            status = OK if res["content"] else FAIL
            if not res["content"]:
                failures += 1
            print(f"    {status}  content={res['content']!r} "
                  f"reasoning_content={'present' if has_reasoning else 'ABSENT'} "
                  f"finish={res['finish_reason']} tokens={res['tokens']}")
            if not has_reasoning:
                print(f"    {WARN}  No reasoning_content — thinking may be ignored for this model.")
        except Exception as e:
            print(f"    {FAIL}  {e}")
            failures += 1

        print("\n[4] Retired 'deepseek-chat' name (expected to fail)")
        try:
            res = await try_completion(client, "deepseek-chat", thinking=False)
            print(f"    {WARN}  Still answering (served_by={res['model']}) — "
                  f"legacy alias not yet enforced, but do not rely on it.")
        except Exception as e:
            print(f"    {OK}  Correctly rejected — {str(e)[:110]}")

    print("\n[5] Base URL forms")
    for candidate in ("https://api.deepseek.com", "https://api.deepseek.com/v1"):
        async with httpx.AsyncClient(base_url=candidate, headers=headers, timeout=timeout) as c:
            try:
                res = await try_completion(c, model, thinking=False)
                print(f"    {OK}  {candidate}  -> {res['content']!r}")
            except Exception as e:
                print(f"    {FAIL}  {candidate}  -> {str(e)[:110]}")
                failures += 1

    print()
    if failures:
        print(f"{RED}{failures} check(s) failed.{RESET}")
    else:
        print(f"{GREEN}All checks passed — the model is returning output.{RESET}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
