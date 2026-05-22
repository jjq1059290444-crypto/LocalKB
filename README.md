# LocalKB — 本地 RAG 知识库

一个桌面端本地 RAG（检索增强生成）知识库应用。拖入文档，用自然语言提问。

## 功能特点

- **本地 RAG**：支持 `.md` / `.txt` / `.pdf` / `.docx` / `.pptx` 文档，数据不上传
- **混合检索**：Qdrant 向量搜索 + BM25 关键词搜索，RRF 融合
- **多供应商 LLM**：DeepSeek、OpenAI 及任意兼容接口
- **流式输出**：答案实时逐字显示
- **参考来源**：展示引用的文档和片段
- **历史搜索**：问答记录保存在本地，可搜索
- **首次引导**：启动即进入配置向导，无需手动编辑配置文件
- **MIT 开源**

## 环境要求

- Windows 10/11（Linux / macOS 也可运行）
- Python 3.10+
- [DeepSeek](https://platform.deepseek.com/) 或 [OpenAI](https://platform.openai.com/) 的 API Key

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/jjq1059290444-crypto/LocalKB.git
cd LocalKB

# 2. 双击启动（首次自动安装依赖）
启动.bat
```

首次启动会自动创建虚拟环境、安装依赖，然后进入引导页面。

## 使用说明

1. **引导设置** → 选择语言 → 配置 API → 选择嵌入模型 → 完成
2. **知识库管理** → 拖入文档文件
3. **对话问答** → 用自然语言提问

## 技术栈

| 组件 | 技术 |
|------|------|
| 界面 | PySide6 (Qt for Python) |
| 向量数据库 | Qdrant (Embedded) |
| 嵌入模型 | BGE-small-zh / BGE-M3 / all-MiniLM |
| 关键词搜索 | BM25 |
| 重排序 | BGE-Reranker (可选) |
| LLM | OpenAI 兼容 API (DeepSeek / OpenAI / 自定义) |

## 项目结构

```
LocalKB/
├── core/                # 核心逻辑，无 GUI 依赖
│   ├── indexing/        # 解析器、分块器、嵌入、去重
│   │   └── chunkers/    # 结构化 & 语义分块
│   ├── retrieval/       # 向量库、BM25、混合检索、重排序
│   └── qa/              # LLM 客户端、提示词、QA 链
├── config/              # 配置管理、供应商预设、模型注册
├── desktop_app/         # PySide6 GUI
│   ├── pages/           # 对话、知识库、设置、API 配置、关于
│   ├── widgets/         # 聊天气泡、输入框、来源面板
│   ├── workers/         # QThread 后台任务
│   └── utils/           # i18n、Markdown 渲染
├── data/                # 运行时数据（不入 git）
├── docs/                # 用户文档
├── 启动.bat             # 一键启动器
└── setup.bat            # 环境安装脚本
```

## 嵌入模型说明

| 模型 | 维度 | 语言 | 大小 |
|------|------|------|------|
| BGE-small-zh-v1.5 | 512 | 中文 | ~95 MB |
| all-MiniLM-L6-v2 | 384 | 英文 | ~90 MB |
| BGE-M3 | 1024 | 多语言 | ~4.5 GB |

首次启动可选择并自动从 ModelScope 下载（国内速度快）。

## License

MIT © LocalKB Contributors
