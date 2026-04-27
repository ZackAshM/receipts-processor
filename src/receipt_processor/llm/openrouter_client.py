"""OpenRouter HTTP client wrapper for optional semantic receipt extraction."""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib import error, request

from receipt_processor.llm.client_base import (
    LLMConfigurationError,
    LLMExtractionResponse,
    LLMProviderError,
    LLMUnsupportedInputError,
    LLMUsage,
)

SYSTEM_PROMPT = (
    "You are a background semantic extractor for an expense-processing app. "
    "You extract semantic receipt fields into JSON only. "
    "Do not return markdown. Do not include prose. "
    "Do not compute derived business fields. "
    "Only extract candidate values from document meaning.\n\n"
    "transaction_type must be one of: Food, Transportation, Lodging, Misc. "
    "If unclear, use Misc.\n\n"
    "Use all available context sources when provided: "
    "primary receipt file/text, filename hints, notes, and statement excerpts. "
    "Treat notes and statements as supplemental evidence, not guaranteed truth.\n\n"
    "Return a single JSON object with these keys when possible:\n"
    "{"
    "\"document_type\": string|null, "
    "\"merchant_name\": string|null, "
    "\"transaction_date\": string|null, "
    "\"transaction_type\": string|null, "
    "\"currency\": string|null, "
    "\"subtotal\": number|null, "
    "\"tax\": number|null, "
    "\"tip\": number|null, "
    "\"service_charge\": number|null, "
    "\"pre_tip_total\": number|null, "
    "\"amount_paid\": number|null, "
    "\"line_items\": [{\"name\": string, \"amount\": number, \"is_highlighted\": boolean}], "
    "\"contributing_items\": [{\"name\": string, \"amount\": number, \"is_highlighted\": boolean}], "
    "\"noncontributing_items\": [{\"name\": string, \"amount\": number, \"is_highlighted\": boolean}], "
    "\"used_keywords\": {\"field_name\": \"evidence snippet\"}, "
    "\"confidence\": number|null, "
    "\"needs_review\": boolean|null"
    "}.\n"
    "Unknown values should be null or empty arrays/objects."
)

REVIEW_ASSIST_SYSTEM_PROMPT = (
    "You are a background exception-resolution assistant for an expense-processing app. "
    "You are not a chat assistant.\n\n"
    "You receive a JSON payload describing an exception and candidate values from multiple "
    "sources. Your job is to decide whether an obvious, high-confidence resolution exists.\n\n"
    "Rules:\n"
    "- Prefer abstaining when uncertain.\n"
    "- Never invent values.\n"
    "- Only pick values from provided field options.\n"
    "- If evidence is ambiguous or weak, abstain.\n"
    "- Return JSON only.\n\n"
    "Return this JSON shape:\n"
    "{"
    "\"action\": \"resolve\" | \"abstain\", "
    "\"confidence\": number|null, "
    "\"resolved_fields\": {\"field_name\": \"chosen_option_value\"}, "
    "\"reason\": string"
    "}.\n"
    "Confidence is informative only; abstain when not obvious."
)


