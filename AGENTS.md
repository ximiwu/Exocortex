# Exocortex Maintainer Guide

This file documents the current architecture contract of the repository. Keep it aligned with the codebase. When behavior changes, update this file in the same change instead of letting it drift behind the implementation.

## Working Baseline

- Activate the shared Conda environment before running Python commands: `conda activate web_env`.
- `environment.yml` is the only environment definition for local development and CI. Do not introduce parallel Python environment files unless there is a strong reason.
- The Node baseline is defined by `.nvmrc`, `web/package.json#engines`, and `web/package.json#packageManager`.
- Frontend installs use `npm ci`, not `npm install`.
- Treat `web/dist`, `dist`, `Output_Installers`, `web/node_modules`, and `web/test-results` as build artifacts, not source-of-truth inputs.

## Repository Map

- `server/`: FastAPI app, routers, services, domain adapters, schemas, and task infrastructure.
- `exocortex_core/`: shared filesystem, markdown, settings, workflow event, and packaging helpers.
- `server/legacy/`: the only allowed compatibility bridge to the old root-level monolith modules.
- `web/src/app/`: frontend composition root, providers, app-level API, hooks, store, and shell.
- `web/src/features/`: feature modules for markdown, PDF, sidebar, workflows, tasks, and shared UI.
- `web/src/generated/`: generated OpenAPI output and the typed wire-contract facade.
- Root-level `assets_manager.py` and `agent_manager.py`: legacy implementation details. New code should not depend on them directly.

## Contract Sources

- Preserve the current HTTP endpoint shapes, payload field names, and asset disk layout unless the change is intentional and coordinated across backend and frontend.
- Browser-based `new asset` imports require a PDF source file, a markdown file, and a JSON content list file; the JSON must be stored at `content_list.json` in the asset directory.
- Browser-based `new asset` imports write `content_list.json` and `content_list_unified.json` immediately after `raw.pdf` is saved. In `content_list.json`, each `bbox` is `[x0, y0, x1, y1]` in a top-left-origin page coordinate space scaled to integer `0..1000` on each axis, not raw PDF points or image pixels. `content_list_unified.json` keeps only entries that are eligible to be rendered into merge Markdown (`text`, `title`, `list`, `image`, `table`, `code`, `algorithm`, `equation`, `interline_equation`, plus entries whose `sub_type` is `code` or `algorithm`), preserves each retained item as-is, converts `page_idx` to 1-based indexing, removes `bbox`, and writes normalized `x`, `y`, `width`, and `height` as `x0/1000`, `y0/1000`, `(x1-x0)/1000`, and `(y1-y0)/1000`.
- Opening an existing asset should auto-generate `content_list_unified.json` from sibling `content_list.json` when the unified file is missing, using the same backend conversion path as `new asset`.
- `POST /api/assets/{asset_name:path}/groups/markdown-preview` generates manual-merge prefill Markdown from the current selected blocks by filtering fully contained entries from `content_list_unified.json` in original file order and rendering them as Markdown fragments.
- `POST /api/assets/{asset_name:path}/groups/merge` writes the submitted Markdown to `group_data/{group_idx}/content.md` and auto-updates `group.alias` from the submitted Markdown first line by removing only a leading run of `#` or `＃` characters and the whitespace immediately after that run; once a non-whitespace character is reached, later spaces are preserved as-is.
- Group-level flashcard generation is triggered by `POST /api/tasks/flashcard` with `{ assetName, groupIdx }`, reads `group_data/{group_idx}/content.md` as `input/content.md`, concatenates only `group_data/{group_idx}/tutor_data/*/ask_history/*.md` into `references/QA.md` using numeric directory/file ordering with name-order fallback, copies any existing `group_data/{group_idx}/flashcard/md/` files into `references/flashcards/`, and appends every file produced under the agent `output/` directory into `group_data/{group_idx}/flashcard/md/` without overwriting existing files. After markdown generation it rebuilds `group_data/{group_idx}/flashcard/html/` and `group_data/{group_idx}/flashcard/apkg/`, renders each `flashcard/md/**/*.md` into `<stem>.front.html` and `<stem>.back.html`, and writes a single `group_data/{group_idx}/flashcard/apkg/deck.apkg` whose deck name is `{asset_name}::{group_alias}` with `Group {group_idx}` fallback.
- `POST /api/assets/{asset_name:path}/reveal` accepts both asset-relative files and directories. Revealing `group_data/{group_idx}/flashcard/apkg` is a no-op when that directory does not exist.
- Asset-level disabled content list entries are stored in each asset `config.json` under `disabled_content_item_indexes`, exposed on asset state as `disabledContentItemIndexes`, updated through `PUT /api/assets/{asset_name:path}/content-list/disabled-items`, and excluded from manual-merge markdown preview.
- PDF page text box wire contracts include stable per-asset `itemIndex` values derived from `content_list_unified.json` source order.
- System-wide UI and tutor ask preferences are stored in `Documents/ximiwu_app/Exocortex/config.json` and exposed through `GET /api/system/config` and `PUT /api/system/config`.
- PDF block wire contracts use normalized page fractions (`fractionRect`) in the `page_fraction_v1` coordinate space. Legacy block files without `coordinate_space` are treated as `reference_dpi_130` and auto-migrated.
- Backend wire schemas live in `server/schemas/`. Do not create route-local ad hoc response models when a shared schema belongs there.
- Frontend wire types come from `web/src/generated/openapi.ts` and `web/src/generated/contracts.ts`.
- Regenerate frontend contracts with `cd web && npm run generate:contracts` after backend schema changes.
- Do not hand-edit files under `web/src/generated/`.
- Frontend app code should prefer `web/src/app/types.ts` and `web/src/app/api/types.ts` over duplicating raw OpenAPI shapes in feature code.
- Backend task and workflow boundaries use typed models in `server/tasking/contracts.py` and `server/domain/workflows/contracts.py`.
- Preserve the structured error envelope from `server/errors.py`: `error.code`, `error.message`, and `error.details` must remain stable.

