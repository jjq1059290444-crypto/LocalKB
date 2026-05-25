# LocalKB 架构文档

## 1. 整体概览

```
┌─────────────────────────────────────────────────────────┐
│                      desktop_app                        │
│  ┌───────────┐  ┌───────────┐  ┌────────────────────┐ │
│  │  pages/   │  │ widgets/  │  │ workers/ (QThread)  │ │
│  │  5 个页面  │  │ 可复用控件  │  │  后台任务不卡 UI    │ │
│  └─────┬─────┘  └─────┬─────┘  └─────────┬──────────┘ │
│        │              │                  │             │
├────────┼──────────────┼──────────────────┼─────────────┤
│        ▼              ▼                  ▼             │
│                        core                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ indexing │  │  retrieval   │  │       qa         │ │
│  │ 文档索引  │  │  向量检索     │  │   问答流水线      │ │
│  └──────────┘  └──────────────┘  └──────────────────┘ │
│                                                         │
│  ┌──────────┐                                          │
│  │  config  │  配置管理 + API 预设                       │
│  └──────────┘                                          │
│                                                         │
│  ┌──────────┐                                          │
│  │  data/   │  Qdrant 向量库 + 切片缓存 + 问答历史        │
│  └──────────┘                                          │
└─────────────────────────────────────────────────────────┘
```

三层架构：

| 层 | 目录 | 职责 | 依赖 |
|----|------|------|------|
| 界面层 | `desktop_app/` | PySide6 GUI，用户交互 | core |
| 核心层 | `core/` | 纯 Python 业务逻辑，不依赖 GUI | 无 |
| 数据层 | `data/` | Qdrant 嵌入式数据库 + 文件缓存 | core |

---

## 2. 完整问答流水线

```
用户输入 "开关节点"
        │
        ▼
┌─── chat_page.py ──────────────────────────────────┐
│  1. 主线程预热模型 (warmup_model)                   │
│  2. 创建 QAWorker 丢到后台线程                       │
└────────────────────┬───────────────────────────────┘
                     │  QThread.run()
                     ▼
┌─── qa_worker.py ─────────────────────────────────┐
│                                                    │
│  ┌─ HyDE 查询扩展 ─────────────────────────────┐  │
│  │ hyde.py                                    │  │
│  │   "开关节点" → LLM → 假设答案(246字)         │  │
│  │   "开关节点是电力电子变换器中连接功率         │  │
│  │    开关器件、电感和续流二极管的关键节点…"      │  │
│  └────────────────────────────────────────────┘  │
│                                                    │
│  ┌─ 嵌入查询 ─────────────────────────────────┐   │
│  │ embedder.py                                │   │
│  │   假设答案 → BGE-M3 → 1024维稠密向量         │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  ┌─ 混合检索 ─────────────────────────────────┐   │
│  │ hybrid.py + vector_store.py                │   │
│  │   稠密向量 → Qdrant cosine 检索 → Top 50    │   │
│  │   (若启用重排序: Cross-encoder 精排 → 9条)  │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  ┌─ 组装 Prompt ─────────────────────────────┐   │
│  │ prompt.py                                  │   │
│  │   系统提示词                                │   │
│  │   + 历史对话 (多轮模式时)                     │   │
│  │   + 9 个检索片段 (带来源标注)                 │   │
│  │   + 用户问题                                │   │
│  │   = ~3464 字符                              │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  ┌─ LLM 流式生成 ────────────────────────────┐   │
│  │ openai_client.py                           │   │
│  │   prompt → DeepSeek API → 逐 token 流式返回 │   │
│  │   每个 token 通过 Signal 发回主线程          │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  ┌─ 记录历史 ────────────────────────────────┐   │
│  │ session.py + qa_history.jsonl              │   │
│  └────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────┘
                     │  token_signal / finished_signal
                     ▼
┌─── chat_page.py (主线程) ─────────────────────────┐
│  _on_token()  → 逐字追加到聊天气泡                    │
│  _on_answer() → 渲染 Markdown → 显示来源面板          │
└────────────────────────────────────────────────────┘
```

---

## 3. 各模块详解

### 3.1 core/indexing/ — 文档索引管道

**数据流**：原始文件 → 解析 → 分块 → 嵌入 → 入库

