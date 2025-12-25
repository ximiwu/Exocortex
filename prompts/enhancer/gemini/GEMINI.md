## Instraction

## Inputs (load with @)
@output/main.md
@input/supplement.md

## Output
Update `/output/main.md` in place.

**Context:**
/output/main.md 和 /input/supplement.md 是对同一问题的不同角度讲解。
* **/output/main.md**：数学严谨，是目标产物需要达到的深度。
* **/input/supplement.md**：直觉极佳，非常易懂。

**Problem:**
/output/main.md 对初学者来说太难了，全是数学符号，看的时候脑子里建立不起图像。
/input/supplement.md 讲解深度太浅了
**Task:**
### 第一步：增量式改进
以 **材料 /output/main.md 的逻辑结构和数学深度** 为主轴，将 /input/supplement.md 中适合插入的片段增量式插入/output/main.md ，禁止删减 main.md的原有内容

**关键要求（Critical Instructions）：**
1. **结构锁定**：必须保留 main.md 中原有的所有内容，不要删减数学细节。
2. **直觉前置**：在每一个数学公式或概念提出**之前**，先用 **材料 /input/supplement.md 中的直觉、类比** 进行通俗引入。
3. **桥接说明**：明确指出“物理直觉”是如何对应到“数学符号”的。

**Goal:**
让最终产物既能看懂物理图像（/input/supplement.md的功劳），又能顺滑地过渡到严谨的数学推导（/output/main.md的功劳），最终无痛掌握 /output/main.md 的内容。

### 第二步：复审（IMPORTANT）
仔细检查 /output/main.md 是否有latex语法错误，必须确保md文件能成功渲染