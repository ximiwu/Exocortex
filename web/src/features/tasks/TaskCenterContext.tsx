import {
  createContext,
  type ReactNode,
  startTransition,
  useContext,
  useEffect,
  useEffectEvent,
  useRef,
  useState
} from "react";
import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import type { TaskDetail, TaskEvent, TaskSummary } from "../../generated/contracts";
import { useToasts } from "./ToastProvider";

interface TaskCenterValue {
  loading: boolean;
  tasks: TaskDetail[];
  tasksById: Record<string, TaskDetail>;
  selectedTaskId: string | null;
  setSelectedTaskId(taskId: string | null): void;
  refreshTask(taskId: string): Promise<void>;
  trackSubmittedTask(task: TaskSummary): void;
  isTaskRunning(kind: string, assetName?: string | null): boolean;
}

const TaskCenterContext = createContext<TaskCenterValue | null>(null);
const ACTIVE_TASK_POLL_INTERVAL_MS = 2000;

export function TaskCenterProvider({
  children,
}: {
  children: ReactNode;
}) {
  const api = useExocortexApi();
  const [loading, setLoading] = useState(true);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [tasksById, setTasksById] = useState<Record<string, TaskDetail>>({});
  const tasksByIdRef = useRef<Record<string, TaskDetail>>({});
  const seenNotifications = useRef<Set<string>>(new Set());
  const { pushToast } = useToasts();

  useEffect(() => {
    tasksByIdRef.current = tasksById;
  }, [tasksById]);

  const refreshTask = useEffectEvent(async (taskId: string) => {
    try {
      const detail = await api.tasks.get(taskId);
      notifyNewTerminalEvents(
        tasksByIdRef.current[taskId],
        detail,
        seenNotifications.current,
        pushToast,
      );
      startTransition(() => {
        setTasksById((current) => ({
          ...current,
          [taskId]: mergeTaskDetail(current[taskId], detail),
        }));
      });
    } catch (error) {
      console.warn("Failed to refresh task", error);
    }
  });

  const trackSubmittedTask = useEffectEvent((task: TaskSummary) => {
    startTransition(() => {
      setTasksById((current) => ({
        ...current,
        [task.id]: mergeTaskSummary(current[task.id], task),
      }));
    });
    setSelectedTaskId((current) => current ?? task.id);
    void refreshTask(task.id);
  });

  useEffect(() => {
    let active = true;

    async function loadTasks() {
      setLoading(true);
      try {
        const summaries = await api.tasks.list();
        const details = await Promise.all(
          summaries.map(async (task) => {
            try {
              const detail = await api.tasks.get(task.id);
              markTaskNotificationsSeen(detail, seenNotifications.current);
              return mergeTaskDetail(undefined, detail);
            } catch {
              return mergeTaskSummary(undefined, task);
            }
          }),
        );
        if (!active) {
          return;
        }

        setTasksById((current) => {
          const merged = { ...current };
          for (const task of details) {
            merged[task.id] = mergeTaskDetail(current[task.id], task);
          }
          return merged;
        });
        setSelectedTaskId((current) => current ?? details[0]?.id ?? null);
      } catch (error) {
        console.warn("Failed to load tasks", error);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadTasks();

    return () => {
      active = false;
    };
  }, [api]);

  const onTaskEvent = useEffectEvent((event: TaskEvent) => {
    startTransition(() => {
      setTasksById((current) => {
        return {
          ...current,
          [event.taskId]: mergeTaskEvent(current[event.taskId], event),
        };
      });
    });

    if (!selectedTaskId) {
      setSelectedTaskId(event.taskId);
    }

    void refreshTask(event.taskId);

    if (event.eventType === "completed" || event.eventType === "failed") {
      const key = notificationKey(event);
      if (!seenNotifications.current.has(key)) {
        seenNotifications.current.add(key);
        pushToast({
          title: humanizeTaskTitle(event.kind),
          description: event.message,
          tone: event.eventType === "completed" ? "success" : "danger"
        });
      }
    }
  });

  useEffect(() => {
    return api.tasks.subscribe((event) => {
      onTaskEvent(event);
    });
  }, [api, onTaskEvent]);

  const tasks = Object.values(tasksById).sort((left, right) =>
    right.updatedAt.localeCompare(left.updatedAt)
  );

  useEffect(() => {
    const activeTaskIds = tasks
      .filter((task) => task.status === "queued" || task.status === "running")
      .map((task) => task.id);

    if (!activeTaskIds.length) {
      return undefined;
    }

    let cancelled = false;
    let timer: number | null = null;

    const poll = async () => {
      await Promise.all(activeTaskIds.map((taskId) => refreshTask(taskId)));
      if (cancelled) {
        return;
      }
      timer = window.setTimeout(() => {
        void poll();
      }, ACTIVE_TASK_POLL_INTERVAL_MS);
    };

    timer = window.setTimeout(() => {
      void poll();
    }, ACTIVE_TASK_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [refreshTask, tasks]);

  function isTaskRunning(kind: string, assetName?: string | null): boolean {
    return tasks.some((task) => {
      if (task.kind !== kind) {
        return false;
      }
      if (assetName && task.assetName && task.assetName !== assetName) {
        return false;
      }
      return task.status === "queued" || task.status === "running";
    });
  }

  return (
    <TaskCenterContext.Provider
      value={{
        loading,
        tasks,
        tasksById,
        selectedTaskId,
        setSelectedTaskId,
        refreshTask,
        trackSubmittedTask,
        isTaskRunning
      }}
    >
      {children}
    </TaskCenterContext.Provider>
  );
}

export function useTaskCenter(): TaskCenterValue {
  const context = useContext(TaskCenterContext);
  if (!context) {
    throw new Error("useTaskCenter must be used inside TaskCenterProvider.");
  }
  return context;
}

function dedupeEvents(events: TaskEvent[]): TaskEvent[] {
  const seen = new Set<string>();
  const deduped = events.filter((event) => {
    const key = `${event.taskId}:${event.eventType}:${event.timestamp}:${event.message}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
  return deduped.sort((left, right) => left.timestamp.localeCompare(right.timestamp));
}

function humanizeTaskTitle(kind: string): string {
  return kind
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function mergeTaskSummary(existing: TaskDetail | undefined, task: TaskSummary): TaskDetail {
  return {
    id: task.id,
    kind: existing?.kind ?? task.kind,
    status: task.status,
    title: task.title,
    assetName: task.assetName,
    createdAt: existing?.createdAt ?? task.createdAt,
    updatedAt: maxTimestamp(task.updatedAt, existing?.updatedAt),
    events: existing?.events ?? [],
    latestEvent: existing?.latestEvent ?? null,
    result: existing?.result ?? null,
  };
}

function mergeTaskDetail(existing: TaskDetail | undefined, detail: TaskDetail): TaskDetail {
  const events = dedupeEvents([...(existing?.events ?? []), ...detail.events]);
  const latestEvent = events.at(-1) ?? detail.latestEvent ?? existing?.latestEvent ?? null;
  return {
    ...detail,
    title: detail.title || existing?.title || humanizeTaskTitle(detail.kind),
    assetName: detail.assetName ?? existing?.assetName ?? null,
    createdAt: existing?.createdAt ?? detail.createdAt,
    updatedAt: maxTimestamp(detail.updatedAt, existing?.updatedAt, latestEvent?.timestamp),
    status: latestEvent?.status ?? detail.status,
    events,
    latestEvent,
    result: detail.result ?? existing?.result ?? null,
  };
}

function mergeTaskEvent(existing: TaskDetail | undefined, event: TaskEvent): TaskDetail {
  const events = dedupeEvents([...(existing?.events ?? []), event]);
  const latestEvent = events.at(-1) ?? event;
  return {
    id: event.taskId,
    kind: existing?.kind ?? event.kind,
    status: latestEvent.status,
    title: existing?.title ?? humanizeTaskTitle(event.kind),
    assetName: existing?.assetName ?? event.assetName ?? null,
    createdAt: existing?.createdAt ?? event.timestamp,
    updatedAt: maxTimestamp(existing?.updatedAt, latestEvent.timestamp),
    events,
    latestEvent,
    result: existing?.result ?? null,
  };
}

function maxTimestamp(...values: Array<string | null | undefined>): string {
  return values.filter((value): value is string => Boolean(value)).sort().at(-1) ?? new Date(0).toISOString();
}

function notificationKey(event: TaskEvent): string {
  return `${event.taskId}:${event.eventType}:${event.timestamp}`;
}

function isTerminalTaskEvent(event: TaskEvent): boolean {
  return event.eventType === "completed" || event.eventType === "failed";
}

function markTaskNotificationsSeen(task: TaskDetail, seenNotifications: Set<string>): void {
  for (const event of task.events) {
    if (!isTerminalTaskEvent(event)) {
      continue;
    }
    seenNotifications.add(notificationKey(event));
  }
}

function notifyNewTerminalEvents(
  previous: TaskDetail | undefined,
  next: TaskDetail,
  seenNotifications: Set<string>,
  pushToast: ReturnType<typeof useToasts>["pushToast"],
): void {
  const previousKeys = new Set(
    (previous?.events ?? []).map((event) => notificationKey(event)),
  );
  for (const event of next.events) {
    if (!isTerminalTaskEvent(event)) {
      continue;
    }
    const key = notificationKey(event);
    if (previousKeys.has(key) || seenNotifications.has(key)) {
      continue;
    }
    seenNotifications.add(key);
    pushToast({
      title: humanizeTaskTitle(event.kind),
      description: event.message,
      tone: event.eventType === "completed" ? "success" : "danger",
    });
  }
}
