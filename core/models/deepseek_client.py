import os
import httpx
from typing import Dict, List, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

logger = logging.getLogger(__name__)


class DeepSeekFatalError(Exception):
    """
    A failure no amount of retrying will fix: no balance, bad key, unknown
    model. Raised outside the retry predicate so it surfaces immediately with
    a readable message instead of three wasted attempts and a RetryError that
    hides the cause.
    """


class DeepSeekClient:
    # DeepSeek API client for code generation
    # Documented base URL as of 2026-09. "/v1" is still accepted as an
    # OpenAI-SDK-compatibility alias but is no longer the documented form.
    BASE_URL = "https://api.deepseek.com"

    # Current model IDs (see api-docs.deepseek.com/quick_start/pricing):
    #   deepseek-flash   -> DeepSeek-V4.1-Flash, 1M context, 384K max output
    #   deepseek-v4-pro  -> DeepSeek-V4-Pro-0813 (routed to V4.1-Flash from 2026-09-14)
    # The legacy names deepseek-chat / deepseek-reasoner were retired 2026-07-24.
    DEFAULT_MODEL = "deepseek-flash"

    def __init__(
        self,
        api_key: str,
        model: str = None,
        base_url: str = None,
        thinking: bool = None,
        reasoning_effort: str = None
    ):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", self.BASE_URL),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            # Thinking mode produces reasoning tokens before the answer, so
            # responses take noticeably longer than non-thinking ones.
            timeout=httpx.Timeout(600.0, connect=30.0),  # 10 min total, 30s connect
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self.model = model or os.getenv("DEEPSEEK_MODEL", self.DEFAULT_MODEL)

        # Thinking mode moved from a separate model name (the retired
        # deepseek-reasoner) to a request parameter. On by default at high
        # effort: this is a code-generation workload, where reasoning quality
        # matters more than latency.
        if thinking is None:
            thinking = os.getenv("DEEPSEEK_THINKING", "true").lower() not in ("false", "0", "no")
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort or os.getenv("DEEPSEEK_REASONING_EFFORT", "high")

        logger.info(
            f"DeepSeek client: model={self.model} thinking={self.thinking} "
            f"reasoning_effort={self.reasoning_effort if self.thinking else 'n/a'}"
        )

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 8192,
        temperature: float = 0.3,  # Lower for code
        thinking: bool = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a completion from the configured DeepSeek model.

        Set thinking=False to override the client default for a single call
        (useful for cheap, mechanical prompts where reasoning adds latency
        without adding quality).
        """
        use_thinking = self.thinking if thinking is None else thinking

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        if use_thinking:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = self.reasoning_effort

        try:
            # Inherit the client timeout (10 min) — a per-request override here
            # would silently cap thinking-mode responses at a shorter limit.
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            
            # With thinking enabled the chain of thought arrives in
            # reasoning_content and the actual answer in content. Never
            # substitute one for the other: reasoning is prose about the code,
            # not the code, and passing it downstream would be written to disk
            # and served as a game.
            message_content = choice["message"].get("content", "")
            reasoning_content = choice["message"].get("reasoning_content", "")
            finish_reason = choice.get("finish_reason")

            if not message_content:
                if reasoning_content and finish_reason == "length":
                    logger.error(
                        "❌ Token budget exhausted during reasoning — no answer was produced. "
                        f"Raise max_tokens (currently {max_tokens}) or lower reasoning_effort."
                    )
                    raise ValueError(
                        "DeepSeek ran out of tokens while reasoning; no content returned"
                    )
                logger.error("❌ Empty response from DeepSeek API")
                raise ValueError("Empty response from DeepSeek API")

            if finish_reason == "length":
                logger.warning(
                    f"⚠️  Response hit the {max_tokens}-token cap and is truncated — "
                    "downstream code should treat this as a failed attempt."
                )

            return {
                "content": message_content,
                "reasoning": reasoning_content,
                "model": data["model"],
                "tokens_used": data["usage"]["total_tokens"],
                "finish_reason": finish_reason,
                "truncated": finish_reason == "length"
            }
        except httpx.HTTPStatusError as e:
            # Better error handling for 400 errors
            error_detail = ""
            status_code = e.response.status_code if e.response else None
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = f" - {error_data.get('error', {}).get('message', '')}"
                except:
                    error_detail = f" - {e.response.text[:200]}"
            
            # Log detailed error information
            logger.error(f"DeepSeek API error (Status {status_code}): {e}{error_detail}")
            
            # Log payload size for debugging
            import json as json_lib
            payload_size = len(json_lib.dumps(payload))
            if payload_size > 100000:  # > 100KB
                logger.warning(f"⚠️  Large payload size: {payload_size} bytes - may cause 400 errors")
            
            # Check for common issues
            if status_code == 402 or "insufficient balance" in error_detail.lower():
                logger.error("❌ DeepSeek balance exhausted. Top up at https://platform.deepseek.com")
                raise DeepSeekFatalError(
                    "DeepSeek account has no credit left. Top up at "
                    "https://platform.deepseek.com and try again."
                ) from e
            if status_code == 401:
                logger.error("❌ DeepSeek API key is invalid or missing.")
                raise DeepSeekFatalError(
                    "DeepSeek API key is invalid or missing. Check DEEPSEEK_API_KEY in core/.env."
                ) from e
            if status_code == 400:
                logger.error("❌ DeepSeek bad request. Check model name and payload format.")
                raise DeepSeekFatalError(
                    f"DeepSeek rejected the request ({error_detail.strip() or 'bad request'})."
                ) from e
            if status_code == 429:
                logger.error("❌ DeepSeek rate limit exceeded; will retry.")

            raise
        except httpx.HTTPError as e:
            error_msg = str(e)
            logger.error(f"DeepSeek API connection error: {e}")
            
            # Check for specific connection issues
            if "incomplete chunked read" in error_msg or "peer closed connection" in error_msg:
                logger.warning("⚠️  Connection closed prematurely - this is often a transient network issue")
                logger.info("   The system will automatically retry (up to 3 times)")
                logger.info("   If this persists, check your internet connection or DeepSeek API status")
            elif "timeout" in error_msg.lower():
                logger.warning("⚠️  Request timed out - DeepSeek may be processing a large response")
                logger.info("   The system will automatically retry with longer timeout")
            else:
                logger.error("   This could be a network issue or API endpoint problem.")
            
            # Re-raise to trigger retry
            raise
        except Exception as e:
            logger.error(f"DeepSeek API unexpected error: {e}", exc_info=True)
            raise
    
    async def health_check(self) -> bool:
        """Check API health"""
        try:
            # No thinking: a liveness probe should be fast and cheap.
            await self.generate(
                messages=[{"role": "user", "content": "print('test')"}],
                max_tokens=10,
                thinking=False
            )
            return True
        except:
            return False
    
    async def close(self):
        """Cleanup"""
        await self.client.aclose()
