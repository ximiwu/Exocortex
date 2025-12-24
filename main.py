from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# from assets.assets_manager import AssetInitResult, asset_init, _clean_markdown_file

# DEFAULT_PDF = Path("A Chebyshev Semi-Iterative Approach for Accelerating.pdf")


# def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
#     parser = argparse.ArgumentParser(description="Initialize an asset from a PDF.")
#     parser.add_argument(
#         "pdf",
#         nargs="?",
#         default=DEFAULT_PDF,
#         type=Path,
#         help=f"Path to the PDF to process (default: {DEFAULT_PDF})",
#     )
#     parser.add_argument(
#         "--asset-name",
#         "-a",
#         help="Target asset name (default: PDF file name without extension).",
#     )
#     return parser.parse_args(argv)


# def main(argv: list[str] | None = None) -> int:
#     args = parse_args(argv)
#     try:
#         result: AssetInitResult = asset_init(args.pdf, args.asset_name)
#     except Exception:
#         logging.exception("Asset initialization failed.")
#         return 1

#     print(f"Asset directory: {result.asset_dir.resolve()}")
#     print(f"Raw PDF: {result.raw_pdf_path.resolve()}")
#     print(
#         f"References ({len(result.reference_files)} file(s)): "
#         f"{result.references_dir.resolve()}"
#     )
#     return 0


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
#     sys.exit(main())


# import re

# def _clean_markdown_file(file_path: Path):
#     content = file_path.read_text(encoding="utf-8-sig")
#     content = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', content, flags=re.DOTALL)
#     def clean_inline(match):
#         inner = match.group(1).replace('\u00A0', ' ').replace('\u3000', ' ').strip()
#         return f"${inner}$"
#     content = re.sub(r'\\\((.*?)\\\)', clean_inline, content, flags=re.DOTALL)
#     pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)

#     def reform_block(match):
#         math_content = match.group(1)
#         lines = math_content.splitlines()
#         clean_lines = []
#         for line in lines:
#             stripped = line.strip().replace("\u00A0", " ").replace("\u3000", " ").replace("\u200b", " ").replace("\ufeff", " ")
#             if stripped:
#                 clean_lines.append(stripped)
        
#         cleaned_math_body = "\n".join(clean_lines)
#         return f"\n\n$$\n{cleaned_math_body}\n$$\n\n"
#     new_content = pattern.sub(reform_block, content)

#     new_content = re.sub(r'\n{3,}', '\n\n', new_content)

#     with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
#         f.write(new_content)



import re
from pathlib import Path

def _clean_markdown_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8-sig")

    # === 辅助函数：修复 LaTeX 语法 (去转义) ===
    def _fix_latex_syntax(text):
        # 将双反斜杠 \\ 替换为单反斜杠 \
        # 注意：在 Python 字符串中，\\\\ 代表字面量的两个反斜杠
        return text.replace('\\\\', '\\')

    # 1. 统一转换 \[ \] 为 $$ $$
    content = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', content, flags=re.DOTALL)

    # 2. 统一转换 \( \) 为 $ $
    # 先把 \( ... \) 这种格式转成 $ ... $，后续统一在步骤3处理内容
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content, flags=re.DOTALL)

    # 3. 处理行内公式 $...$ (修复 \\epsilon 为 \epsilon，并去除多余空格)
    # 正则解释：(?<!\$) 表示前面不能是 $，(?!\$) 表示后面不能是 $，确保只匹配单个 $ 包裹的内容
    def clean_inline(match):
        inner = match.group(1)
        # 修复转义字符
        inner = _fix_latex_syntax(inner)
        # 清洗特殊空格
        inner = inner.replace('\u00A0', ' ').replace('\u3000', ' ').strip()
        return f"${inner}$"
    
    content = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', clean_inline, content, flags=re.DOTALL)

    # 4. 处理块级公式 $$...$$ (修复语法 + 重新排版)
    pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    def reform_block(match):
        math_content = match.group(1)
        
        # 修复转义字符 (例如 \\epsilon -> \epsilon)
        math_content = _fix_latex_syntax(math_content)
        
        lines = math_content.splitlines()
        clean_lines = []
        for line in lines:
            stripped = line.strip().replace("\u00A0", " ").replace("\u3000", " ").replace("\u200b", " ").replace("\ufeff", " ")
            if stripped:
                clean_lines.append(stripped)
        
        cleaned_math_body = "\n".join(clean_lines)
        return f"\n\n$$\n{cleaned_math_body}\n$$\n\n"
    
    new_content = pattern.sub(reform_block, content)

    # ================= [缩进清洗功能] =================
    lines = new_content.splitlines()
    processed_lines = []
    in_code_block = False
    strip_chars = ' \t\u00A0\u3000'

    for line in lines:
        # 检测代码块标记
        if re.match(r'^\s*```', line):
            in_code_block = not in_code_block
            processed_lines.append(line.lstrip(strip_chars))
            continue
        
        if in_code_block:
            processed_lines.append(line)
        else:
            # 非代码块，强制去除左侧缩进，解决公式不渲染问题
            processed_lines.append(line.lstrip(strip_chars))
            
    new_content = "\n".join(processed_lines)
    # =================================================

    # 5. 规范化换行符
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)

_clean_markdown_file(Path("codex/integrator/output/output.md"))

print("cleaned")
