<INSTRUCTIONS>

# img2md (image -> Markdown)

## Must (keep it simple)
- Transcribe user-provided paper images into Markdown and save to the path user specify (allow overwrite).
- Output **in English**.
- If unclear, do not guess; mark as "(unreadable)" or "(uncertain)".

## Must not
- Do not run/install any OCR tools (e.g. `tesseract`, `pytesseract`, `easyocr`, `paddleocr`).
- Do not run any image-processing tools/scripts/commands (e.g. `PIL`).
- Do not download or fetch any content from the internet; the only allowed input source is user-provided content.

## How to write
- **Text**: copy wording as-is; keep paragraph breaks; keep headings if present.
- **Math**: inline `\(...\)`, display `\[...\]`.
- **Tables**: if small/clear, convert to a Markdown table; otherwise summarize as bullets (headers + key values) and mark unreadable cells.
- **Figures/charts**: brief description only (axes labels/units if visible, legend meaning, overall trend); never invent exact numbers/data points.

## Reading/Saving Markdown (PowerShell, UTF-8)

* Must use UTF-8 encoding for reading and saving; use the following commands directly:
* Read: `-Command [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding utf8`
* Save: `"-NoProfile -ExecutionPolicy Bypass -Command "$bytes = [System.Convert]::FromBase64String('[BASE64_STRING]'); [System.IO.File]::WriteAllBytes('{target_path}', $bytes)"`
* Search: `-Command [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; rg --encoding utf8`


## PowerShell File I/O Protocol (UTF-8 Enforced)

All file interactions must strictly enforce UTF-8 encoding to prevent character corruption or data loss.

### 1. Reading Files

To read text files safely, use `Get-Content` with explicit encoding settings.

* **Pattern:**
`powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding utf8 '{file_path}'"`

### 2. Searching Content

When using search tools (like `rg` or `grep`), ensure the console output encoding is synchronized.

* **Pattern:**
`powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; rg --encoding utf8 '{pattern}' '{path}'"`


### 3. Saving Files

Use the apply_patch shell command to edit files


## Tool Usage: Ripgrep (rg) on Windows

When searching for exact strings, especially code or LaTeX (e.g., `\sum`, `\mathbf{X}`, `(a+b)`):

1. **Use `-F**`: Always add the `--fixed-strings` (or `-F`) flag. This treats the pattern as a literal string, ignoring special regex meanings of `+`, `*`, `(`, `{`.
2. **Escaping Backslashes**: Since `-F` is active, you only need to escape the backslash for the shell string. Map a literal `\` in the target text to `\\` in the command.
* Target: `\frac{a}{b}` -> Command: `rg -F "\\frac{a}{b}"`
* Target: `C:\Path` -> Command: `rg -F "C:\\Path"`


3. **Avoid Redundancy**: Do not escape braces `{}`, parenthesis `()`, or plus signs `+` when `-F` is on.


</INSTRUCTIONS>
