from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ClassificationOut(BaseModel):
    category: str
    suggested_priority: str
    confidence: float
    warnings: list[str] = []
    suggestion_id: int
    trace_id: str | None = None


class SummaryOut(BaseModel):
    summary: str
    missing_information: str | None
    confidence: float
    warnings: list[str] = []
    suggestion_id: int
    trace_id: str | None = None


class SuggestedReplyOut(BaseModel):
    suggested_reply: str
    confidence: float
    sources: list[str] = []
    policy_flags: list[str] = []
    warnings: list[str] = []
    suggestion_id: int
    trace_id: str | None = None


class SuggestedReplyRequest(BaseModel):
    tone: str | None = None
    language: str | None = None


class FeedbackIn(BaseModel):
    suggestion_id: int
    action: Literal["accepted", "edited", "rejected", "flagged"]
    reason: str | None = None
    edited_content_hash: str | None = None
    edited_output: dict | None = None


class FeedbackOut(BaseModel):
    suggestion_id: int
    action: str
    reason: str | None
    edited_content_hash: str | None
    created_at: datetime


class SuggestionOut(BaseModel):
    id: int
    type: str
    state: str
    confidence: float | None
    model: str | None
    prompt_version: str | None
    output: dict
    created_at: datetime

    model_config = {"from_attributes": True}