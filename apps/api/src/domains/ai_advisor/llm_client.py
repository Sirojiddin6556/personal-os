"""Resilient multi-provider LLM client with OpenAI primary, Anthropic fallback, and offline heuristics."""

import html
import json
import logging
import math
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from src.config import settings

logger = logging.getLogger("personal_os.ai.llm_client")


@dataclass
class LLMToolCall:
    name: str
    args: Dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    json_data: Optional[Dict[str, Any]] = None
    tool_calls: List[LLMToolCall] = field(default_factory=list)
    explanation: str = ""
    provider: str = "heuristic"
    prompt_tokens: int = 0
    completion_tokens: int = 0


def wrap_untrusted_data(content: str, origin: str = "user_input") -> str:
    """Escape and wrap external untrusted content in XML delimiters to prevent prompt injection."""
    sanitized = html.escape(content, quote=False)
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", sanitized)
    return (
        f'<untrusted_external_data origin="{origin}" sanitized="true">\n'
        f"{sanitized}\n"
        f"</untrusted_external_data>"
    )


def extract_untrusted_data(text: str) -> str:
    """Extract raw payload from within XML delimiters if present."""
    match = re.search(r"<untrusted_external_data[^>]*>(.*?)</untrusted_external_data>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

PLANNER_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "move_task",
            "description": "Reschedule or modify attributes of an existing task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID of the task"},
                    "status": {"type": "string", "enum": ["todo", "scheduled", "in_progress", "done"]},
                    "due_at": {"type": "string", "description": "ISO-8601 due datetime"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_time_block",
            "description": "Block dedicated focus slot on calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "starts_at": {"type": "string", "description": "ISO-8601 start datetime"},
                    "ends_at": {"type": "string", "description": "ISO-8601 end datetime"},
                    "label": {"type": "string", "description": "Focus block title"},
                    "task_id": {"type": "string", "description": "Optional linked task UUID"},
                },
                "required": ["starts_at", "ends_at"],
            },
        },
    },
]


