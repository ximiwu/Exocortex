from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TutorReasoningEffort = Literal["low", "medium", "high", "xhigh"]


class AppConfigModel(BaseModel):
    themeMode: Literal["light", "dark"] = "light"
    sidebarTextLineClamp: int = Field(default=1, ge=1, le=6)
    sidebarFontSizePx: int = Field(default=14, ge=10, le=24)
    tutorReasoningEffort: TutorReasoningEffort = "medium"
    tutorWithGlobalContext: bool = True


class UpdateAppConfigRequest(BaseModel):
    themeMode: Literal["light", "dark"] | None = None
    sidebarTextLineClamp: int | None = Field(default=None, ge=1, le=6)
    sidebarFontSizePx: int | None = Field(default=None, ge=10, le=24)
    tutorReasoningEffort: TutorReasoningEffort | None = None
    tutorWithGlobalContext: bool | None = None


__all__ = ["AppConfigModel", "TutorReasoningEffort", "UpdateAppConfigRequest"]
