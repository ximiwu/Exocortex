import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState
} from "react";

type ToastTone = "neutral" | "success" | "warning" | "danger";

interface ToastRecord {
  id: string;
  title: string;
  description: string;
  tone: ToastTone;
}

interface ToastContextValue {
  pushToast(input: Omit<ToastRecord, "id">): void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);

  function pushToast(input: Omit<ToastRecord, "id">) {
    const id = crypto.randomUUID();
    setToasts((current) => [...current, { ...input, id }]);
  }

  useEffect(() => {
    if (!toasts.length) {
      return;
    }

    const timer = window.setTimeout(() => {
      setToasts((current) => current.slice(1));
    }, 4200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [toasts]);

  return (
    <ToastContext.Provider value={{ pushToast }}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((toast) => (
          <article
            key={toast.id}
            className={`toast-card toast-card--${toast.tone}`}
          >
            <h3>{toast.title}</h3>
            <p>{toast.description}</p>
          </article>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToasts(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToasts must be used inside ToastProvider.");
  }
  return context;
}
