"""Dataset de control para la evaluación de clasificación IA (spec §17.2, FR-01).

Casos con salida esperada para verificar que el clasificador produce una
clasificación coherente con la información del ticket. Se usa con un proveedor
mock que devuelve la salida esperada por caso (la evaluación con proveedor real
queda preparada para feature 018).
"""

import json
from typing import TypedDict

from app.services.llm import LLMResponse, LLMUsage


class ClassificationCase(TypedDict):
    subject: str
    description: str
    expected_category: str
    expected_priority: str


CLASSIFICATION_CASES: list[ClassificationCase] = [
    {
        "subject": "No llega la factura de este mes",
        "description": "El cliente indica que no recibió la factura correspondiente al periodo actual y necesita copia.",
        "expected_category": "billing",
        "expected_priority": "medium",
    },
    {
        "subject": "No puedo iniciar sesión en la plataforma",
        "description": "El usuario reporta error de credenciales aunque cambió la contraseña hace una semana.",
        "expected_category": "technical",
        "expected_priority": "high",
    },
    {
        "subject": "Quiero cambiar mi plan a la versión premium",
        "description": "El cliente consulta cómo migrar su suscripción actual a la versión premium.",
        "expected_category": "account",
        "expected_priority": "low",
    },
    {
        "subject": "¿Cuánto cuesta el soporte telefónico?",
        "description": "El cliente pregunta por el costo del servicio de soporte telefónico.",
        "expected_category": "general",
        "expected_priority": "low",
    },
    {
        "subject": "Atención insatisfactoria en la última llamada",
        "description": "El cliente dejó un comentario negativo por la demora en la atención y pide que se revise su caso.",
        "expected_category": "feedback",
        "expected_priority": "low",
    },
    {
        "subject": "Plataforma caída: no se puede operar",
        "description": "El cliente reporta que su equipo no puede acceder a la plataforma y que el servicio está interrumpido para todos los usuarios.",
        "expected_category": "urgent",
        "expected_priority": "urgent",
    },
    {
        "subject": "Consulta sobre trámite administrativo",
        "description": "El cliente desea información general sobre los trámites que puede gestionar en su cuenta, sin especificar un problema concreto.",
        "expected_category": "other",
        "expected_priority": "medium",
    },
]


class MockClassifyProvider:
    """Proveedor mock que devuelve la clasificación esperada de un caso.

    `index` selecciona el caso del dataset. La salida es determinista y válida
    según el schema del clasificador (FR-01).
    """

    def __init__(self, index: int = 0, *, confidence: float = 0.9, warnings: list[str] | None = None) -> None:
        self._case = CLASSIFICATION_CASES[index]
        self._confidence = confidence
        self._warnings = warnings or []

    def complete(self, *, messages, model, max_tokens, temperature=0, task=None) -> LLMResponse:
        case = self._case
        content = json.dumps({
            "category": case["expected_category"],
            "suggestedPriority": case["expected_priority"],
            "confidence": self._confidence,
            "warnings": self._warnings,
        })
        return LLMResponse(
            content=content,
            model="gpt-4o-mini",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10),
            duration_seconds=0.01,
        )
