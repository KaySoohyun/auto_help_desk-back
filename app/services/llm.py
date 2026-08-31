"""Capa de conectores LLM (spec §14.2, ADR-002).

Sin SDKs de proveedores: `httpx` contra un endpoint compatible con OpenAI
Chat Completions. Implementaciones HTTP real y mock (para dev/tests).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings, settings


class LLMUnavailableError(RuntimeError):
    """El proveedor LLM no respondió tras los reintentos (fallback seguro)."""


class LLMRateLimitExceeded(Exception):
    """Se excedió el límite de llamadas LLM para el usuario/tenant."""


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    usage: LLMUsage
    duration_seconds: float


class BaseLLMProvider(Protocol):
    """Contrato mínimo de un proveedor LLM."""

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float = 0,
        task: str | None = None,
    ) -> LLMResponse:
        """Ejecuta una llamada de chat y devuelve la respuesta.

        `task` identifica la salida estructurada esperada (p. ej. `classify`,
        `summary`, `reply`); los proveedores reales lo ignoran (el prompt ya lo
        describe) y los mocks lo usan para devolver JSON válido por tarea.
        """


def _openai_payload(messages: list[dict[str, str]], model: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


class HTTPLLMProvider:
    """Proveedor HTTP OpenAI-compatible (chat completions)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        chat_path: str = "/v1/chat/completions",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._chat_path = chat_path if chat_path.startswith("/") else f"/{chat_path}"
        self._api_key = api_key
        self._timeout = timeout_seconds

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float = 0,
        task: str | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}{self._chat_path}",
                headers=headers,
                json=_openai_payload(messages, model, max_tokens, temperature),
            )
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"LLM error {response.status_code}", request=response.request, response=response
                )
            data = response.json()
        usage = data.get("usage", {})
        content = data["choices"][0]["message"]["content"]
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            usage=LLMUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ),
            duration_seconds=time.perf_counter() - started,
        )


class MockLLMProvider:
    """Proveedor simulado determinista para desarrollo y pruebas.

    No usa red ni credenciales. `failure_rate` simula errores para probar
    reintentos/fallback.
    """

    def __init__(self, model: str = "gpt-4o-mini", failure_rate: float = 0.0) -> None:
        self.model = model
        self._failure_rate = failure_rate
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    @staticmethod
    def _mock_content(task: str | None) -> str:
        """JSON válido por tarea para que los parsers reales lo acepten.

        Devuelve salidas estructuralmente correctas (campos que validan
        `classifier`/`summarizer`/`reply_suggester`). El caso default preserva el
        comportamiento histórico `{"ok": true, "task": "mock"}`.
        """
        if task == "classify":
            return json.dumps(
                {
                    "category": "technical",
                    "suggestedPriority": "high",
                    "confidence": 0.9,
                    "warnings": [],
                }
            )
        if task == "summary":
            return json.dumps(
                {
                    "summary": "Resumen determinista de prueba (mock): problema de autenticación reportado.",
                    "missingInformation": None,
                    "confidence": 0.9,
                    "warnings": [],
                }
            )
        if task == "reply":
            return json.dumps(
                {
                    "suggestedReply": "Respuesta determinista de prueba (mock): pedir pasos de reproducción.",
                    "confidence": 0.9,
                    "sources": [],
                    "policyFlags": [],
                    "warnings": [],
                }
            )
        return '{"ok": true, "task": "mock"}'

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float = 0,
        task: str | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        user_message = messages[-1]["content"] if messages else ""
        failure_reached = self._failure_rate > 0 and (self._calls % 2 == 1)
        if failure_reached:
            raise httpx.TimeoutException("mock timeout")
        self._calls += 1
        content = self._mock_content(task)
        return LLMResponse(
            content=content,
            model=model or self.model,
            usage=LLMUsage(prompt_tokens=len(user_message.split()), completion_tokens=len(content.split())),
            duration_seconds=time.perf_counter() - started,
        )


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_CHAT_PATH = "/v1beta/openai/chat/completions"
OPENROUTER_BASE_URL = "https://openrouter.ai/api"
OPENROUTER_CHAT_PATH = "/v1/chat/completions"


def get_llm_provider(settings: Settings) -> BaseLLMProvider:
    """Devuelve el proveedor configurado por env (`LLM_PROVIDER`).

    Valores: `mock` (dev/tests, sin red), `http` (OpenAI-compatible genérico
    con `LLM_BASE_URL`/`LLM_API_KEY`), `gemini` (Google AI Studio vía endpoint
    OpenAI-compatible) u `openrouter`. Sin SDKs: httpx contra chat completions.
    """
    if settings.llm_provider == "gemini":
        api_key = settings.gemini_api_key.get_secret_value()
        if not api_key:
            raise ValueError("GEMINI_API_KEY requerida para LLM_PROVIDER=gemini")
        return HTTPLLMProvider(
            GEMINI_BASE_URL,
            api_key,
            settings.llm_timeout_seconds,
            chat_path=GEMINI_CHAT_PATH,
        )
    if settings.llm_provider == "openrouter":
        api_key = settings.openrouter_api_key.get_secret_value()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY requerida para LLM_PROVIDER=openrouter")
        return HTTPLLMProvider(
            OPENROUTER_BASE_URL,
            api_key,
            settings.llm_timeout_seconds,
            chat_path=OPENROUTER_CHAT_PATH,
        )
    if settings.llm_provider == "http":
        return HTTPLLMProvider(
            settings.llm_base_url,
            settings.llm_api_key.get_secret_value(),
            settings.llm_timeout_seconds,
            chat_path=settings.llm_chat_path,
        )
    if settings.llm_provider == "mock":
        return MockLLMProvider(model=settings.llm_effective_model)
    raise ValueError(f"LLM_PROVIDER inválido: {settings.llm_provider!r}")