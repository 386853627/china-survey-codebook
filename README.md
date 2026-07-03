# 中国社会调查问卷资料库

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

面向 AI Agent 的结构化社会调查问卷资料库。当前覆盖 **CGSS（中国综合社会调查）** 全部波次，将 PDF 问卷转换为 SQLite 结构化数据库，支持自然语言搜索与精确变量查询。

> **注意**：本仓库仅包含变量元数据（变量名、题干、选项编码），不包含原始问卷PDF及调查数据。原始问卷和数据请从 [CGSS 官网](http://cgss.ruc.edu.cn/) 获取。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入 API 密钥：

```bash
cp .env.example .env
```

```
MINERU_API_KEY=your_mineru_key_here    # MinerU PDF 解析
LLM_API_KEY=your_llm_api_key_here       # 结构化提取（兼容 OpenAI API）
LLM_BASE_URL=https://api.deepseek.com/v1  # LLM 端点
LLM_MODEL=deepseek-chat                  # 模型名称
```

### 3. 三步建库

```bash
# Step 1: PDF → Markdown（将问卷 PDF 放入 data/pdf/ 后运行）
python scripts/step1_pdf_to_md.py

# Step 2: Markdown → 结构化 JSON
python scripts/step2_md_to_json.py

# Step 3: JSON → SQLite
python scripts/step3_json_to_db.py
```

### 4. 开始查询

```bash
# 全文搜索
python scripts/query.py search "生育意愿"

# 精确查变量
python scripts/query.py var --wave 2017 --var a1

# 列出所有波次
python scripts/query.py waves

# 列出某波次模块
python scripts/query.py sections --wave 2017

# 列出某模块全部变量
python scripts/query.py module --wave 2017 --section "A部分"

# 数据库统计
python scripts/query.py stats

# 导出 CSV
python scripts/query.py export --wave 2017 -o cgss2017.csv
```

## 数据库 Schema

```
surveys（调查元信息）
├── waves（波次）
│   └── variables（变量）── value_labels（值标签）
```

### variables 核心字段

| 字段 | 说明 |
|------|------|
| var_name | 变量名（a1, a2, a3a...） |
| question_text | 题干 |
| question_type | 单选题/多选题/填空题/开放题/量表题 |
| section | 所属模块 |
| universe | 适用人群 |
| skip_pattern | 跳转逻辑 |
| interviewer_note | 访题说明 |
| value_labels | 选项编码（值=标签） |

## 覆盖范围

| 调查 | 年份 | 状态 |
|------|------|------|
| CGSS | 2003, 2005, 2006, 2008, 2010, 2011, 2012, 2013, 2015, 2017, 2018, 2021 | 首批 |
| CFPS | 2010-2022 | 后续 |
| CLDS | 后续 | 后续 |
| CHARLS | 后续 | 后续 |

## 项目结构

```
├── PLAN.md              # 完整建设方案
├── schema.sql           # 数据库建表 SQL
├── requirements.txt     # Python 依赖
├── data/
│   ├── pdf/             # 原始问卷 PDF（不提交）
│   ├── markdown/        # 中间 Markdown
│   ├── json/            # 中间 JSON
│   └── cgss.db          # SQLite 数据库
├── scripts/
│   ├── step1_pdf_to_md.py
│   ├── step2_md_to_json.py
│   ├── step3_json_to_db.py
│   └── query.py         # AI Agent 查询入口
├── prompts/
│   └── extraction.md    # LLM 提取 Prompt
└── tests/
    └── test_queries.py
```

## License

MIT
