# Exocortex: 深度阅读与知识内化的多智能体工作流

> **并不是又一个 "Chat with PDF" 工具，而是一个外挂的认知皮层。**

## 📖 前言 (Introduction)

在传统的 LLM 辅助阅读场景中，我们经常面临着“碎片化交互”的困境：网页端的线性对话窗口不仅难以维持长文档的上下文（Context），更难以将 AI 产生的洞见与原文建立结构化的持久联系。当阅读一篇充满公式和图表的理工科论文时，单纯的 OCR 文本丢失了排版语义，而反复的上下文翻阅则打断了心流。

**Exocortex** 正是为了解决这一痛点而生。

这是一个基于 **[Codex](https://github.com/openai/codex)** 和 **[Gemini-CLI](https://github.com/google-gemini/gemini-cli)** 构建的通用多智能体（Multi-Agent）工作流系统。不同于传统应用将逻辑硬编码到 LLM 调用层面，Exocortex 的工作流编排粒度细化到 **Agent** 层级。通过 Prompt Engineering，利用智能体具备的规划能力，协同完成从全局解析到局部精读的认知闭环。

### 核心设计哲学

Exocortex 的工作流模拟了人类专家深度学习的四个认知阶段：

1. **全局锚定 (Global Contextualization)**：
* **Global Parsing Agent** 并不直接服务于用户，而是作为系统的“潜意识”。它预先扫描论文，提取背景、核心概念及公式定义，生成一份结构化的“全局信息”。这份信息作为后续所有 Agent 的共享上下文（Shared Context），确保了局部讲解不会脱离整体逻辑。


2. **视觉感知与聚焦 (Visual Attention mechanism)**：
* 摒弃了有损的 OCR 方案，Exocortex 引入了 **Block (区块)** 和 **Group (组)** 的概念。用户框选的关注区域（Focus on content）被作为**图像**直接传递给 **Teacher Agent**。利用现代模型的原生多模态能力，保留了公式、图表在原文中的空间布局信息，从而生成具有全局视角的精准讲解。


3. **苏格拉底式解惑 (Interactive Clarification)**：
* 当用户对讲解产生疑问时，**Resolver Agent** 介入。它基于选中的特定内容和用户的具体困惑，开展多轮深度的解惑对话。得益于持久化的全局信息，答复不再是通用的废话，而是紧扣论文逻辑的精准剖析。


4. **知识结晶与持久化 (Integration & Persistence)**：
* 阅读的终点不是对话的结束，而是知识的沉淀。**Integrator Agent** 会自动分析解惑过程中的对话记录，将其提炼为精炼的笔记，并**折叠插入**到原文对应讲解的后方。这种“原位（In-place）”的知识管理方式，让用户的每一次交互都成为构建个人知识库的一块基石。



### 为什么选择 Exocortex？

* **多智能体协同**：相比单一 LLM，分工明确的 Agent 组（解析、教学、答疑、整合）不仅提升了任务的专注度，更大幅提高了输出质量。
* **结构化上下文**：通过右侧原文 PDF 与左侧 AI 生成内容的实时映射，彻底告别了在聊天记录中“大海捞针”的体验。
* **视觉优先**：利用多模态能力处理数学公式和复杂图表，避免了 LaTeX 转换错误带来的理解偏差。

Exocortex 不仅仅是一个阅读器，它是你大脑的延伸，帮你把复杂的外部资料，结构化地“吃”进脑子里。

---
## 快速开始

### 1.gemini-cli与codex的准备
* 确保 **[Codex](https://github.com/openai/codex)** 和 **[Gemini-CLI](https://github.com/google-gemini/gemini-cli)** 在你的系统环境可以正常调用。

### 2.下载[Exocortex](https://github.com/ximiwu/Exocortex/releases)

## 使用教程

