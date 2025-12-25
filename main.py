import re
import sys
from pathlib import Path

def read_file_content(file_path: Path) -> str:
    """
    尝试以不同编码读取文件，返回解码后的字符串。
    解决 'UnicodeDecodeError' 和中文乱码问题。
    """
    # 按照优先级尝试编码
    # 1. utf-8: 标准格式
    # 2. gb18030: 包含 GBK 和 GB2312，Windows 常见中文编码
    # 3. latin-1: 最后的兜底，但中文会变成乱码，仅防止程序崩溃
    candidate_encodings = ["utf-8", "gb18030"]
    
    raw_bytes = file_path.read_bytes()
    
    for enc in candidate_encodings:
        try:
            content = raw_bytes.decode(enc)
            return content
        except UnicodeDecodeError:
            continue
            
    # 如果以上都失败，抛出异常或使用 replace 策略
    print(f"⚠️  警告: 无法识别 {file_path.name} 的编码，尝试强制读取...")
    return raw_bytes.decode("utf-8", errors="replace")

def clean_markdown_file(file_path: Path) -> None:
    # 1. 读取 (智能解码)
    content = read_file_content(file_path)

    # --- 你的原始清洗逻辑 (保持不变) ---
    def fix_latex_syntax(text: str) -> str:
        return text.replace("\\\\", "\\")

    content = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", content, flags=re.DOTALL)
    content = re.sub(r"\\\((.*?)\\\)", r"$\1$", content, flags=re.DOTALL)

    def clean_inline(match: re.Match[str]) -> str:
        inner = fix_latex_syntax(match.group(1))
        inner = inner.replace("\u00A0", " ").replace("\u3000", " ").strip()
        return f"${inner}$"

    content = re.sub(
        r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", clean_inline, content, flags=re.DOTALL
    )

    pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)

    def reform_block(match: re.Match[str]) -> str:
        math_content = fix_latex_syntax(match.group(1))
        lines = math_content.splitlines()
        clean_lines = []
        for line in lines:
            stripped = line.strip().replace("\u00A0", " ").replace("\u3000", " ")
            stripped = stripped.replace("\u200b", " ").replace("\ufeff", " ")
            if stripped:
                clean_lines.append(stripped)
        cleaned_math_body = "\n".join(clean_lines)
        return f"\n\n$$\n{cleaned_math_body}\n$$\n\n"

    new_content = pattern.sub(reform_block, content)

    lines = new_content.splitlines()
    processed_lines = []
    in_code_block = False
    strip_chars = " \t\u00A0\u3000"

    for line in lines:
        if re.match(r"^\s*```", line):
            in_code_block = not in_code_block
            processed_lines.append(line.lstrip(strip_chars))
            continue
        if in_code_block:
            processed_lines.append(line)
        else:
            processed_lines.append(line.lstrip(strip_chars))

    new_content = "\n".join(processed_lines)
    new_content = re.sub(r"\n{3,}", "\n\n", new_content)

    # --- 关键修改 ---
    # encoding="utf-8": 默认就是无 BOM 的 UTF-8
    # 确保 newline 为 \n，防止 Windows 自动转为 \r\n 导致某些 Linux 工具处理异常
    file_path.write_text(new_content, encoding="utf-8", newline="\n")
    
    print(f"✅ 已清洗并转为 UTF-8 (No BOM): {file_path.name}")

def process_folder(folder_path_str: str) -> None:
    folder = Path(folder_path_str)
    if not folder.exists():
        print(f"❌ 路径不存在: {folder}")
        return

    print(f"📂 正在处理: {folder.resolve()}")
    md_files = list(folder.rglob("*.md"))
    
    if not md_files:
        print("ℹ️  未找到 .md 文件")
        return

    for file_path in md_files:
        try:
            clean_markdown_file(file_path)
        except Exception as e:
            print(f"❌ 处理失败 {file_path.name}: {e}")

    print("-" * 30)
    print("处理完成。")

# 请替换为你的实际路径
process_folder("prompts")