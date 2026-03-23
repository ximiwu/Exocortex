import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useExocortexApi } from "../../../app/api/ExocortexApiContext";
import { useSystemConfigQuery } from "../../../app/api/queries";
import { queryKeys } from "../../../app/api/exocortexApi";
import type { AppSystemConfig, AppSystemConfigUpdate, TutorReasoningEffort } from "../../../app/api/types";

interface WorkflowTutorDockProps {
  visible: boolean;
  questionText: string;
  effectiveTutorIdx: number | null;
  canSubmit: boolean;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
}

interface TutorAskSettingsState {
  tutorReasoningEffort: TutorReasoningEffort;
  tutorWithGlobalContext: boolean;
}

const DEFAULT_TUTOR_SETTINGS: TutorAskSettingsState = {
  tutorReasoningEffort: "medium",
  tutorWithGlobalContext: true,
};

const EFFORT_OPTIONS: TutorReasoningEffort[] = ["xhigh", "high", "medium", "low"];

function tutorSettingsFromConfig(config: AppSystemConfig | undefined): TutorAskSettingsState {
  return {
    tutorReasoningEffort: config?.tutorReasoningEffort ?? DEFAULT_TUTOR_SETTINGS.tutorReasoningEffort,
    tutorWithGlobalContext: config?.tutorWithGlobalContext ?? DEFAULT_TUTOR_SETTINGS.tutorWithGlobalContext,
  };
}

function reasoningEffortLabel(value: TutorReasoningEffort): string {
  switch (value) {
    case "xhigh":
      return "extra high";
    case "high":
      return "high";
    case "medium":
      return "medium";
    case "low":
      return "low";
  }
}

export function WorkflowTutorDock({
  visible,
  questionText,
  effectiveTutorIdx,
  canSubmit,
  onQuestionChange,
  onSubmit,
}: WorkflowTutorDockProps) {
  const api = useExocortexApi();
  const queryClient = useQueryClient();
  const { data: systemConfig } = useSystemConfigQuery();
  const [settings, setSettings] = useState<TutorAskSettingsState>(DEFAULT_TUTOR_SETTINGS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSettings(tutorSettingsFromConfig(systemConfig));
  }, [systemConfig]);

  useEffect(() => {
    if (!settingsOpen) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (
        (triggerRef.current && target && triggerRef.current.contains(target)) ||
        (popoverRef.current && target && popoverRef.current.contains(target))
      ) {
        return;
      }
      setSettingsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSettingsOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [settingsOpen]);

  async function persistSettings(update: AppSystemConfigUpdate) {
    const previous = settings;
    const next: TutorAskSettingsState = {
      tutorReasoningEffort: update.tutorReasoningEffort ?? previous.tutorReasoningEffort,
      tutorWithGlobalContext: update.tutorWithGlobalContext ?? previous.tutorWithGlobalContext,
    };
    setSettings(next);
    try {
      const persisted = await api.system.updateConfig(update);
      queryClient.setQueryData(queryKeys.systemConfig, persisted);
      setSettings(tutorSettingsFromConfig(persisted));
    } catch (error) {
      console.warn("Failed to save tutor ask settings", error);
      setSettings(previous);
    }
  }

  if (!visible) {
    return null;
  }

  const currentEffortLabel = reasoningEffortLabel(settings.tutorReasoningEffort);
  const handleQuestionKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    if (canSubmit) {
      onSubmit();
    }
  };

  return (
    <div className="workflow-taskMount workflow-taskMount--compact">
      <div className="workflow-tutorCompact">
        <textarea
          aria-label={`Question for tutor ${effectiveTutorIdx ?? ""}`}
          className="workflow-bar__question"
          rows={2}
          value={questionText}
          onChange={(event) => onQuestionChange(event.currentTarget.value)}
          onKeyDown={handleQuestionKeyDown}
          placeholder="Ask a follow-up question"
        />
        <div className="workflow-tutorCompact__actions">
          <div className="workflow-tutorCompact__settingsWrap">
            <button
              ref={triggerRef}
              aria-expanded={settingsOpen}
              aria-haspopup="dialog"
              aria-label="Tutor ask settings"
              className="workflow-tutorCompact__settingsButton"
              type="button"
              onClick={() => setSettingsOpen((open) => !open)}
            >
              <span>{currentEffortLabel}</span>
              <svg
                className={`workflow-tutorCompact__settingsChevron${settingsOpen ? " is-open" : ""}`}
                viewBox="0 0 16 16"
                aria-hidden="true"
              >
                <path
                  d="M3.2 10.2a.75.75 0 0 1 0-1.06l4.27-4.27a.75.75 0 0 1 1.06 0l4.27 4.27a.75.75 0 1 1-1.06 1.06L8 6.47l-3.74 3.75a.75.75 0 0 1-1.06 0Z"
                  fill="currentColor"
                />
              </svg>
            </button>
            {settingsOpen ? (
              <div
                ref={popoverRef}
                className="workflow-tutorCompact__settingsPopover"
                role="dialog"
                aria-label="Tutor ask settings panel"
              >
                <div className="workflow-tutorCompact__settingsOptions">
                  {EFFORT_OPTIONS.map((option) => {
                    const label = reasoningEffortLabel(option);
                    return (
                      <button
                        key={option}
                        className={`workflow-tutorCompact__settingsOption${settings.tutorReasoningEffort === option ? " is-active" : ""}`}
                        type="button"
                        onClick={() => {
                          void persistSettings({ tutorReasoningEffort: option });
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
                <div className="workflow-tutorCompact__settingsDivider" />
                <label className="workflow-tutorCompact__settingsCheckbox">
                  <span>with global context</span>
                  <input
                    checked={settings.tutorWithGlobalContext}
                    type="checkbox"
                    onChange={(event) => {
                      void persistSettings({ tutorWithGlobalContext: event.currentTarget.checked });
                    }}
                  />
                </label>
              </div>
            ) : null}
          </div>
          <button
            aria-label="Ask Tutor"
            className="primary-button workflow-tutorCompact__submit"
            title="Ask Tutor"
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M2 3.5 14 8 2 12.5l2.6-4.5L2 3.5Z"
                fill="currentColor"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
