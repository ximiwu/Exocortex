# Using Gemini CLI for Large Codebase Analysis

When analyzing large codebases or multiple files that might exceed context limits, use the Gemini CLI with its massive
context window. Use `gemini --m "gemini-3-pro-preview" --yolo "<instruction>"` to leverage Google Gemini's large context capacity.

## File and Directory Inclusion Syntax

Use the `@` syntax to include files and directories in your Gemini prompts. The paths should be relative to WHERE you run the
  gemini command:

### Examples:

**Single file analysis:**
gemini --m "gemini-3-pro-preview" --yolo "@src/main.py Explain this file's purpose and structure"

Multiple files:
gemini --m "gemini-3-pro-preview" --yolo "@package.json @src/index.js Analyze the dependencies used in the code"

Entire directory:
gemini --m "gemini-3-pro-preview" --yolo "@src/ Summarize the architecture of this codebase"

Multiple directories:
gemini --m "gemini-3-pro-preview" --yolo "@src/ @tests/ Analyze test coverage for the source code"

Current directory and subdirectories:
gemini --m "gemini-3-pro-preview" --yolo "@./ Give me an overview of this entire project"

# Or use --all_files flag:
gemini --all_files --m "gemini-3-pro-preview" --yolo "Analyze the project structure and dependencies"

Implementation Verification Examples

Check if a feature is implemented:
gemini --m "gemini-3-pro-preview" --yolo "@src/ @lib/ Has dark mode been implemented in this codebase? Show me the relevant files and functions"

Verify authentication implementation:
gemini --m "gemini-3-pro-preview" --yolo "@src/ @middleware/ Is JWT authentication implemented? List all auth-related endpoints and middleware"

Check for specific patterns:
gemini --m "gemini-3-pro-preview" --yolo "@src/ Are there any React hooks that handle WebSocket connections? List them with file paths"

Verify error handling:
gemini --m "gemini-3-pro-preview" --yolo "@src/ @api/ Is proper error handling implemented for all API endpoints? Show examples of try-catch blocks"

Check for rate limiting:
gemini --m "gemini-3-pro-preview" --yolo "@backend/ @middleware/ Is rate limiting implemented for the API? Show the implementation details"

Verify caching strategy:
gemini --m "gemini-3-pro-preview" --yolo "@src/ @lib/ @services/ Is Redis caching implemented? List all cache-related functions and their usage"

Check for specific security measures:
gemini --m "gemini-3-pro-preview" --yolo "@src/ @api/ Are SQL injection protections implemented? Show how user inputs are sanitized"

Verify test coverage for features:
gemini --m "gemini-3-pro-preview" --yolo "@src/payment/ @tests/ Is the payment processing module fully tested? List all test cases"

When to Use Gemini CLI

Use gemini --m "gemini-3-pro-preview" --yolo when:
- Analyzing entire codebases or large directories
- Comparing multiple large files
- Need to understand project-wide patterns or architecture
- Current context window is insufficient for the task
- Working with files totaling more than 100KB
- Verifying if specific features, patterns, or security measures are implemented
- Checking for the presence of certain coding patterns across the entire codebase

Important Notes

- Paths in @ syntax are relative to your current working directory when invoking gemini
- The CLI will include file contents directly in the context
- No need for --yolo flag for read-only analysis
- Gemini's context window can handle entire codebases that would overflow Claude's context
- When checking implementations, be specific about what you're looking for to get accurate results