## Backend Architecture Rules

- `server/app.py` is the FastAPI composition root. Register routers there and keep `TaskManager` lifecycle ownership there.
- `server/config.py` owns runtime HTTP constants such as host, API prefix, websocket path, and frontend dist paths.
- `exocortex_core/settings.py` owns repo-root, prompts, asset root, workspace root, prompt paths, and model identifiers. Do not scatter those values across services.
- Layer boundaries are strict:
  - `server/api/*`: request parsing, dependency injection, response shaping, and status codes.
  - `server/services/*`: application logic, path validation, orchestration, and service-level normalization.
  - `server/domain/*`: repository and workflow orchestration boundaries.
  - `server/tasking/*`: task execution infrastructure and typed task payload/result models.
  - `server/legacy/*`: only compatibility wrappers around the root-level monolith.
- Do not import `assets_manager.py` or `agent_manager.py` directly from `server/api`, `server/services`, `server/domain`, or new modules. If old behavior must be reused, go through `server/legacy/*` and keep the bridge contained there.
- Reuse shared upload and task helper modules instead of duplicating staging and cleanup logic:
  - `server/api/uploads.py`
  - `server/api/task_helpers.py`
  - `server/services/assets.py`
- The canonical raw PDF endpoint is `GET /api/assets/{asset_name:path}/pdf/file`; keep it stable for frontend PDF rendering.
- Reuse asset path normalization and root-boundary checks from `server/services/assets.py`. Never trust raw asset-relative paths from request data.
- Use typed workflow commands such as `AssetInitCommand`, `GroupDiveCommand`, `TutorQuestionCommand`, `BugFinderCommand`, `FixLatexCommand`, and `CompressCommand` instead of loose dictionaries.
- Use typed task outputs such as `TaskArtifact`, `TaskFailure`, and `TaskResult` instead of new `dict[str, Any]` contracts.
- New failure paths should either raise `ApiError` or return task failures with stable codes and structured details. Do not collapse errors into opaque strings.

## Frontend Architecture Rules

- `web/src/app/main.tsx` is the only frontend bootstrap entry. Do not add parallel React roots or alternate boot files.
- `web/src/app/App.tsx` should stay thin: compose top-level queries, synchronization hooks, and the shell.
- `web/src/app/shell/WorkbenchShell.tsx` is the shell composition point for the sidebar, markdown workspace, PDF pane, workflow controller, modal host, and tutor dock.
- Keep TypeScript config layered as it is now:
  - `web/tsconfig.json` is only a project-reference wrapper.
  - `web/tsconfig.app.json` owns the browser app and includes all of `src`.
