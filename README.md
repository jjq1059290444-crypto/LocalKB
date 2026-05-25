# LocalKB — 本地 RAG 知识库

一个 Windows 桌面端本地 RAG（检索增强生成）知识库应用。拖入文档，用自然语言提问，数据全程不出本机。

## 功能

| 模块 | 说明 |
|------|------|
| **文档索引** | 支持 `.md` `.txt` `.pdf` `.docx` `.pptx` `.ppt`，自动分块、去重、嵌入 |
| **切片策略** | 结构化（按 H2 标题） / 语义相似度 / 迟交互分块 |
| **混合检索** | Qdrant 内置 RRF 融合稠密向量 + 稀疏词法权重 |
| **HyDE 查询扩展** | 可选：先生成假设性答案再检索，提升命中率 |
| **重排序** | 可选：Cross-encoder 对召回结果精排（BGE-Reranker） |
| **单轮 / 多轮对话** | 默认单轮，可在输入框切换多轮；设置页面可改默认模式 |
| **流式输出** | 答案实时逐字显示 |
| **参考来源** | 显示文档名、章节标题、匹配度分数 |
| **历史记录** | 问答记录本地存储，可搜索回看 |
| **首次引导** | 启动即进入配置向导，无需手动编辑配置文件 |
| **后台初始化** | 窗口秒开，向量库 + 模型加载在后台线程并行执行，启动不卡顿 |

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

### 文档预处理建议

对于 **PDF 扫描件、复杂排版、含表格/公式的文档**，直接拖入的解析质量有限。建议先用 [MinerU](https://github.com/opendatalab/MinerU) 预处理：

```bash
# 1. 用 MinerU 将 PDF 转为高质量 Markdown
mineru -p /path/to/pdf -o /path/to/output

# 2. MinerU 输出的 .md 文件按章节/主题人工分块（每个 chunk 一个文件），
#    放入 data/docs/ 目录

# 3. 打开 LocalKB，切到知识库管理，点击「扫描新文件」或拖入
```

MinerU 的优势：自动识别表格、公式（LaTeX）、页眉页脚过滤、阅读顺序还原，远优于 PyMuPDF 的原始提取。对于**纯文本 Markdown / txt 文档**则直接拖入即可，系统内置的结构化分块器已足够。

## 嵌入模型

| 模型 | 维度 | 语言 | 大小 | 稀疏向量 |
|------|------|------|------|----------|
| BGE-small-zh-v1.5 | 512 | 中文 | ~95 MB | 字 n-gram |
| all-MiniLM-L6-v2 | 384 | 英文 | ~90 MB | 字 n-gram |
| BGE-M3 | 1024 | 多语言 | ~2 GB | 字 n-gram（备选 FlagEmbedding 原生） |

- BGE-small-zh-v1.5 为内置模型（随仓库分发），启动即可用。
- BGE-M3 和 all-MiniLM-L6-v2 需在设置页切换后自动下载（从 ModelScope，国内速度快）。
- 稠密向量通过 **SentenceTransformer** 加载。
- 稀疏向量默认使用**纯 Python 字符 n-gram 哈希**（无 C 扩展依赖，稳定可靠）。若环境中安装了 FlagEmbedding 则自动切换为 BGE-M3 原生词法权重。

## 技术栈

| 组件 | 技术 |
|------|------|
| 界面 | PySide6 (Qt for Python) |
| 向量数据库 | Qdrant Embedded（Rust + RocksDB） |
| 稠密嵌入 | SentenceTransformer |
| 稀疏嵌入 | 字符 n-gram 哈希（纯 Python，无外部依赖） |
| 检索融合 | Qdrant 内置 RRF |
| 重排序 | BGE-Reranker-v2-m3（Cross-encoder，需 FlagEmbedding） |
| LLM 客户端 | OpenAI 兼容 API（DeepSeek / OpenAI / Ollama 等） |
| 文档解析 | python-docx, python-pptx, PyMuPDF (fitz) |
| Markdown 渲染 | 自研 Qt rich-text 渲染器（纯 Python） |
| 国际化 | 自研 i18n 管理器（zh / en） |
| 后台任务 | QThread Worker 模式（索引、问答、初始化、模型预热） |
| 打包 | 未打包，源码运行（`启动.bat`） |

## 项目结构

```
LocalKB/
├── core/                  # 核心逻辑，无 GUI 依赖
│   ├── indexing/          # 解析器、分块器、嵌入、去重
│   │   ├── chunkers/      # 结构化 / 语义 / 迟交互分块
│   │   ├── embedder.py    # 稠密 + 稀疏嵌入（ST + n-gram）
│   │   └── sparse_embedder.py  # 纯 Python 稀疏向量生成
│   ├── retrieval/         # 向量库、混合检索、重排序
│   │   ├── vector_store.py     # Qdrant Embedded 封装
│   │   └── hybrid.py           # 稠密 + 稀疏 RRF 融合
│   └── qa/                # LLM 客户端、提示词、HyDE、会话
├── config/                # 配置管理、模型预设
├── desktop_app/           # PySide6 GUI
│   ├── pages/             # 对话、知识库、设置、API 配置、向导
│   ├── widgets/           # 聊天气泡、输入框、来源面板、历史列表
│   ├── workers/           # QThread 后台任务
│   │   ├── startup_worker.py   # 向量库 + QA 引擎初始化
│   │   ├── warmup_worker.py    # 嵌入模型预热
│   │   ├── qa_worker.py        # 流式问答
│   │   └── index_worker.py     # 文档索引
│   └── utils/             # i18n、Markdown 渲染、模型下载
├── data/                  # 运行时数据（不入 git）
├── models/                # 嵌入模型文件（内置小模型入 git，其余不入）
├── tools/                 # 辅助脚本
├── 启动.bat               # 一键启动器
└── setup.bat              # 环境安装脚本
```

## License

MIT © LocalKB Contributors