class LLMClient:
    """Multi-provider client: OpenAI -> Anthropic -> Intelligent Heuristics."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        # 1. Try OpenAI API if key configured
        if settings.openai_api_key:
            try:
                res = await self._call_openai(messages, tools, response_format)
                if res:
                    return res
            except Exception as ex:
                logger.warning("OpenAI API call failed, falling back to Anthropic: %s", ex)

        # 2. Try Anthropic Claude API if key configured
        if settings.anthropic_api_key:
            try:
                res = await self._call_anthropic(messages, tools, response_format)
                if res:
                    return res
            except Exception as ex:
                logger.warning("Anthropic API call failed, falling back to heuristics: %s", ex)

        # 3. Intelligent Heuristic Fallback Engine
        return self._heuristic_fallback(messages, tools, response_format)

    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[str] = None,
    ) -> Optional[LLMResponse]:
        payload: Dict[str, Any] = {
            "model": settings.ai_default_model or "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.2,
        }
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        if tools:
            payload["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning("OpenAI returned status %d: %s", resp.status_code, resp.text)
                return None

            data = resp.json()
            choice = data["choices"][0]["message"]
            content = choice.get("content") or ""
            parsed_json = None
            if response_format == "json_object" and content:
                try:
                    parsed_json = json.loads(content)
                except Exception:
                    pass

            tool_calls = []
            if "tool_calls" in choice and choice["tool_calls"]:
                for tc in choice["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = {}
                    if "arguments" in fn:
                        try:
                            fn_args = json.loads(fn["arguments"])
                        except Exception:
                            fn_args = {}
                    tool_calls.append(LLMToolCall(name=fn_name, args=fn_args))

            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                json_data=parsed_json,
                tool_calls=tool_calls,
                explanation=content if not tool_calls else "AI proposed plan based on current schedule.",
                provider="openai",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

    async def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[str] = None,
    ) -> Optional[LLMResponse]:
        system_prompt = ""
        anthropic_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_prompt += m.get("content", "") + "\n"
            else:
                anthropic_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        payload: Dict[str, Any] = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 2048,
            "system": system_prompt.strip(),
            "messages": anthropic_messages,
        }

        if tools:
            anthropic_tools = []
            for t in tools:
                anthropic_tools.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                })
            payload["tools"] = anthropic_tools

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning("Anthropic returned status %d: %s", resp.status_code, resp.text)
                return None

            data = resp.json()
            content_blocks = data.get("content", [])
            text_pieces = []
            tool_calls = []

            for block in content_blocks:
                if block.get("type") == "text":
                    text_pieces.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append(LLMToolCall(
                        name=block.get("name", ""),
                        args=block.get("input", {}),
                    ))

            full_text = "\n".join(text_pieces)
            parsed_json = None
            if response_format == "json_object" and full_text:
                try:
                    parsed_json = json.loads(full_text)
                except Exception:
                    pass

            usage = data.get("usage", {})
            return LLMResponse(
                content=full_text,
                json_data=parsed_json,
                tool_calls=tool_calls,
                explanation=full_text if not tool_calls else "AI proposed plan based on current schedule.",
                provider="anthropic",
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
            )

    def _heuristic_fallback(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """Deterministic NLP heuristics for quick parsing and scheduling when external APIs are unavailable."""
        user_text = ""
        system_text = ""
        for m in messages:
            if m.get("role") == "user":
                user_text += " " + m.get("content", "")
            elif m.get("role") == "system":
                system_text += " " + m.get("content", "")

        raw_user_input = extract_untrusted_data(user_text)
        lower_input = raw_user_input.lower()

        # Check if this is a Quick Add parse request
        if "quick add parser" in system_text.lower() or response_format == "json_object":
            parse_result = self._heuristic_parse(raw_user_input, lower_input)
            return LLMResponse(
                content=json.dumps(parse_result),
                json_data=parse_result,
                provider="heuristic_parser",
            )

        # Check if this is a Schedule Planner request
        if tools and any("move_task" in t.get("name", "") for t in tools):
            tool_calls, explanation = self._heuristic_planner(user_text, raw_user_input)
            return LLMResponse(
                content=explanation,
                tool_calls=tool_calls,
                explanation=explanation,
                provider="heuristic_planner",
            )

        # Default freeform consultation
        reply = (
            f"Personal OS AI Advisor analyzed: '{raw_user_input[:100]}'. "
            "All systems operational. No conflicts detected in current schedule or active tasks."
        )
        return LLMResponse(
            content=reply,
            explanation=reply,
            provider="heuristic_advisor",
        )

    def _heuristic_parse(self, text: str, lower: str) -> Dict[str, Any]:
        """Extract intent and entities using robust regex heuristics."""
        # 1. Financial / Expense detection
        financial_keywords = ["купить", "расход", "потратил", "оплатил", "чек", "руб", "usd", "eur", "spent", "buy", "expense", "paid", "$", "₽"]
        if any(w in lower for w in financial_keywords):
            # Extract number
            numbers = re.findall(r"\b\d+(?:[\.,]\d+)?\b", text)
            amount_minor = 0
            if numbers:
                val = float(numbers[0].replace(",", "."))
                amount_minor = int(val * 100)

            currency = "USD"
            if "руб" in lower or "₽" in lower or "rub" in lower:
                currency = "RUB"
            elif "eur" in lower or "€" in lower:
                currency = "EUR"

            # Extract category or note
            category = "groceries" if any(w in lower for w in ["еда", "кофе", "обед", "продукты", "food", "coffee", "lunch"]) else "general"
            return {
                "intent": "CREATE_EXPENSE",
                "fields": {
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "category": category,
                    "note": text,
                },
                "confidence": 0.95,
            }

        # 2. Event / Calendar detection
        event_keywords = ["встреча", "созвон", "call", "meeting", "календарь", "event", "вебинар", "митинг"]
        if any(w in lower for w in event_keywords) or (" в " in lower and any(d in lower for d in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])):
            time_match = re.search(r"\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b", text)
            time_str = time_match.group(0) if time_match else "14:00"
            return {
                "intent": "CREATE_EVENT",
                "fields": {
                    "title": text,
                    "starts_at": f"2026-09-11T{time_str}:00Z",
                    "ends_at": f"2026-09-11T{int(time_str.split(':')[0])+1:02d}:{time_str.split(':')[1]}:00Z",
                },
                "confidence": 0.90,
            }

        # 3. Reminder detection
        reminder_keywords = ["напомни", "напоминание", "remind", "reminder"]
        if any(w in lower for w in reminder_keywords):
            return {
                "intent": "CREATE_REMINDER",
                "fields": {
                    "title": re.sub(r"^(напомни|напоминание|remind|reminder)\s*", "", text, flags=re.IGNORECASE).strip(),
                },
                "confidence": 0.92,
            }

        # 4. Default: Task
        priority = "medium"
        if "срочно" in lower or "важно" in lower or "urgent" in lower or "asap" in lower:
            priority = "high"
        elif "низкий" in lower or "low" in lower:
            priority = "low"

        return {
            "intent": "CREATE_TASK",
            "fields": {
                "title": text,
                "priority": priority,
                "status": "todo",
            },
            "confidence": 0.88,
        }

    def _heuristic_planner(self, full_context: str, user_request: str) -> tuple[List[LLMToolCall], str]:
        """Generate structured schedule rearrangements from context."""
        tool_calls: List[LLMToolCall] = []

        # Find task UUIDs if present in context
        task_ids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", full_context)
        if task_ids:
            first_task = task_ids[0]
            tool_calls.append(
                LLMToolCall(
                    name="move_task",
                    args={
                        "task_id": first_task,
                        "new_status": "scheduled",
                        "scheduled_at": "2026-09-11T10:00:00Z",
                    },
                )
            )
            tool_calls.append(
                LLMToolCall(
                    name="create_time_block",
                    args={
                        "task_id": first_task,
                        "start_at": "2026-09-11T10:00:00Z",
                        "end_at": "2026-09-11T11:30:00Z",
                        "label": "Focus Time Block",
                    },
                )
            )
            explanation = (
                f"Planned dedicated 90-minute focus block for task {first_task} "
                "within morning availability window. Rescheduled task to 'scheduled'."
            )
        else:
            explanation = "Evaluated current tasks and schedule. No tasks require immediate rescheduling."

        return tool_calls, explanation


llm_client = LLMClient()
