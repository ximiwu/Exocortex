/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_EXOCORTEX_API_BASE?: string;
  readonly VITE_EXOCORTEX_API_MODE?: "auto" | "live" | "mock";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
