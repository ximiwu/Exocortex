from __future__ import annotations

import re

from PySide6 import QtCore

from .constants import KATEX_CDN_BASE, KATEX_LOCAL_DIR, KATEX_RENDER_SCRIPT

try:
    import markdown
except ImportError:  # pragma: no cover
    markdown = None

try:
    import pymdownx.arithmatex  # type: ignore # noqa: F401
    _ARITHMETEX_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ARITHMETEX_AVAILABLE = False


_BOLD_SYMBOL_PATTERN = re.compile(r"\\mathbf\\s*\\{\\s*(\\\\[A-Za-z]+)\\s*\\}")
# 用于处理 note 样式的 regex
_DETAILS_TAG_PATTERN = re.compile(r"<details\b([^>]*)>", re.IGNORECASE)
_CLASS_ATTR_PATTERN = re.compile(r"\bclass\s*=\s*(\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)
_MARKDOWN_ATTR_PATTERN = re.compile(r"\bmarkdown\s*=", re.IGNORECASE)
_DETAILS_BLOCK_PATTERN = re.compile(r"<details\b[^>]*>.*?</details>", re.IGNORECASE | re.DOTALL)


def normalize_math_content(content: str) -> str:
    """Adjust math macros to keep KaTeX happy."""
    return _BOLD_SYMBOL_PATTERN.sub(r"\\boldsymbol{\1}", content)


def normalize_details_attrs(attrs: str) -> tuple[str, bool]:
    """处理 details 标签的 class，识别是否有 note 样式"""
    attrs_text = attrs
    class_match = _CLASS_ATTR_PATTERN.search(attrs_text)
    has_note = False
    if class_match:
        class_value = class_match.group(2) or class_match.group(3) or ""
        classes = class_value.split()
        has_note = "note" in classes or "note-container" in classes
        if has_note and "note-container" not in classes:
            classes.append("note-container")
            new_value = " ".join(classes)
            attrs_text = (
                attrs_text[: class_match.start()]
                + f' class="{new_value}"'
                + attrs_text[class_match.end() :]
            )
    # 确保 details 内部总是开启 markdown 解析
    if not _MARKDOWN_ATTR_PATTERN.search(attrs_text):
        attrs_text = attrs_text.rstrip() + ' markdown="1"'
    return attrs_text, has_note


def normalize_note_content_divs(block: str) -> str:
    """给 note 样式的 details 内容包裹一层 div，便于 CSS 控制"""
    # 这里的逻辑保持不变，为了配合你的 CSS
    div_pattern = re.compile(r"<div\b([^>]*)>", re.IGNORECASE)
    
    def replace_div(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if not _MARKDOWN_ATTR_PATTERN.search(attrs):
            return match.group(0)
        class_match = _CLASS_ATTR_PATTERN.search(attrs)
        if class_match:
            class_value = class_match.group(2) or class_match.group(3) or ""
            classes = class_value.split()
            if "note-content" not in classes:
                classes.append("note-content")
                new_value = " ".join(classes)
                attrs = (
                    attrs[: class_match.start()]
                    + f' class="{new_value}"'
                    + attrs[class_match.end() :]
                )
        else:
            attrs = f' class="note-content"{attrs}'
        return f"<div{attrs}>"

    return div_pattern.sub(replace_div, block)


def normalize_details_markdown(content: str) -> str:
    """预处理 details 块，添加 markdown='1' 并处理 note 样式"""
    def replace_block(match: re.Match[str]) -> str:
        block = match.group(0)
        tag_match = _DETAILS_TAG_PATTERN.search(block)
        if not tag_match:
            return block
        attrs = tag_match.group(1)
        new_attrs, has_note = normalize_details_attrs(attrs)
        # 替换开头的 <details ...>
        block = block.replace(tag_match.group(0), f"<details{new_attrs}>", 1)
        if has_note:
            block = normalize_note_content_divs(block)
        return block

    return _DETAILS_BLOCK_PATTERN.sub(replace_block, content)


def katex_assets() -> str:
    """(保持原样) 生成 KaTeX 的资源链接"""
    local_available = (KATEX_LOCAL_DIR / "katex.min.js").is_file()
    # ... (省略中间路径逻辑，保持你原来的代码即可) ...
    if local_available:
        base_url = QtCore.QUrl.fromLocalFile(str(KATEX_LOCAL_DIR)).toString(QtCore.QUrl.FullyEncoded)
        css = (
            f'<link rel="stylesheet" href="{base_url}/katex.min.css">'
            f'<link rel="stylesheet" href="{base_url}/contrib/copy-tex.css">'
        )
        scripts = (
            f'<script src="{base_url}/katex.min.js"></script>'
            f'<script src="{base_url}/contrib/copy-tex.min.js"></script>'
            f'<script src="{base_url}/contrib/auto-render.min.js"></script>'
        )
    else:
        css = (
            f'<link rel="stylesheet" href="{KATEX_CDN_BASE}/katex.min.css">'
            f'<link rel="stylesheet" href="{KATEX_CDN_BASE}/contrib/copy-tex.css">'
        )
        scripts = (
            f'<script src="{KATEX_CDN_BASE}/katex.min.js"></script>'
            f'<script src="{KATEX_CDN_BASE}/contrib/copy-tex.min.js"></script>'
            f'<script src="{KATEX_CDN_BASE}/contrib/auto-render.min.js"></script>'
        )
    render_helper_url = QtCore.QUrl.fromLocalFile(str(KATEX_RENDER_SCRIPT)).toString(QtCore.QUrl.FullyEncoded)
    scripts += f'<script src="{render_helper_url}"></script>'
    return css + scripts

# def render_markdown_content(content: str) -> str:
#     if markdown is None:
#         raise RuntimeError("Missing 'markdown' package.")
#     if not _ARITHMETEX_AVAILABLE:
#         raise RuntimeError("Missing 'pymdown-extensions'.")

#     extensions = ["extra", "sane_lists", "fenced_code", "tables", "pymdownx.arithmatex"]
#     extension_configs = {"pymdownx.arithmatex": {"generic": True}}

#     normalized = normalize_math_content(content.lstrip("\ufeff"))
#     normalized = normalize_details_markdown(normalized)
    
#     md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    
#     block_elements = md.block_level_elements
#     if isinstance(block_elements, set):
#         block_elements.update({"details", "summary"})
#     else:
#         for tag in ("details", "summary"):
#             if tag not in block_elements:
#                 block_elements.append(tag)
                
#     body = md.convert(normalized)

#     # -----------------------------------------------------------
#     # 修改点 1：CSS 样式更新
#     # 增加了 .tab-content-area 的显示/隐藏控制
#     # -----------------------------------------------------------
#     styles = """
#     body { font-family: 'Times New Roman','Segoe UI',sans-serif; font-size: 16px; line-height: 1.6; color: #222; padding: 16px; }
#     p { margin: 0.6em 0; }
#     pre { background: #f7f7f7; padding: 10px; border: 1px solid #e0e0e0; overflow-x: auto; }
#     code { font-family: 'JetBrains Mono',monospace; font-size: 0.95em; }
#     img { max-width: 100%; }
#     table { border-collapse: collapse; width: 100%; margin: 12px 0; }
#     th, td { border: 1px solid #dcdcdc; padding: 10px 12px; }
#     thead th { background: #f5f5f5; }
    
#     /* 笔记样式 */
#     details.note-container { 
#         background-color: #F8F6E4; 
#         border-left: 5px solid #E0D785; 
#         margin: 10px 0; 
#         padding: 10px; 
#         border-radius: 4px; 
#     }
#     details.note-container summary { 
#         font-weight: bold; 
#         color: #f57f17; 
#         cursor: pointer; 
#         outline: none; 
#     }
#     .note-content { margin-top: 10px; font-size: 0.9em; }

#     /* Tabs 样式 */
#     .tab-wrapper {
#         margin: 15px 0;
#         border: 1px solid #ddd;
#         border-radius: 6px;
#         overflow: hidden;
#         box-shadow: 0 2px 5px rgba(0,0,0,0.05);
#         transition: all 0.3s ease;
#     }
#     .tab-header {
#         display: flex;
#         background: #f1f3f4;
#         border-bottom: 1px solid #ddd; /* 默认有底边框 */
#         overflow-x: auto;
#     }
#     /* 当没有内容展开时，移除 header 的底边框，让它看起来像一个完整的圆角条 */
#     .tab-wrapper:not(.expanded) .tab-header {
#         border-bottom: none;
#     }

#     .tab-btn {
#         flex: 1;
#         padding: 12px 15px;
#         border: none;
#         background: none;
#         cursor: pointer;
#         font-weight: 600;
#         color: #5f6368;
#         border-right: 1px solid #e0e0e0;
#         transition: background 0.2s, color 0.2s;
#         min-width: 80px;
#         text-align: center;
#     }
#     .tab-btn:last-child { border-right: none; }
#     .tab-btn:hover { background: #e8eaed; color: #202124; }
    
#     .tab-btn.active {
#         background: #fff;
#         color: #1a73e8;
#         border-bottom: 2px solid #1a73e8;
#         margin-bottom: -1px; 
#     }
    
#     .tab-content-area {
#         background: #fff;
#         padding: 20px;
#         display: none; /* 默认隐藏内容区域 */
#     }
    
#     /* 只有当 wrapper 拥有 expanded 类时才显示内容区域 */
#     .tab-wrapper.expanded .tab-content-area {
#         display: block;
#     }

#     .tab-pane { display: none; animation: fadeEffect 0.3s; }
#     .tab-pane.active { display: block; }
#     @keyframes fadeEffect { from {opacity: 0;} to {opacity: 1;} }
    
#     .tab-pane > details > summary { display: none; }
#     .tab-pane > details.note-container { 
#         border: none; margin: 0; padding: 0; background: none; box-shadow: none; 
#     }
#     """

#     # -----------------------------------------------------------
#     # 修改点 2：JS 逻辑更新
#     # 1. 初始化时不设置 active
#     # 2. 点击时支持 toggle（已激活则关闭，未激活则打开）
#     # -----------------------------------------------------------
#     tabs_script = """
#     <script>
#     (function() {
#         function initTabs() {
#             const allDetails = Array.from(document.querySelectorAll('details'));
#             const processed = new Set();
            
#             allDetails.forEach(detail => {
#                 if (processed.has(detail)) return;
                
#                 let siblings = [detail];
#                 let next = detail.nextElementSibling;
                
#                 while (next) {
#                     if (next.tagName && next.tagName.toLowerCase() === 'details') {
#                         siblings.push(next);
#                         processed.add(next);
#                         next = next.nextElementSibling;
#                     } else if (next.nodeType === 3 && !next.textContent.trim()) {
#                         next = next.nextSibling;
#                     } else {
#                         break;
#                     }
#                 }
                
#                 processed.add(detail);
                
#                 if (siblings.length >= 2) {
#                     createTabGroup(siblings);
#                 }
#             });
#         }

#         function createTabGroup(detailsList) {
#             const wrapper = document.createElement('div');
#             wrapper.className = 'tab-wrapper'; // 默认没有 expanded 类
            
#             const header = document.createElement('div');
#             header.className = 'tab-header';
            
#             const contentArea = document.createElement('div');
#             contentArea.className = 'tab-content-area';
            
#             const firstDetail = detailsList[0];
#             firstDetail.parentNode.insertBefore(wrapper, firstDetail);
            
#             wrapper.appendChild(header);
#             wrapper.appendChild(contentArea);
            
#             detailsList.forEach((detail, index) => {
#                 const summary = detail.querySelector('summary');
#                 const titleText = summary ? summary.textContent.trim() : ('Tab ' + (index + 1));
                
#                 const btn = document.createElement('button');
#                 // 初始化：都不加 active
#                 btn.className = 'tab-btn'; 
#                 btn.textContent = titleText;
                
#                 // 搬运内容
#                 const pane = document.createElement('div');
#                 pane.className = 'tab-pane'; // 初始化：都不加 active
#                 pane.appendChild(detail);
#                 detail.open = true;
#                 contentArea.appendChild(pane);

#                 // 点击事件：实现 Toggle 逻辑
#                 btn.onclick = () => {
#                     const isActive = btn.classList.contains('active');
                    
#                     // 1. 重置所有按钮和面板状态
#                     header.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
#                     contentArea.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                    
#                     if (isActive) {
#                         // 2. 如果当前已经是激活的，则说明用户想关闭 -> 收起 Wrapper
#                         wrapper.classList.remove('expanded');
#                     } else {
#                         // 3. 如果当前未激活，则激活它 -> 展开 Wrapper
#                         btn.classList.add('active');
#                         pane.classList.add('active');
#                         wrapper.classList.add('expanded');
#                     }
#                 };
                
#                 header.appendChild(btn);
#             });
#         }

#         if (document.readyState === 'loading') {
#             document.addEventListener('DOMContentLoaded', initTabs);
#         } else {
#             initTabs();
#         }
#     })();
#     </script>
#     """

#     head_assets = katex_assets()
#     html_text = (
#         "<!DOCTYPE html>"
#         "<html><head><meta charset='UTF-8'>"
#         f"<style>{styles}</style>{head_assets}"
#         "</head><body>"
#         f"{body}"
#         f"{tabs_script}"
#         "</body></html>"
#     )
#     return html_text


def render_markdown_content(content: str) -> str:
    if markdown is None:
        raise RuntimeError("Missing 'markdown' package.")
    if not _ARITHMETEX_AVAILABLE:
        raise RuntimeError("Missing 'pymdown-extensions'.")

    extensions = ["extra", "sane_lists", "fenced_code", "tables", "pymdownx.arithmatex"]
    extension_configs = {"pymdownx.arithmatex": {"generic": True}}

    normalized = normalize_math_content(content.lstrip("\ufeff"))
    normalized = normalize_details_markdown(normalized)
    
    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    
    block_elements = md.block_level_elements
    if isinstance(block_elements, set):
        block_elements.update({"details", "summary"})
    else:
        for tag in ("details", "summary"):
            if tag not in block_elements:
                block_elements.append(tag)
                
    body = md.convert(normalized)

    # -----------------------------------------------------------
    # 修改点：CSS 样式大幅增强
    # 目标：让多标签并列时更像一个显眼的 UI 组件，而非简单的文本
    # -----------------------------------------------------------
    styles = """
    body { font-family: 'Times New Roman','Segoe UI',sans-serif; font-size: 16px; line-height: 1.6; color: #333; padding: 16px; background-color: #ffffff; }
    p { margin: 0.6em 0; }
    pre { background: #f6f8fa; padding: 12px; border-radius: 6px; border: 1px solid #d0d7de; overflow-x: auto; }
    code { font-family: 'JetBrains Mono',monospace; font-size: 0.9em; background: rgba(175, 184, 193, 0.2); padding: 0.2em 0.4em; border-radius: 4px; }
    img { max-width: 100%; border-radius: 4px; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; border: 1px solid #d0d7de; }
    th, td { border: 1px solid #d0d7de; padding: 10px 12px; }
    thead th { background: #f6f8fa; font-weight: 600; }
    
    /* 笔记样式 - 保持原样，但也稍微加深一点阴影 */
    details.note-container { 
        background-color: #fff9e6; 
        border-left: 5px solid #e6c200; /* 更深一点的黄色 */
        margin: 15px 0; 
        padding: 12px 16px; 
        border-radius: 0 4px 4px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    details.note-container summary { 
        font-weight: 700; 
        color: #b38600; 
        cursor: pointer; 
        outline: none; 
        font-family: 'Segoe UI', sans-serif;
    }
    .note-content { margin-top: 10px; font-size: 0.95em; color: #4a4a4a; }

    /* Tabs 样式 - 视觉强化版 */
    .tab-wrapper {
        margin: 20px 0;
        border: 1px solid #dcdcdc;
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
        /* 增加阴影，产生悬浮感 */
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        /* 左侧加一个强调条，暗示这是一个交互区域，颜色用科技蓝 */
        border-left: 5px solid #1976d2; 
        transition: all 0.3s ease;
    }
    
    .tab-header {
        display: flex;
        background: #f0f2f5; /* 明显的灰底，区分内容区 */
        border-bottom: 1px solid #dcdcdc;
        overflow-x: auto;
        padding: 4px 4px 0 4px; /* 让按钮看起来像卡片插在槽里 */
    }

    /* 当未展开时，去除底部分割线，让整体看起来像一个完整的圆角条 */
    .tab-wrapper:not(.expanded) .tab-header {
        border-bottom: none;
        background: #f8f9fa; /* 折叠时稍微亮一点 */
    }

    .tab-btn {
        flex: 1;
        padding: 10px 16px;
        margin: 0 2px;
        border: 1px solid transparent;
        border-bottom: none;
        background: none;
        cursor: pointer;
        font-weight: 600;
        font-size: 15px;
        color: #5f6368;
        border-radius: 6px 6px 0 0; /* 按钮上方圆角 */
        transition: all 0.2s;
        min-width: 100px;
        text-align: center;
        position: relative;
    }

    /* 悬停效果：明显的背景变色 */
    .tab-btn:hover {
        background: #e4e6eb;
        color: #202124;
    }
    
    /* 激活状态：变成白色卡片，顶部有高亮条 */
    .tab-btn.active {
        background: #fff;
        color: #1976d2; /* 激活文字变蓝 */
        border-color: #dcdcdc; /* 加上边框 */
        border-bottom-color: #fff; /* 遮住 header 的底边框，实现融合效果 */
        border-top: 3px solid #1976d2; /* 顶部高亮条 */
        margin-bottom: -1px; /* 往下压像素，覆盖分割线 */
        box-shadow: 0 -2px 5px rgba(0,0,0,0.02);
    }
    
    /* 内容区域 */
    .tab-content-area {
        background: #fff;
        padding: 24px;
        display: none; 
        border-top: 1px solid transparent; /* 占位 */
    }
    
    .tab-wrapper.expanded .tab-content-area {
        display: block;
    }

    .tab-pane { display: none; animation: fadeIn 0.3s ease-in-out; }
    .tab-pane.active { display: block; }
    
    @keyframes fadeIn { 
        from { opacity: 0; transform: translateY(5px); } 
        to { opacity: 1; transform: translateY(0); } 
    }
    
    /* 隐藏原 Note 的一些样式，使其融入 Tab */
    .tab-pane > details > summary { display: none; }
    .tab-pane > details.note-container { 
        border: none; 
        margin: 0; 
        padding: 0; 
        background: none; 
        box-shadow: none; 
        border-left: none; /* 去除 Note 内部的左边框，因为外层 Tab 已经有了 */
    }
    """

    # JS 逻辑保持不变 (因为逻辑本身是正确的，只需要 CSS 配合)
    tabs_script = """
    <script>
    (function() {
        function initTabs() {
            const allDetails = Array.from(document.querySelectorAll('details'));
            const processed = new Set();
            
            allDetails.forEach(detail => {
                if (processed.has(detail)) return;
                
                let siblings = [detail];
                let next = detail.nextElementSibling;
                
                while (next) {
                    if (next.tagName && next.tagName.toLowerCase() === 'details') {
                        siblings.push(next);
                        processed.add(next);
                        next = next.nextElementSibling;
                    } else if (next.nodeType === 3 && !next.textContent.trim()) {
                        next = next.nextSibling;
                    } else {
                        break;
                    }
                }
                
                processed.add(detail);
                
                if (siblings.length >= 2) {
                    createTabGroup(siblings);
                }
            });
        }

        function createTabGroup(detailsList) {
            const wrapper = document.createElement('div');
            wrapper.className = 'tab-wrapper'; 
            
            const header = document.createElement('div');
            header.className = 'tab-header';
            
            const contentArea = document.createElement('div');
            contentArea.className = 'tab-content-area';
            
            const firstDetail = detailsList[0];
            firstDetail.parentNode.insertBefore(wrapper, firstDetail);
            
            wrapper.appendChild(header);
            wrapper.appendChild(contentArea);
            
            detailsList.forEach((detail, index) => {
                const summary = detail.querySelector('summary');
                const titleText = summary ? summary.textContent.trim() : ('Tab ' + (index + 1));
                
                const btn = document.createElement('button');
                btn.className = 'tab-btn'; 
                btn.textContent = titleText;
                
                const pane = document.createElement('div');
                pane.className = 'tab-pane';
                pane.appendChild(detail);
                detail.open = true;
                contentArea.appendChild(pane);

                btn.onclick = () => {
                    const isActive = btn.classList.contains('active');
                    
                    header.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    contentArea.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                    
                    if (isActive) {
                        wrapper.classList.remove('expanded');
                    } else {
                        btn.classList.add('active');
                        pane.classList.add('active');
                        wrapper.classList.add('expanded');
                    }
                };
                
                header.appendChild(btn);
            });
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initTabs);
        } else {
            initTabs();
        }
    })();
    </script>
    """

    head_assets = katex_assets()
    html_text = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='UTF-8'>"
        f"<style>{styles}</style>{head_assets}"
        "</head><body>"
        f"{body}"
        f"{tabs_script}"
        "</body></html>"
    )
    return html_text


__all__ = [
    "katex_assets",
    "normalize_details_attrs",
    "normalize_details_markdown",
    "normalize_math_content",
    "normalize_note_content_divs",
    "render_markdown_content",
]