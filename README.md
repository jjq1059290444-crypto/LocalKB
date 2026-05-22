# LocalKB — 本地 RAG 知识库

一个 Windows 桌面端本地 RAG（检索增强生成）知识库应用。拖入文档，用自然语言提问，数据全程不出本机。

## 功能

| 模块 | 说明 |
|------|------|
| **文档索引** | 支持 `.md` `.txt` `.pdf` `.docx` `.pptx` `.ppt`，自动分块、去重、嵌入 |
| **切片策略** | 结构化（按 H2 标题） / 语义相似度 / 迟交互分块（BGE-M3） |
| **混合检索** | Qdrant 内置 RRF 融合稠密向量 + 稀疏词法权重（BGE-M3 原生） |
| **HyDE 查询扩展** | 可选：先生成假设性答案再检索，提升命中率 |
| **重排序** | 可选：Cross-encoder 对召回结果精排（BGE-Reranker） |
| **单轮 / 多轮对话** | 默认单轮，可在输入框切换多轮；设置页面可改默认模式 |
| **流式输出** | 答案实时逐字显示 |
| **参考来源** | 显示文档名、章节标题、匹配度分数、内容预览 |
| **历史记录** | 问答记录本地存储，可搜索回看 |
| **首次引导** | 启动即进入配置向导，无需手动编辑配置文件 |
| **控制台调试日志** | cmd 启动时输出完整流水线耗时（HyDE → 检索 → LLM） |

## 系统要求

- **操作系统**：Windows 10 / 11（仅支持 Windows）
- **Python**：3.10+
- **API Key**：DeepSeek / OpenAI / 或任意 OpenAI 兼容接口

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/zhuzhu-unnn/LocalKB.git
cd LocalKB

# 2. 双击启动（首次自动创建虚拟环境并安装依赖）
启动.bat
```

首次启动会自动创建虚拟环境、安装依赖，然后进入引导页面。

## 使用流程

1. **引导设置**：选择语言 → 配置 API Key / Base URL / 模型名 → 选择嵌入模型 → 完成
2. **知识库管理**：拖入文档文件，系统自动切片、嵌入、存入向量库
3. **设置页**：调整检索条数、温度、嵌入模型、切片策略、对话模式等
4. **对话问答**：用自然语言提问，实时获得带来源标注的回答

## 嵌入模型

| 模型 | 维度 | 语言 | 大小 | 稀疏向量 |
|------|------|------|------|----------|
| BGE-small-zh-v1.5 | 512 | 中文 | ~95 MB | — |
| all-MiniLM-L6-v2 | 384 | 英文 | ~90 MB | — |
| BGE-M3 | 1024 | 多语言 | ~2 GB | ✅ 词法权重 |

- BGE-small-zh-v1.5 为内置模型（随仓库分发），启动即可用。
- BGE-M3 和 all-MiniLM-L6-v2 需在设置页切换后自动下载（从 ModelScope，国内速度快）。
- BGE-M3 同时输出稠密和稀疏向量，原生支持混合检索，但首次加载约 15-30 秒。

## 技术栈

| 组件 | 技术 |
|------|------|
| 界面 | PySide6 (Qt for Python) |
| 向量数据库 | Qdrant Embedded（Rust + RocksDB） |
| 稠密嵌入 | SentenceTransformer / FlagEmbedding |
| 稀疏嵌入 | BGE-M3 词法权重（FlagEmbedding） |
| 检索融合 | Qdrant 内置 RRF |
| 重排序 | BGE-Reranker-v2-m3（Cross-encoder） |
| LLM 客户端 | OpenAI 兼容 API（DeepSeek / OpenAI / Ollama 等） |

## 项目结构

```
LocalKB/
├── core/                # 核心逻辑，无 GUI 依赖
│   ├── indexing/        # 解析器、分块器、嵌入、去重
│   │   └── chunkers/    # 结构化 / 语义 / 迟交互分块
│   ├── retrieval/       # 向量库、混合检索、重排序、迁移
│   └── qa/              # LLM 客户端、提示词、HyDE、会话
├── config/              # 配置管理、模型预设
├── desktop_app/         # PySide6 GUI
│   ├── pages/           # 对话、知识库、设置、API 配置、向导
│   ├── widgets/         # 聊天气泡、输入框、来源面板、历史列表
│   ├── workers/         # QThread 后台任务（索引、问答）
│   └── utils/           # i18n、Markdown 渲染、模型下载
├── data/                # 运行时数据（不入 git）
├── models/              # 嵌入模型文件（内置小模型入 git，其余不入）
├── docs/                # 架构图文档
├── 启动.bat             # 一键启动器
└── setup.bat            # 环境安装脚本
```

## License

MIT © LocalKB Contributors
