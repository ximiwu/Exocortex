# Sidebar Controls, Split Ratios, and Desktop Titlebar

## Summary
- Fix sidebar rename so editing never starts row dragging, and the alias text is fully selected as soon as rename starts.
- Replace inline sidebar close buttons and the `open all markdown under asset` toolbar button with richer right-click actions plus a new sidebar display settings modal.
- Make the two desktop pane boundaries draggable, persist their positions as ratios in each asset’s `config.json`, and restore them when that asset is reopened.
- Add a desktop-only custom web titlebar for the `pywebview` shell, remove the native titlebar there, and launch the desktop window maximized.

## Public Interfaces and State Changes
- Extend asset UI state with two new API fields:
  - `sidebarWidthRatio`
  - `rightRailWidthRatio`
- Persist those in asset `config.json` as snake_case keys:
  - `sidebar_width_ratio`
  - `right_rail_width_ratio`
- Add system-wide app config API and schema for `Documents/ximiwu_app/Exocortex/config.json` with these fields:
  - `sidebarTextLineClamp`
  - `sidebarFontSizePx`
- Persist system config as snake_case keys:
  - `sidebar_text_line_clamp`
  - `sidebar_font_size_px`
- Add new backend endpoint for tutor-session deletion:
  - `DELETE /api/assets/{asset_name}/groups/{group_idx}/tutors/{tutor_idx}`
- Reuse existing endpoints for:
  - group delete
  - ask-history markdown delete
  - asset UI-state persistence
- Regenerate frontend contracts after schema changes in the same change.

## Implementation Changes
- Desktop workspace uses draggable splitters only in the existing 3-column desktop layout; below the current responsive breakpoint the existing 2-column and 1-column layouts stay unchanged and splitters are hidden.
- Store split positions as proportions, not pixels. Defaults come from the current visual baseline `180:440:340`. Clamp drag updates so sidebar, markdown, and PDF panes never shrink below their current desktop minimums.
- Sidebar rename behavior changes:
  - editing rows do not receive drag handlers
  - the input selects all text immediately on focus/mount
  - input pointer interaction is isolated so text selection cannot trigger drag
- Sidebar item text rendering changes:
  - every button gets a hard max width from its container
  - overflow is clipped with no ellipsis
  - line count and font size come from system config
  - default system config when missing is `1` line and `14px`
- Replace the toolbar’s `open all markdown under asset` action with a sidebar display settings button that opens a modal with:
  - line clamp input, default `1`, allowed range `1-6`
  - font size input in px, default `14`, allowed range `10-24`
  - save/cancel actions
- Move all inline sidebar close affordances into the tree context menu. Menu behavior is:
  - any node with an open file or open descendants gets `close` in danger styling
  - renameable nodes keep `rename alias`
  - `group` nodes add `locate in pdf`, `history ask session`, `delete`
  - `tutor` nodes add `history question`, `delete`
  - `ask` nodes add `delete`
- `close` behavior is node-scoped:
  - leaf node closes its own tab
  - branch node closes all open descendant tabs
- `delete` behavior is node-scoped and confirmed before execution:
  - `group` deletes the full `group_data/<group_idx>` directory via the existing group-delete backend flow, then closes descendant tabs and refreshes asset/tree state
  - `tutor` deletes `group_data/<group_idx>/tutor_data/<tutor_idx>`, then closes descendant tabs and refreshes asset/tree state
  - `ask` deletes the matching markdown under `ask_history`, closes that tab if open, and refreshes asset/tree state
- `locate in pdf` parses `group:<idx>`, uses the current `assetState.groups[].blockIds` order, resolves the first block’s `pageIndex`, and moves the PDF pane to that page.
- `history ask session` modal is built from the clicked group’s existing tutor children:
  - each row uses the tutor node title, which already reflects `focus.md` alias
  - double-click opens that `focus.md`
  - checkboxes allow multi-select
  - confirm opens all selected `focus.md` files
  - one toggle button switches between select-all and clear-all
- `history question` modal is built from the clicked tutor node’s existing `ask` children and uses the same double-click, multi-select, confirm, and select-all/clear-all behavior.
- Desktop shell changes:
  - `run_web.py` creates the `pywebview` window with `frameless=True` and `maximized=True`
  - expose a small webview JS API for `minimize`, `toggleMaximize`, `close`, and current maximize state
  - render the custom titlebar only when running inside desktop shell
  - browser mode keeps normal browser chrome and does not try to emulate window controls
  - place the window controls on the top-right of the web titlebar and move the existing theme toggle out of their way into the same titlebar layout

## Test Plan
- Backend tests cover:
  - loading and saving system app config with defaults and validation
  - asset UI-state persistence for split ratios
  - tutor-session deletion staying inside the asset root and deleting only the targeted folder
- Frontend unit tests cover:
  - rename input auto-selects and disables drag while editing
  - context menu entries appear for the correct node kinds
  - `locate in pdf` uses the first `blockIds` entry for the target group
  - history-session and history-question modals support double-click open, multi-select open, and select-all/clear-all
  - split ratio drag/clamp/persist/restore behavior
  - desktop shell bridge is a safe no-op outside `pywebview`
- Verification commands stay aligned with repo policy:
  - `python -m ruff check .`
  - `python -m pytest`
  - `cd web && npm run generate:contracts`
  - `cd web && npm run lint`
  - `cd web && npm run typecheck`
  - `cd web && npm run test:unit -- --run`

## Assumptions
- `history ask session` is scoped to the clicked group’s `tutor_data`, not the whole asset.
- `history question` is scoped to the clicked tutor session’s `ask_history`.
- `locate in pdf` treats the first block as the first entry in the saved `blockIds` order for that group.
- Splitters are active only in the desktop 3-pane layout; responsive collapsed layouts do not persist alternate mobile/tablet positions.
- If system config is missing, sidebar text defaults to `1` line and `14px`.
