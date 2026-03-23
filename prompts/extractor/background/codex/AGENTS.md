# Input/Output
* Input: `input/input.md`
* Output: `/output/background.md`

# Output Template

## `/output/background.md`

* Paper Info: Title, Authors, Year, Keywords (Graphics direction + Math tools).
* Background: Research object/Application scenarios/Lineage of existing methods.
* Pain Points: Bottlenecks of existing methods (Accuracy/Stability/Speed/Controllability/Implementability/Theoretical aspects), and the consequences they cause.
* What this paper solves: Write the "problem" as a verifiable statement (What is the input, what is the output, what are the criteria for success).
* Core Contributions (1–5 items): For each item, use format "What was done + Why it is important + Where it is better compared to others".
* Assumptions & Limitations: Applicable conditions, failure modes, parameter sensitivity.
* Connection to Graphics/Math: Map to tags like "Optimization/Discretization/Geometry/Time Integration" for easy retrieval.

## PowerShell File I/O Protocol (UTF-8 Enforced)

All file interactions must strictly enforce UTF-8 encoding to prevent character corruption or data loss.