- The app-facing network boundary is `web/src/app/api/exocortexApi.ts`. Feature code should consume its `assets`, `markdown`, `pdf`, `tasks`, and `workflows` modules instead of bypassing the wrapper.
- Transport details belong in `web/src/features/workflows/api/client.ts` and `web/src/features/workflows/api/mockClient.ts`. Pages, components, and UI hooks must not add direct `fetch` or WebSocket calls.
- The mock/live mode decision happens once at startup. Use `live` or `mock`; do not add request-time fallback-to-mock behavior.
- React Query owns server state, query keys, and invalidation. Shared query helpers live in `web/src/app/api/queries.ts` and `web/src/app/lib/queryClient.ts`.
- Zustand owns local shell and UI state only. Do not duplicate server-owned asset state, markdown tree state, or task detail state in the store.
- Keep the store split by responsibility:
  - `shellUiSlice`
  - `workspaceTabsSlice`
  - `assetUiSlice`
  - `pdfUiSlice`
  - `workflowUiSlice`
- Asset UI hydration and persistence belong in `web/src/app/hooks/useAssetUiStateSync.ts`, not in scattered component effects.
- Task subscription, refresh, and task-completion notifications belong in `web/src/features/tasks/TaskCenterContext.tsx`, not in the app store.
- Shared UI primitives should stay centralized in `web/src/features/shared/ContextMenu.tsx` and `web/src/features/shared/Modal.tsx`.
- Shared sidebar and markdown helpers belong in:
  - `web/src/features/sidebar/treeUtils.ts`
  - `web/src/features/markdown/renderAdapter.ts`
- Keep feature styles close to the feature. Global CSS should remain limited to app-level layout and theme/token files.

## Frontend Composition Patterns To Preserve

- Workflow orchestration is split across controllers and composed shell pieces:
  - behavior in `web/src/features/workflows/controllers/*`
  - host components in `web/src/features/workflows/components/*`
- Do not reintroduce a monolithic workflow bridge component.
- Keep PDF code split by responsibility:
  - data/container work in `PdfPaneContainer.tsx` and `usePdfDocument.ts`
  - UI orchestration in `PdfPane.tsx`
  - presentation pieces in `web/src/features/pdf/components/*`
  - interaction state in `web/src/features/pdf/hooks/*`
  - pure geometry/constants/types in `geometry.ts`, `constants.ts`, and `types.ts`
- PDF pages render in-app via `pdf.js` canvas using `/api/assets/{asset_name:path}/pdf/file`; do not regress to server-rendered page PNGs as the primary path.
- Keep sidebar code split by responsibility:
  - container in `SidebarPane.tsx`
  - tree and list views in `MarkdownTree.tsx` and `AssetList.tsx`
  - pure helpers in `treeUtils.ts`
- Cross-feature commands should flow through controllers, providers, and explicit store request state. Do not use `window.dispatchEvent`, `CustomEvent`, DOM slot lookup, or portal discovery as an app architecture pattern.

## Runtime And Release Rules

- `python run_web.py --dev` may auto-build the frontend when inputs are newer than `web/dist`.
- Default `python run_web.py` is production-style and requires an existing `web/dist`. Production runs must consume prebuilt frontend assets and must not auto-build.
- Static frontend serving happens from `web/dist` only.
- Static frontend serving must register deterministic MIME types for module assets such as `.mjs` before mounting `web/dist`, so packaged PDF workers load consistently across Windows machines.
- Runtime KaTeX assets must come from `web/public/vendor/katex` and the built copy under `web/dist/vendor/katex`. Do not make runtime behavior depend on `web/node_modules` or a CDN.
- Packaging is a staged pipeline in `build_dist.py`:
  - `dependencies`
  - `frontend`
  - `package`
  - `installer`
  - `validate`
- Each packaging stage should remain runnable on its own. Keep packaging changes aligned with that staged contract.

## Verification Contract

- Python verification commands:
  - `python -m ruff check .`
  - `python -m pytest`
- Frontend verification commands:
  - `npm ci`
  - `npm run generate:contracts`
  - `npm run lint`
  - `npm run typecheck`
  - `npm run test:unit -- --run`(--run is important)
  - `npm run build`
- CI in `.github/workflows/ci.yml` is the canonical gate. Local workflows should stay aligned with those commands.

## Change Discipline

- If you change backend schemas, update the generated frontend contracts in the same change.
- If you add an API endpoint, wire it through the shared backend schema/service layers and the centralized frontend client instead of inventing a feature-local transport path.
- If you touch legacy behavior, prefer moving new code toward `server/domain/*`, `server/services/*`, and typed contracts instead of expanding direct legacy usage.
- If you add new UI coordination, first look for an existing controller, provider, query helper, or store slice before creating a new communication mechanism.
