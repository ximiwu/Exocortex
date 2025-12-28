<INSTRUCTIONS>

# img2md (image -> Markdown)

## Input/Output
- Input image: input/input.png
- Save markdown to output/output.md

## Must (keep it simple)
- Transcribe user-provided paper images into Markdown and save to the path user specify (allow overwrite).
- Output **in English**.
- If unclear, do not guess; mark as "(unreadable)" or "(uncertain)".

## How to write
- **Text**: copy wording as-is; keep paragraph breaks; keep headings if present.
- **Math**: inline `$...$`, display `

$$
...
$$

`.
- **Tables**: if small/clear, convert to a Markdown table; otherwise summarize as bullets (headers + key values) and mark unreadable cells.
- **Figures/charts**: brief description only (axes labels/units if visible, legend meaning, overall trend); never invent exact numbers/data points.


</INSTRUCTIONS>