```
raw_docs/xxx.pdf
  │
  ▼
parser.py ──► parsers/pdf_parser.py   (PyMuPDF 解析)
                parsers/docx_parser.py (python-docx)
                parsers/ppt_parser.py  (python-pptx)
                parsers/text_parser.py (纯文本 .md/.txt)
  │ 输出: { source_file, content, char_count, md5, ... }
  ▼
md5_dedup.py
  │ 检查 registry.json，已处理过的文件跳过
  ▼
chunker.py ──► chunkers/structural_chunker.py  (按 H2 标题切)
                chunkers/semantic_chunker.py    (按语义相似度切)
                chunkers/late_chunker.py        (迟交互分块, 需 BGE-M3)
  │ 输出: [{ source_file, chunk_index, content, md5 }, ...]
  ▼
embedder.py
  │ bge-small-zh-v1.5: SentenceTransformer → 512维
  │ BGE-M3:            SentenceTransformer → 1024维 (不含稀疏)
  ▼
vector_store.py
  │ QdrantClient(path=data/vector_db) → upsert
  ▼
data/vector_db/  (RocksDB)
```

**embedder.py 加载路径**：
```
supports_sparse(model_name)?
  ├─ True  → _load_flag()  → FlagEmbedding BGEM3FlagModel (当前未安装)
  └─ False → _load_st()    → SentenceTransformer
```

### 3.2 core/retrieval/ — 检索系统

| 文件 | 功能 |
|------|------|
| `vector_store.py` | Qdrant 嵌入式向量库封装。支持稠密向量 + 稀疏向量双索引 |
| `hybrid.py` | 混合检索调度器。稠密检索 + (可选)稀疏检索 → 融合排序 |
| `bm25.py` | BM25 关键词检索索引 (备用) |
| `reranker.py` | Cross-encoder 重排序。需 FlagEmbedding (当前未安装, 自动降级) |

**检索流程**：
```
查询向量
  ├─ dense: Qdrant cosine search → 初排 Top-K
  ├─ sparse: Qdrant dot-product search (仅 BGE-M3)
  └─ RRF 融合 (Qdrant 内置)
       │
       ▼
  (可选) reranker.py
       │ Cross-encoder [query, doc] 逐对打分
       │ 按新分数重排
       ▼
  返回 Top-K 结果
```

### 3.3 core/qa/ — 问答流水线

| 文件 | 功能 |
|------|------|
| `base.py` | LLM 客户端抽象基类 |
| `openai_client.py` | OpenAI 兼容客户端 (DeepSeek/OpenAI/Ollama 等) |
| `chain.py` | 问答链调度：检索 → prompt → LLM 流式输出 |
| `prompt.py` | Prompt 模板：系统提示词 + 检索片段 + 历史 + 问题 |
| `hyde.py` | HyDE 查询扩展：LLM 先编假设答案再检索 (提升 15-30% 召回) |
| `session.py` | 多轮对话会话管理 (最多保留 N 轮历史) |

### 3.4 desktop_app/ — 桌面 GUI

```
启动流程:
main.py
  ├─ 加载 config.json
  ├─ 首次启动 → 向导页 (wizard_page.py)
  ├─ 初始化 VectorStore (Qdrant)
  ├─ 初始化 QAChain (检索器 + LLM 客户端)
  ├─ 显示 MainWindow
  └─ 进入 Qt 事件循环
```

#### 页面 (pages/)

| 页面 | 类 | 功能 |
|------|-----|------|
| 对话 | `ChatPage` | 聊天气泡 + 输入框 + 来源面板 + 历史列表 |
| 知识库 | `KBManagePage` | 拖入文档 → 索引 → 查看切片列表 |
| 设置 | `SettingsPage` | 检索条数、温度、嵌入模型、切片策略、对话模式 |
| API | `APIConfigPage` | API Key / Base URL / 模型名 配置 |
| 关于 | `AboutPage` | 版本信息 |
| 向导 | `WizardPage` | 首次引导：语言 → API → 模型 → 完成 |

#### 控件 (widgets/)

| 控件 | 功能 |
|------|------|
| `chat_bubble.py` | 聊天气泡，区分用户/AI，支持 Markdown 渲染 |
| `chat_input.py` | 输入框 + 发送按钮 + 单轮/多轮切换 |
| `source_panel.py` | 来源面板，显示检索片段及来源文件 |
| `history_list.py` | 问答历史列表，可搜索回看 |

