import { useState } from "react";
import { useTaskCenter } from "./TaskCenterContext";

interface TaskCenterProps {
  visible: boolean;
  onClose(): void;
  variant?: "floating" | "embedded";
}

export function TaskCenter({
  visible,
  onClose,
  variant = "floating"
}: TaskCenterProps) {
  const {
    loading,
    tasks,
    tasksById,
    selectedTaskId,
    setSelectedTaskId
  } = useTaskCenter();
  const [copiedArtifact, setCopiedArtifact] = useState<string | null>(null);

  if (!visible) {
    return null;
  }

  const queued = tasks.filter((task) => task.status === "queued");
  const running = tasks.filter((task) => task.status === "running");
  const completed = tasks.filter((task) => task.status === "completed");
  const failed = tasks.filter((task) => task.status === "failed");
  const selectedTask =
    (selectedTaskId ? tasksById[selectedTaskId] : null) ?? tasks[0] ?? null;
  const artifactPath = selectedTask ? latestArtifactPath(selectedTask.events) : null;
  const progress = selectedTask ? latestProgress(selectedTask.events) : null;

  async function copyArtifactPath() {
    if (!artifactPath) {
      return;
    }

    await navigator.clipboard.writeText(artifactPath);
    setCopiedArtifact(artifactPath);
    window.setTimeout(() => {
      setCopiedArtifact((current) => (current === artifactPath ? null : current));
    }, 1800);
  }

  return (
    <aside
      className={`task-center-shell ${variant === "embedded" ? "task-center-shell--embedded" : ""}`}
    >
      <header className="task-center-header">
        <div>
          <p className="section-kicker">Task Center</p>
          <h2>Live workflow activity</h2>
        </div>
        <button className="ghost-button" type="button" onClick={onClose}>
          close
        </button>
      </header>

      <div className="task-center-grid">
        <section className="task-sections">
          {loading ? <p className="empty-copy">Loading tasks…</p> : null}
          {!loading && !tasks.length ? (
            <p className="empty-copy">No tasks yet. Start a workflow to populate the panel.</p>
          ) : null}
          <TaskSection
            title="queued"
            tasks={queued}
            selectedTaskId={selectedTaskId}
            onSelect={setSelectedTaskId}
          />
          <TaskSection
            title="running"
            tasks={running}
            selectedTaskId={selectedTaskId}
            onSelect={setSelectedTaskId}
          />
          <TaskSection
            title="completed"
            tasks={completed}
            selectedTaskId={selectedTaskId}
            onSelect={setSelectedTaskId}
          />
          <TaskSection
            title="failed"
            tasks={failed}
            selectedTaskId={selectedTaskId}
            onSelect={setSelectedTaskId}
          />
        </section>

        <section className="task-detail-panel">
          {!selectedTask ? (
            <p className="empty-copy">Select a task to inspect the live log feed.</p>
          ) : (
            <>
              <header className="task-detail-header">
                <div>
                  <p className="section-kicker">{selectedTask.kind.replaceAll("_", " ")}</p>
                  <h3>{selectedTask.title}</h3>
                </div>
                <span className={`status-pill status-pill--${selectedTask.status}`}>
                  {selectedTask.status}
                </span>
              </header>

              <dl className="task-detail-meta">
                <div>
                  <dt>asset</dt>
                  <dd>{selectedTask.assetName ?? "session-wide"}</dd>
                </div>
                <div>
                  <dt>updated</dt>
                  <dd>{formatTime(selectedTask.updatedAt)}</dd>
                </div>
                <div>
                  <dt>progress</dt>
                  <dd>{progress === null ? "n/a" : `${Math.round(progress * 100)}%`}</dd>
                </div>
              </dl>

              <div className="artifact-row">
                <span>artifact</span>
                {artifactPath ? (
                  <button className="ghost-button" type="button" onClick={copyArtifactPath}>
                    {copiedArtifact === artifactPath ? "copied" : "copy path"}
                  </button>
                ) : (
                  <span className="muted-copy">none yet</span>
                )}
              </div>
              {artifactPath ? <p className="artifact-path">{artifactPath}</p> : null}

              <div className="task-log-feed">
                {selectedTask.events.map((event) => (
                  <article key={`${event.timestamp}-${event.eventType}-${event.message}`} className="task-log-entry">
                    <div className="task-log-meta">
                      <span className={`event-pill event-pill--${event.eventType}`}>
                        {event.eventType}
                      </span>
                      <time>{formatTime(event.timestamp)}</time>
                    </div>
                    <p>{event.message}</p>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </aside>
  );
}

function TaskSection({
  title,
  tasks,
  selectedTaskId,
  onSelect
}: {
  title: string;
  tasks: Array<{
    id: string;
    title: string;
    status: string;
    updatedAt: string;
  }>;
  selectedTaskId: string | null;
  onSelect(taskId: string): void;
}) {
  return (
    <section className="task-section-card">
      <header>
        <h3>{title}</h3>
        <span>{tasks.length}</span>
      </header>
      {!tasks.length ? (
        <p className="muted-copy">No tasks in this section.</p>
      ) : (
        <div className="task-list">
          {tasks.map((task) => (
            <button
              key={task.id}
              type="button"
              className={`task-list-item ${selectedTaskId === task.id ? "task-list-item--active" : ""}`}
              onClick={() => onSelect(task.id)}
            >
              <strong>{task.title}</strong>
              <span>{formatTime(task.updatedAt)}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function latestArtifactPath(events: Array<{ artifactPath: string | null }>): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.artifactPath) {
      return events[index].artifactPath;
    }
  }
  return null;
}

function latestProgress(events: Array<{ progress: number | null }>): number | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (typeof events[index]?.progress === "number") {
      return events[index].progress;
    }
  }
  return null;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}
