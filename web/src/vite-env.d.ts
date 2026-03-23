/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_EXOCORTEX_API_BASE?: string;
  readonly VITE_EXOCORTEX_API_MODE?: "auto" | "live" | "mock";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.worker.js?url";
declare module "*.worker.min.js?url";
declare module "*.worker.mjs?url";
declare module "*.worker.min.mjs?url";
