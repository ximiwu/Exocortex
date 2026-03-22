from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class TaskArtifact:
    path: str | Path
    message: str
    payload: JsonObject | None = None

    def to_wire(self) -> JsonObject:
        return {
            "path": str(self.path),
            "message": self.message,
            "payload": self.payload,
        }


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class TaskFailure:
    code: str
    exception_type: str
    details: JsonValue = None
    status_code: int | None = None

    def to_payload(self) -> JsonObject:
        payload: JsonObject = {
            "code": self.code,
            "details": self.details,
            "exceptionType": self.exception_type,
        }
        if self.status_code is not None:
            payload["statusCode"] = self.status_code
        return payload


@dataclass(frozen=True, slots=True)
class TaskResult:
    message: str
    artifact_path: str | Path | None = None
    payload: JsonObject | None = None

    def to_wire(self) -> JsonObject:
        return {
            "message": self.message,
            "artifactPath": str(self.artifact_path) if self.artifact_path is not None else None,
            "payload": self.payload,
        }


__all__ = [
    "JsonObject",
    "JsonScalar",
    "JsonValue",
    "TaskArtifact",
    "TaskFailure",
    "TaskResult",
]
