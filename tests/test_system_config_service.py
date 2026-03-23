from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.schemas import UpdateAppConfigRequest
from server.services import system as system_service


def test_get_app_config_returns_defaults_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(system_service, "_app_config_path", lambda: config_path)

    config = system_service.get_app_config()

    assert config.sidebarTextLineClamp == 1
    assert config.sidebarFontSizePx == 14
    assert config.tutorReasoningEffort == "medium"
    assert config.tutorWithGlobalContext is True


def test_get_app_config_falls_back_to_defaults_for_invalid_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "sidebar_text_line_clamp": 99,
                "sidebar_font_size_px": "invalid",
                "tutor_reasoning_effort": "extreme",
                "tutor_with_global_context": "maybe",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(system_service, "_app_config_path", lambda: config_path)

    config = system_service.get_app_config()

    assert config.sidebarTextLineClamp == 1
    assert config.sidebarFontSizePx == 14
    assert config.tutorReasoningEffort == "medium"
    assert config.tutorWithGlobalContext is True


def test_update_app_config_persists_snake_case_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(system_service, "_app_config_path", lambda: config_path)

    updated = system_service.update_app_config(
        sidebar_text_line_clamp=3,
        sidebar_font_size_px=18,
        tutor_reasoning_effort="xhigh",
        tutor_with_global_context=False,
    )

    assert updated.sidebarTextLineClamp == 3
    assert updated.sidebarFontSizePx == 18
    assert updated.tutorReasoningEffort == "xhigh"
    assert updated.tutorWithGlobalContext is False
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved == {
        "theme_mode": "light",
        "sidebar_text_line_clamp": 3,
        "sidebar_font_size_px": 18,
        "tutor_reasoning_effort": "xhigh",
        "tutor_with_global_context": False,
    }


def test_update_app_config_request_validates_bounds() -> None:
    with pytest.raises(ValidationError):
        UpdateAppConfigRequest(sidebarTextLineClamp=0)

    with pytest.raises(ValidationError):
        UpdateAppConfigRequest(sidebarFontSizePx=25)

    with pytest.raises(ValidationError):
        UpdateAppConfigRequest(tutorReasoningEffort="extra-high")
