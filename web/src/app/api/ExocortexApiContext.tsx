import { createContext, type PropsWithChildren, useContext } from "react";

import type { ExocortexApi } from "./exocortexApi";

const ExocortexApiContext = createContext<ExocortexApi | null>(null);

export function ExocortexApiProvider({
  api,
  children,
}: PropsWithChildren<{ api: ExocortexApi }>) {
  return <ExocortexApiContext.Provider value={api}>{children}</ExocortexApiContext.Provider>;
}

export function useExocortexApi(): ExocortexApi {
  const api = useContext(ExocortexApiContext);
  if (!api) {
    throw new Error("useExocortexApi must be used inside ExocortexApiProvider.");
  }
  return api;
}
