<INSTRUCTIONS>

# Responsibilities & Scope

* This directory is responsible for extracting the **research background and pain points** of the paper, and producing structured notes that are suitable for review, flashcards, or reproduction.
* Treat paper content as sensitive information by default: Avoid pasting large chunks of the original text; prioritize paraphrasing + citation localization (section/figure number/equation number).

# Deliverables (Must Generate)

* `background/output/background.md`: Extract the research background and the pain points resolved by the paper.

## Markdown Output Standards (Must Adhere To)

* Output entirely in English; ensure a clear structure using headings, lists, and tables to assist reading.
* Mathematical Formulas:
* Use `\(...\)` for inline formulas.
* Use `\[...\]` for formula blocks.


* Code/Pseudocode: Use fenced code blocks (write as: `lang ... `).
* Multi-subfigures: Explain segment by segment using `(a)(b)(c)` or "Fig 1(a)/Fig 1(b)"; when citing, specify the corresponding region/label/arrow color.

# Output Template (Copy Structure Directly)

## `background/output/background.md`

* Paper Info: Title, Authors, Year, Keywords (Graphics direction + Math tools).
* Background: Research object/Application scenarios/Lineage of existing methods.
* Pain Points: Bottlenecks of existing methods (Accuracy/Stability/Speed/Controllability/Implementability/Theoretical aspects), and the consequences they cause.
* What this paper solves: Write the "problem" as a verifiable statement (What is the input, what is the output, what are the criteria for success).
* Core Contributions (1–5 items): For each item, use format "What was done + Why it is important + Where it is better compared to others".
* Assumptions & Limitations: Applicable conditions, failure modes, parameter sensitivity.
* Connection to Graphics/Math: Map to tags like "Optimization/Discretization/Geometry/Time Integration" for easy retrieval.

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