#### 后台线程 (workers/)

| Worker | 父类 | 功能 |
|--------|------|------|
| `QAWorker` | QThread | 问答链流水线 (HyDE→检索→LLM流式)，通过 Signal 传回 UI |
| `IndexWorker` | QThread | 文档索引 (解析→分块→嵌入→入库)，可暂停/取消 |
| `ConfigWorker` | QThread | API 连通性验证 |
| `ModelDownloadWorker` | QThread | 从 ModelScope 下载模型，带进度条 |
| `QdrantImportWorker` | QThread | 直接导入已有的 Qdrant 数据库 |

#### 工具 (utils/)

| 文件 | 功能 |
|------|------|
| `i18n.py` | 中英文切换 (zh.json / en.json)，带信号通知 |
| `markdown_renderer.py` | Markdown → HTML 渲染 |
| `model_download.py` | 从 ModelScope 下载嵌入模型到本地 |

---

## 4. 数据存储

```
data/
├── vector_db/          ← Qdrant 嵌入式数据库 (Rust + RocksDB)
│   ├── .lock           ← 进程锁 (崩溃后需手动删除)
│   ├── meta.json       ← 集合定义
│   └── collection/     ← 向量数据 + 元数据
├── chunks/
│   ├── all_chunks.jsonl  ← 全量切片缓存
│   └── summary.json      ← 切片统计
├── docs/               ← 上传的原始文档副本
└── qa_history.jsonl    ← 问答历史 (每行一个 JSON)
```

配置文件：`C:\Users\<用户名>\AppData\Roaming\LocalKB\config.json`

```json
{
  "version": 1,
  "api_base": "https://api.deepseek.com",
  "api_key": "sk-xxx",
  "model": "deepseek-chat",
  "embed_model": "bge-small-zh-v1.5",
  "temperature": 0.3,
  "top_k": 9,
  "use_reranker": false,
  "hyde_enabled": true,
  "chunking_strategy": "structural",
  "conversation_mode": "single"
}
```

---

## 5. 嵌入模型

| 模型名 | 维度 | 大小 | 加载时间 | 稀疏向量 | 说明 |
|--------|------|------|----------|----------|------|
| bge-small-zh-v1.5 | 512 | ~95MB | 0.2s | 无 | 中文优化，内置 |
| BGE-M3 | 1024 | ~2GB | 2.6s | 需要 FlagEmbedding | 多语言，质量最高 |
| all-MiniLM-L6-v2 | 384 | ~90MB | ~1s | 无 | 英文优化 |

BGE-M3 当前通过 SentenceTransformer 加载 (纯稠密模式)，稀疏向量功能需要 FlagEmbedding 库。

---

## 6. 线程模型

```
主线程 (Main Thread)              后台线程 (QThread)
─────────────────────             ───────────────────
GUI 事件循环                       QAWorker.run()
  │                                   │
  ├─ 点击发送                         ├─ HyDE (调 LLM)
  │   │                               ├─ 嵌入查询
  │   ├─ warmup_model() ── 同步 ────► │  (加载模型到内存)
  │   │                               │
  │   ├─ 创建 QAWorker                 ├─ 向量检索
  │   └─ worker.start() ───── 异步 ─► │  (查 Qdrant)
  │       │                           │
  │       ├─ token_signal  ◄─ Signal ─┤─ LLM 流式
  │       │   → _on_token()           │  逐 token 发出
  │       │   → 更新气泡               │
  │       │                           │
  │       └─ finished_signal ◄────────┤─ 汇总结果
  │           → _on_answer()          │
  │           → 渲染 + 来源 + 历史      │
```

**关键设计**：PyTorch 模型加载不是线程安全的，必须在主线程加载 (`warmup_model`)。加载完后，模型对象可安全地在子线程只用。

---

## 7. 依赖清单

```
核心:
  PySide6>=6.5          桌面 GUI
  openai>=1.0           LLM API 客户端
  qdrant-client>=1.9    向量数据库
  sentence-transformers  稠密嵌入模型
  torch                 PyTorch (CPU 版)

文档处理:
  pymupdf>=1.23         PDF 解析
  python-docx>=0.8      Word 解析
  python-pptx>=0.6      PPT 解析

辅助:
  rich                  终端美化输出
  markdown              Markdown 渲染
  modelscope            模型下载 (国内源)
  python-dotenv         环境变量
```
