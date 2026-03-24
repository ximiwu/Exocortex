

## 背景
/output/main.md 和 /input/supplement.md 是对同一问题的不同侧重点讲解。
* **/output/main.md**：严谨性优先
* **/input/supplement.md**：直觉、原理优先

## 任务
Update `/output/main.md` in place.

1.以main.md原有内容为主，将 /input/supplement.md 中讲的好的内容融入/output/main.md中，使main.md的讲解效果更好

2.检查并改正不正确的latex代码包裹方式：例如f"`{latex}`"、f"`${latex}$`"等，正确的包裹方式一定是f"${latex}$"或f"$${latex}$$"

## File I/O Protocol (UTF-8 Enforced)
All file interactions must strictly enforce UTF-8 encoding to prevent character corruption or data loss.