class OpenRouterClient:
    """Small, swappable OpenRouter API wrapper isolated from pipeline code."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 30.0,
        base_url: str = "https://openrouter.ai/api/v1",
        app_referer: str = "",
        app_title: str = "ReceiptProcessor",
        pdf_engine: str = "",
        input_cost_per_1k_tokens: float | None = None,
        output_cost_per_1k_tokens: float | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")
        self.app_referer = app_referer.strip()
        self.app_title = app_title.strip()
        self.pdf_engine = pdf_engine.strip()
        self.input_cost_per_1k_tokens = input_cost_per_1k_tokens
        self.output_cost_per_1k_tokens = output_cost_per_1k_tokens
        if not self.api_key:
            raise LLMConfigurationError("OPENROUTER_API_KEY is missing.")

    def extract_from_text(
        self,
        *,
        model: str,
        filename: str,
        text: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        context_block = context_text.strip()
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Receipt filename: "
                        f"{filename}\n"
                        "Primary document text:\n"
                        f"{text}\n\n"
                        "Supplemental context:\n"
                        f"{context_block or '[none]'}"
                    ),
                },
            ],
        }
        response = self._post_json("/chat/completions", payload)
        return self._to_extraction_response(response)

    def extract_from_file(
        self,
        *,
        model: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        encoded = base64.b64encode(file_bytes).decode("ascii")
        context_block = context_text.strip() or "[none]"

        if mime_type in {"image/png", "image/jpeg"}:
            content_item: dict[str, Any] = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{encoded}",
                },
            }
        elif mime_type == "application/pdf":
            content_item = {
                "type": "file",
                "file": {
                    "filename": filename,
                    "file_data": f"data:{mime_type};base64,{encoded}",
                },
            }
        else:
            raise LLMUnsupportedInputError(f"Unsupported direct-file MIME type: {mime_type}")

        payload: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Receipt filename: "
                                f"{filename}\n"
                                "Extract semantic fields from the attached receipt file.\n\n"
                                "Supplemental context:\n"
                                f"{context_block}"
                            ),
                        },
                        content_item,
                    ],
                },
            ],
        }
        if mime_type == "application/pdf" and self.pdf_engine:
            payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": self.pdf_engine}}]

        response = self._post_json("/chat/completions", payload)
        return self._to_extraction_response(response)

    def assist_review_resolution(
        self,
        *,
        model: str,
        review_payload: dict[str, Any],
    ) -> LLMExtractionResponse:
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": REVIEW_ASSIST_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Exception review payload JSON:\n"
                        f"{json.dumps(review_payload, ensure_ascii=True)}"
                    ),
                },
            ],
        }
        response = self._post_json("/chat/completions", payload)
        return self._to_extraction_response(response)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_referer:
            headers["HTTP-Referer"] = self.app_referer
        if self.app_title:
            headers["X-Title"] = self.app_title

        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            message = f"OpenRouter API HTTP error: status={exc.code}"
            raise LLMProviderError(message) from exc
        except error.URLError as exc:
            raise LLMProviderError("OpenRouter API connection error.") from exc
        except TimeoutError as exc:
            raise LLMProviderError("OpenRouter API timeout.") from exc
        except Exception as exc:  # pragma: no cover - defensive transport fallback
            raise LLMProviderError(f"OpenRouter API unexpected error: {type(exc).__name__}") from exc

        if int(status) >= 400:
            raise LLMProviderError(f"OpenRouter API returned status={status}.")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("OpenRouter API returned non-JSON response.") from exc
        if isinstance(parsed, dict) and parsed.get("error"):
            raise LLMProviderError(f"OpenRouter API error: {parsed.get('error')}")
        return parsed

    def _to_extraction_response(self, response_json: dict[str, Any]) -> LLMExtractionResponse:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderError("OpenRouter response missing choices.")

        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        message = first_choice.get("message", {})
        content = self._extract_content_text(first_choice, message)
        if not content:
            reason = self._describe_empty_content(first_choice)
            raise LLMProviderError(f"OpenRouter response missing structured content ({reason}).")

        try:
            payload = self._parse_json_payload(content)
        except ValueError as exc:
            raise LLMProviderError("LLM response did not contain valid JSON object.") from exc

        if not isinstance(payload, dict):
            raise LLMProviderError("LLM response JSON must be an object.")

        usage = response_json.get("usage", {})
        prompt_tokens = self._to_int(usage.get("prompt_tokens"))
        completion_tokens = self._to_int(usage.get("completion_tokens"))
        total_tokens = self._to_int(usage.get("total_tokens"))
        estimated_cost = self._estimate_cost(prompt_tokens, completion_tokens)

        return LLMExtractionResponse(
            payload=payload,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
            ),
            response_id=str(response_json.get("id", "")).strip() or None,
        )

    @staticmethod
    def _content_to_string(raw_content: Any) -> str:
        if isinstance(raw_content, str):
            return raw_content.strip()
        if isinstance(raw_content, list):
            text_parts: list[str] = []
            for item in raw_content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
                    continue
                content_value = item.get("content")
                if isinstance(content_value, str):
                    text_parts.append(content_value)
                    continue
                value = item.get("value")
                if isinstance(value, str):
                    text_parts.append(value)
            return "\n".join(text_parts).strip()
        return ""

    @classmethod
    def _extract_content_text(cls, choice: dict[str, Any], message: dict[str, Any]) -> str:
        raw_content = message.get("content", "")
        content = cls._content_to_string(raw_content)
        if content:
            return content

        if isinstance(choice.get("text"), str) and choice.get("text", "").strip():
            return str(choice["text"]).strip()
        if isinstance(choice.get("content"), str) and choice.get("content", "").strip():
            return str(choice["content"]).strip()

        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    continue
                arguments = function.get("arguments")
                if isinstance(arguments, str) and arguments.strip():
                    return arguments.strip()

        function_call = message.get("function_call")
        if isinstance(function_call, dict):
            arguments = function_call.get("arguments")
            if isinstance(arguments, str) and arguments.strip():
                return arguments.strip()
        return ""

    @staticmethod
    def _parse_json_payload(content: str) -> dict[str, Any]:
        text = str(content or "").strip()
        if not text:
            raise ValueError("empty_content")

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise ValueError("missing_json_object")
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, dict):
            raise ValueError("json_not_object")
        return parsed

    @staticmethod
    def _describe_empty_content(choice: dict[str, Any]) -> str:
        keys = sorted(str(key) for key in choice.keys())
        if not keys:
            return "choice_keys=none"
        return f"choice_keys={','.join(keys)}"

    @staticmethod
    def _to_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _estimate_cost(
        self,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> float | None:
        if prompt_tokens is None and completion_tokens is None:
            return None
        if self.input_cost_per_1k_tokens is None or self.output_cost_per_1k_tokens is None:
            return None
        prompt_cost = float(prompt_tokens or 0) / 1000 * self.input_cost_per_1k_tokens
        completion_cost = float(completion_tokens or 0) / 1000 * self.output_cost_per_1k_tokens
        return round(prompt_cost + completion_cost, 6)
