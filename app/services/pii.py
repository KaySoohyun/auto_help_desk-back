from dataclasses import dataclass, field
from hashlib import sha256
import re
import secrets

PII_EMAIL = "email"
PII_PHONE = "phone"
PII_CARD = "card"
PII_ID_DOCUMENT = "id_number"
PII_PASSPORT = "passport"
PII_BIRTH_DATE = "birth_date"
PII_IP = "ip_address"
PII_INTERNAL_URL = "internal_url"

PII_TYPES = (
    PII_EMAIL,
    PII_PHONE,
    PII_CARD,
    PII_ID_DOCUMENT,
    PII_PASSPORT,
    PII_BIRTH_DATE,
    PII_IP,
    PII_INTERNAL_URL,
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Orden importa: los patrones más específicos primero y con ancho variable;
    # la detección es no-solapada (un span ya cubierto no se re-procesa).
    (PII_IP, re.compile(
        r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
    )),
    (PII_CARD, re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
    (PII_ID_DOCUMENT, re.compile(r"\b[XYZ]?\d{7,8}[A-Z]\b")),
    (PII_PASSPORT, re.compile(r"\b[A-Z]{2}\d{6,7}\b")),
    (PII_BIRTH_DATE, re.compile(r"\b\d{1,2}/\d{1,2}/(?:19|20)\d{2}\b")),
    (PII_EMAIL, re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    (PII_PHONE, re.compile(
        r"(?:\+\d[\d\s().-]{6,16}"
        r"|\b\d{2,4}(?:[\s.-]\d{2,4}){2}\b"
        r"|\b\d{9}\b)"
    )),
    (PII_INTERNAL_URL, re.compile(
        r"(?:https?://)?(?:[A-Za-z0-9-]+\.)*(?:localhost|\.local|\.internal)(?:[:/][^\s]*)?",
        re.IGNORECASE,
    )),
)

_TOKEN_FORMAT = "[[PII:{type}:{hash8}]]"


class PiiRedactionError(ValueError):
    pass


def mask_email(email: str | None) -> str | None:
    """Enmascara un email para display (no lo redacta ni lo persiste).

    Conserva los primeros 2 caracteres del local-part y el dominio, suficiente
    para distinguir la dirección sin exponer datos personales. P. ej.
    `juana@acme.com` → `ju***@acme.com`.
    """
    if not email or "@" not in email:
        return None
    local, domain = email.rsplit("@", 1)
    prefix = local[:2] if len(local) >= 2 else local
    return f"{prefix}***@{domain}"


@dataclass
class PIIReport:
    types: dict[str, int] = field(default_factory=dict)
    total: int = 0


@dataclass
class RedactedResult:
    text: str
    report: PIIReport


@dataclass
class _Span:
    start: int
    end: int
    pi_type: str
    value: str


def _luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    parity = len(digits) % 2
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _overlaps(span: _Span, spans: list[_Span]) -> bool:
    return any(
        span.start < other.end and other.start < span.end for other in spans
    )


class PiiRedactor:
    """Servicio de redacción de PII (ADR-004, spec §9.3).

    Detecta datos sensibles en texto libre y los reemplaza por tokens seguros.
    Nunca expone ni persiste el valor original; la auditoría la hace el caller
    (sin el texto) y el mapeo token→original es por request, no se guarda.
    """

    def __init__(self, salt: str | None = None) -> None:
        self.salt = salt or secrets.token_hex(16)

    def _match_spans(self, text: str) -> list[_Span]:
        """Devuelve ocurrencias no solapadas, en el orden de prioridad de _PATTERNS.

        Un span ya cubierto (p. ej. una tarjeta) bloquea re-detección por teléfono.
        """
        spans: list[_Span] = []
        for pi_type, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                span = _Span(match.start(), match.end(), pi_type, match.group(0))
                if _overlaps(span, spans):
                    continue
                spans.append(span)
        spans.sort(key=lambda s: s.start)
        return spans

    def redact(self, text: str, mode: str = "redact") -> RedactedResult:
        if mode not in ("off", "detect", "redact"):
            raise PiiRedactionError(f"Modo inválido: {mode}")

        report = PIIReport()
        if mode == "off":
            return RedactedResult(text=text, report=report)

        spans = self._match_spans(text)
        if mode == "detect":
            for span in spans:
                report.total += 1
                report.types[span.pi_type] = report.types.get(span.pi_type, 0) + 1
            return RedactedResult(text=text, report=report)

        # redact: construir el texto resultado recorriendo los spans en orden.
        pieces: list[str] = []
        cursor = 0
        for span in spans:
            pieces.append(text[cursor : span.start])
            if span.pi_type == PII_CARD and not _luhn_valid(span.value):
                pieces.append(span.value)  # tarjeta inválida → no se redacta
            else:
                pieces.append(
                    _TOKEN_FORMAT.format(type=span.pi_type, hash8=self._hash(span.value))
                )
                report.total += 1
                report.types[span.pi_type] = report.types.get(span.pi_type, 0) + 1
            cursor = span.end
        pieces.append(text[cursor:])

        return RedactedResult(text="".join(pieces), report=report)

    def _hash(self, value: str) -> str:
        digest = sha256((self.salt + value).encode("utf-8")).hexdigest()
        return digest[:8]