from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from .common import RectModel


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list[Any] | dict[str, Any]


class TaskFailurePayloadModel(BaseModel):
    code: str
    details: JsonValue = None
    exceptionType: str
    statusCode: int | None = None


class TaskArtifactModel(BaseModel):
    path: str
    message: str
    payload: dict[str, JsonValue] | None = None


class TaskResultModel(BaseModel):
    message: str
    artifactPath: str | None = None
    payload: TaskFailurePayloadModel | dict[str, JsonValue] | None = None


class TaskEventModel(BaseModel):
    taskId: str
    kind: str
    status: str
    eventType: str
    message: str
    progress: float | None = None
    artifactPath: str | None = None
    payload: TaskFailurePayloadModel | dict[str, JsonValue] | None = None
    timestamp: str


class TaskSummaryModel(BaseModel):
    id: str
    kind: str
    status: str
    title: str
    assetName: str | None = None
    createdAt: str
    updatedAt: str


class TaskDetailModel(TaskSummaryModel):
    events: list[TaskEventModel] = Field(default_factory=list)
    latestEvent: TaskEventModel | None = None
    result: TaskResultModel | None = None


class GroupWorkflowRequest(BaseModel):
    assetName: str
    groupIdx: int


class TutorWorkflowRequest(BaseModel):
    assetName: str
    groupIdx: int
    tutorIdx: int


class AskTutorWorkflowRequest(TutorWorkflowRequest):
    question: str


class ReTutorWorkflowRequest(TutorWorkflowRequest):
    question: str


class FixLatexWorkflowRequest(BaseModel):
    assetName: str | None = None
    markdownPath: str


class CompressTaskRequest(BaseModel):
    assetName: str
    fractionRect: RectModel
    ratio: int
    compressScale: float = 1.0
    drawBadge: bool = True
    badgePosition: str = "top_left"


__all__ = [
    "AskTutorWorkflowRequest",
    "FixLatexWorkflowRequest",
    "GroupWorkflowRequest",
    "CompressTaskRequest",
    "ReTutorWorkflowRequest",
    "TaskArtifactModel",
    "TaskDetailModel",
    "TaskEventModel",
    "TaskFailurePayloadModel",
    "TaskResultModel",
    "TaskSummaryModel",
    "TutorWorkflowRequest",
]
