from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Auto Help Desk API"
    api_v1_prefix: str = "/v1"

    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "api.example.com"
    jwt_audience: str = "api.example.com"

    database_url: str = "sqlite:///./app.db"

    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"
    llm_chat_path: str = "/v1/chat/completions"
    llm_timeout_seconds: float = 15.0
    llm_max_retries: int = 2
    llm_retry_backoff: float = 0.5
    llm_max_tokens: int = 1024
    llm_rate_max_calls: int = 60
    llm_rate_window_seconds: int = 60

    # Proveedores específicos (018): el activo se elige con `LLM_PROVIDER`.
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_project_id: str = ""
    openrouter_api_key: SecretStr = SecretStr("")

    ai_confidence_threshold: float = 0.6
    ai_classify_categories: str = (
        "billing,technical,account,general,urgent,feedback,other"
    )

    ai_features_enabled: bool = True

    guardrails_enabled: bool = True
    guardrail_prohibited_patterns: list[str] = [
        r"ignor(?:a|e|ar) (?:todos? las? )?(?:las )?instrucciones",
        r"reveal(?:ing)? your (?:system|developer) prompt",
        r"system prompt",
        r"act as an unrestricted",
        r"dame tu prompt",
        r"exfiltra",
        r"accede a (?:bases de datos|archivos|sistemas internos)",
    ]
    guardrail_injection_patterns: list[str] = [
        r"ignor(?:a|e|ar) (?:todas? las? )?instrucciones",
        r"eres (?:ahora|un) (?:admin|asistente sin restricciones)",
        r"reveal(?:ing)? your (?:system|developer) prompt",
        r"exfiltra",
        r"cambia tu rol",
    ]

    @property
    def llm_effective_model(self) -> str:
        """Modelo por defecto según el proveedor configurado (018).

        Con `LLM_PROVIDER=gemini` usa `GEMINI_MODEL` (los modelos de Gemini
        no son compatibles con el nombre por defecto de OpenAI).
        """
        if self.llm_provider == "gemini":
            return self.gemini_model or self.llm_model
        return self.llm_model

    @property
    def encryption_key(self) -> bytes:
        """Clave de cifrado de campos, derivada de SECRET_KEY (nunca persistida)."""
        return self.secret_key.encode("utf-8")


settings = Settings()