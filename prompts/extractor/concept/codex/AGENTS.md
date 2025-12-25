<INSTRUCTIONS>

# Responsibilities & Scope

* This module is responsible for extracting the **Core Concepts** of the paper (minimal knowledge units that are reasonable, implementable, and reusable) and clarifying "why they count as core."
* **Default to treating paper content as sensitive information:** Avoid pasting large chunks of the original text; prioritize **paraphrasing + citation localization** (section/figure number/formula number).

# Input/Output
* Input: `input/input.md`
* Output: `/output/concept.md`

# Deliverables (Mandatory Generation)

* `/output/concept.md`: Extracts the core concepts involved in the paper (including reasoning for selection and localization basis).

## Markdown Output Standards (Must Adhere To)

* Output entirely in English; ensure a clear structure using headings, lists, and tables to assist reading.
* Mathematical Formulas:
* Use `$...$` for inline formulas.
* Use `

$$
...
$$

` for formula blocks.

* **Code/Pseudocode:** Use fenced code blocks (write: `lang ... `).
* **Multi-subfigures:** Explain in segments like `(a)(b)(c)` or "Fig 1(a)/Fig 1(b)"; when citing, describe the corresponding region/label/arrow color.

# Core Concept Determination (Key Focus)

## What Counts as a "Concept"

A "Concept" is one of the minimal knowledge units capable of carrying reasoning, implementation, or reuse. Common forms include:

* **Objective/Energy/Loss:** What is to be minimized/maximized (including physical/geometric meanings).
* **State/Variable/Parameterization:** What are the unknowns? What are the spaces/dimensions/constraints?
* **Operator/Discretization:** Gradient, Divergence, Laplacian, Mass Matrix, Stiffness Matrix, Discrete Exterior Calculus, Hodge star, etc., and how they map onto meshes/basis functions.
* **Optimization & Numerical Algorithms:** Newton/Gauss-Newton/LM, Local-Global, ADMM, Line Search, Preconditioned Conjugate Gradient, Time Integration (Explicit/Implicit), especially paper-specific variants.
* **Geometric/Physical Assumptions:** Material models, inextensibility/incompressibility, thin shell/rod models, boundary conditions, stability assumptions, etc.
* **Data Structure/Implementation Mechanism:** Multi-resolution, hierarchical solvers, constraint projection, collision handling, caching/pre-factorization strategies (if the paper claims this as a key contribution).

## Which "Concepts" are Worth Including

Score/filter candidate concepts by "Value". A concept is usually worth including in `concept.md` if it satisfies at least 2 of the following:

* **Centrality:** Impossible to explain the method's main flow/core formulas/key experiments without understanding it.
* **Novelty:** New definitions, new energy terms, new discretizations, new solution flows, or new stability tricks proposed by the paper.
* **High Reusability:** Transferable to other graphics problems (e.g., generic discrete operators, generic optimization frameworks, reusable constraint forms).
* **Implementability:** Can directly guide code implementation (clear input/output/steps/complexity/numerical caveats).
* **High Frequency:** Appears repeatedly in the Abstract/Contribution List/Subsection Headers/Multiple Formulas, or is strongly bound to key figures/tables.

## Rapid Determination Process

For each candidate concept, answer 5 questions (Yes/No) sequentially and note the basis location in `concept.md`:

1. Does it appear in the Title/Abstract/Contributions/Subsection Headers?
2. Does it directly correspond to a key formula (Objective Function, Discrete Operator, Update Rule)?
3. Would removing it make the method's main flow illogical (Irreplaceable)?
4. Does it bring something new (New Definition/New Term/New Discretization/New Solving Technique/New Stability Handling)?
5. Can it be translated into implementation points (Input/Output/Steps/Complexity/Numerical Notes)?
**Rule:** Usually, if "Yes" ≥ 2, include as a Core Concept; if "Yes" = 1 and it belongs to background common knowledge, put it in "Prerequisites (Optional)".

## Non-Core/How to Handle

* **Pure Background Knowledge** (e.g., "Gradient Descent", "Least Squares") if strictly mentioned in passing: Do not put in Core Concepts; list briefly in the "Prerequisites (Optional)" list at the end.
* **Undefined by Paper but Deemed Important:** Can be included, but must be labeled "Not explicitly defined in paper/Requires supplementary reading/Inferred from context," and provide the location basis for your inference.

# Output Template

## `/output/concept.md`

* List of Core Concepts (Sorted by importance)
* Dependency Graph between concepts (Text version: A -> B -> C)
* Prerequisites (Optional)

Each "Core Concept" is suggested to include:

* **Name + Type** (Definition/Energy/Operator/Algorithm/Assumption)
* **What it solves/Intuition** (2–5 sentences)
* **Mathematical Form** (Cite corresponding formula ID, paste key equation if necessary)
* **How it is used in the method flow** (Input/Output/Steps)
* **Why it is Core** (Correspond to the value criteria above, specify which ones are met)

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