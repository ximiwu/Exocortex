# 背景：
在 input/input.md 中，开头的`# 原始教学内容：`后的内容是教师最开始讲解的内容。`# 历史对话：`后面的内容，是用户学生与老师的对话内容，学生有不懂的地方，老师已经解答了。
# 任务：
学生不懂的内容是真正的精华，知识是非线性的，但对话记录是线性的。你负责把线性的对话内容整合起来，整合成一个逻辑顺畅，思维严密的笔记，方便学生复习查看。

# 要求：
1.学生的每个提问都是精华，要保证整理的笔记没有遗漏`# 历史对话：`后面的任何内容。
2.`# 原始教学内容：`在笔记中不应该被整段重复提及
3.对于对话中不标准、口语化的用语，利用`references/formula.md`和`references/concept.md`中的标准定义来修正术语
4.使用中文，markdown格式，输出到 /output/output.md中



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

</INSTRUCTIONS>
