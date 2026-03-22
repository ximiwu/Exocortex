import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ExocortexApiProvider } from "./api/ExocortexApiContext";
import { createExocortexApi } from "./api/exocortexApi";
import { AppProviders } from "./providers/AppProviders";
import { WorkflowBridge } from "../features/workflows/WorkflowBridge";
import { TaskCenterProvider } from "../features/tasks/TaskCenterContext";
import { ToastProvider } from "../features/tasks/ToastProvider";
import "../index.css";
import "./app.css";

const rootNode = document.getElementById("root");
if (!rootNode) {
  throw new Error("Missing #root element");
}

function Root() {
  const [api] = useState(() => createExocortexApi());

  return (
    <ExocortexApiProvider api={api}>
      <AppProviders>
        <ToastProvider>
          <TaskCenterProvider>
            <App />
            <WorkflowBridge />
          </TaskCenterProvider>
        </ToastProvider>
      </AppProviders>
    </ExocortexApiProvider>
  );
}

createRoot(rootNode).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
