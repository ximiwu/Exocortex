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
import type { TaskDetail, TaskEvent } from "../../generated/contracts";
import { useToasts } from "./ToastProvider";

interface TaskCenterValue {
  loading: boolean;
  tasks: TaskDetail[];
  tasksById: Record<string, TaskDetail>;
  selectedTaskId: string | null;
  setSelectedTaskId(taskId: string | null): void;
  refreshTask(taskId: string): Promise<void>;
  isTaskRunning(kind: string, assetName?: string | null): boolean;
}

const TaskCenterContext = createContext<TaskCenterValue | null>(null);

export function TaskCenterProvider({
  children,
}: {
  children: ReactNode;
}) {
  const api = useExocortexApi();
  const [loading, setLoading] = useState(true);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [tasksById, setTasksById] = useState<Record<string, TaskDetail>>({});
  const seenNotifications = useRef<Set<string>>(new Set());
  const { pushToast } = useToasts();

  const refreshTask = useEffectEvent(async (taskId: string) => {
    try {
      const detail = await api.tasks.get(taskId);
      startTransition(() => {
        setTasksById((current) => ({
          ...current,
          [taskId]: detail
        }));
      });
    } catch (error) {
      console.warn("Failed to refresh task", error);
    }
  });

  useEffect(() => {
    let active = true;

    async function loadTasks() {
      setLoading(true);
      try {
        const summaries = await api.tasks.list();
        const details = await Promise.all(
          summaries.map((task) => api.tasks.get(task.id).catch(() => null))
        );
        if (!active) {
          return;
        }

        const nextEntries = details
          .filter((task): task is TaskDetail => task !== null)
          .reduce<Record<string, TaskDetail>>((accumulator, task) => {
            accumulator[task.id] = task;
            return accumulator;
          }, {});
        setTasksById(nextEntries);
        setSelectedTaskId((current) => current ?? details[0]?.id ?? null);
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
        const existing = current[event.taskId];
        const nextEvents = existing
          ? dedupeEvents([...existing.events, event])
          : [event];
        const nextTask: TaskDetail = {
          id: event.taskId,
          kind: existing?.kind ?? event.kind,
          status: event.status,
          title: existing?.title ?? humanizeTaskTitle(event.kind),
          assetName: existing?.assetName ?? null,
          createdAt: existing?.createdAt ?? event.timestamp,
          updatedAt: event.timestamp,
          events: nextEvents
        };
        return {
          ...current,
          [event.taskId]: nextTask
        };
      });
    });

    if (!selectedTaskId) {
      setSelectedTaskId(event.taskId);
    }

    void refreshTask(event.taskId);

    if (event.eventType === "completed" || event.eventType === "failed") {
      const notificationKey = `${event.taskId}:${event.eventType}:${event.timestamp}`;
      if (!seenNotifications.current.has(notificationKey)) {
        seenNotifications.current.add(notificationKey);
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
  return events.filter((event) => {
    const key = `${event.taskId}:${event.eventType}:${event.timestamp}:${event.message}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function humanizeTaskTitle(kind: string): string {
  return kind
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
