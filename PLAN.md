# CGSS 问卷资料库（SQLite）建设方案

## 1. 项目概述

**目标**：从 CGSS 全部波次（2003-2023）PDF 问卷出发，构建 SQLite 结构化数据库，通过 Python 脚本让 AI agent 自由查询变量。

**选型**：方案 A — SQLite 结构化数据库 + FTS5 全文搜索。

**覆盖范围**：首批 CGSS 全部波次（2003、2005、2006、2008、2010、2011、2012、2013、2015、2017、2018、2021），后续扩展 CFPS / CLDS / CHARLS。

---

## 2. 数据库 Schema

### 2.1 表结构

```sql
-- 调查元信息
CREATE TABLE surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,       -- CGSS
    full_name TEXT,                  -- 中国综合社会调查 (Chinese General Social Survey)
    name_cn TEXT,                    -- 中国综合社会调查
    institution TEXT,                -- 中国人民大学中国调查与数据中心
    website TEXT,                    -- http://cgss.ruc.edu.cn/
    description TEXT
);

-- 波次
CREATE TABLE waves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER NOT NULL REFERENCES surveys(id),
    year INTEGER NOT NULL,
    sample_size INTEGER,
    questionnaire_type TEXT,         -- 家庭问卷 / 个人问卷 / 村居问卷
    source_file TEXT,                -- 原始PDF/MD文件名
    notes TEXT,
    UNIQUE(survey_id, year, questionnaire_type)
);

-- 变量（核心表）
CREATE TABLE variables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wave_id INTEGER NOT NULL REFERENCES waves(id),
    var_name TEXT NOT NULL,          -- a1, a2, a3a
    section TEXT,                    -- A部分：核心模块
    question_number TEXT,            -- A1, A1a, A1b
    question_text TEXT NOT NULL,     -- 题干全文
    question_type TEXT,              -- 单选题 / 多选题 / 填空题 / 开放题 / 量表题
    interviewer_note TEXT,           -- 访题说明 / 访员注意
    skip_pattern TEXT,               -- 跳转逻辑（如：若选3→跳至A5）
    universe TEXT,                   -- 适用人群（如：所有受访者 / 仅已婚者）
    is_core_module INTEGER DEFAULT 0,-- 是否核心追踪模块
    sort_order REAL                  -- 在问卷中的排序
);

-- 值标签（选项编码）
CREATE TABLE value_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variable_id INTEGER NOT NULL REFERENCES variables(id),
    value TEXT NOT NULL,             -- 1, 2, 97, 98, 99
    label TEXT NOT NULL,             -- 男, 女, 不适用, 拒绝回答, 不知道
    is_missing INTEGER DEFAULT 0,    -- 是否系统缺失值
    sort_order INTEGER DEFAULT 0
);

-- 跨波次变量对照（后续扩展）
CREATE TABLE crosswalk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER REFERENCES surveys(id),
    var_name TEXT,
    wave_a_id INTEGER REFERENCES waves(id),
    wave_b_id INTEGER REFERENCES waves(id),
    variable_a_id INTEGER REFERENCES variables(id),
    variable_b_id INTEGER REFERENCES variables(id),
    match_type TEXT,                 -- exact / similar / derived / new
    note TEXT
);

-- FTS5 全文搜索索引
CREATE VIRTUAL TABLE variables_fts USING fts5(
    var_name,
    question_text,
    section,
    content='variables',
    content_rowid='id'
);
```

### 2.2 索引

```sql
CREATE INDEX idx_variables_wave ON variables(wave_id);
CREATE INDEX idx_variables_name ON variables(var_name);
CREATE INDEX idx_variables_section ON variables(section);
CREATE INDEX idx_value_labels_var ON value_labels(variable_id);
CREATE INDEX idx_waves_survey_year ON waves(survey_id, year);
```

---

## 3. 项目目录结构

```
D:\AI agent\Workbuddy工作\问卷codebook\
│
├── PLAN.md                          # 本文件：完整建设方案
├── schema.sql                       # 数据库建表SQL
│
├── data/
│   ├── pdf/                         # 原始PDF问卷（用户提供，不提交Git）
│   │   ├── CGSS2003_questionnaire.pdf
│   │   ├── CGSS2005_questionnaire.pdf
│   │   └── ...
│   ├── markdown/                    # MinerU转换后的Markdown
│   │   ├── CGSS2003.md
│   │   └── ...
│   ├── json/                        # LLM提取的结构化JSON
│   │   ├── CGSS2003.json
│   │   └── ...
│   └── cgss.db                      # SQLite最终产物
│
├── scripts/
│   ├── step1_pdf_to_md.py           # PDF → Markdown（调MinerU API）
│   ├── step2_md_to_json.py          # Markdown → 结构化JSON（调LLM）
│   ├── step3_json_to_db.py          # JSON → SQLite（建库写入）
│   ├── query.py                     # AI agent入口：查询工具
│   └── utils.py                     # 公共工具函数
│
├── prompts/
│   └── extraction.md                # LLM提取的system prompt（核心！）
│
├── tests/
│   └── test_queries.py              # 验证查询
│
└── .gitignore
```

---

## 4. 流水线三步走

### Step 1: PDF → Markdown

**脚本**：`scripts/step1_pdf_to_md.py`

**逻辑**：
1. 扫描 `data/pdf/` 下所有 PDF
2. 逐文件调用 MinerU API 上传并解析
3. 等待解析完成，下载 Markdown 结果
4. 保存到 `data/markdown/`

**依赖**：
- MinerU API Key（已配置于用户环境）
- `requests` 库

**注意事项**：
- CGSS 早期问卷（2003-2008）排版较旧，OCR 可能需要额外校验
- 部分 PDF 可能是扫描件，MinerU 需要启用 OCR 模式（`language=ch`）
- 建议先抽一个样本跑通后再批量

---

### Step 2: Markdown → 结构化JSON

**脚本**：`scripts/step2_md_to_json.py`

**逻辑**：
1. 读取 `data/markdown/CGSS{year}.md`
2. 调用 LLM（DeepSeek V4 Pro），传入提取 prompt
3. LLM 输出结构化 JSON 数组
4. 验证 JSON schema
5. 保存到 `data/json/CGSS{year}.json`

**LLM Prompt 设计要点**（详见 `prompts/extraction.md`）：
- 输入：整个问卷的 Markdown 文本
- 输出格式：JSON 数组，每个元素对应一道题
- 提取字段：var_name, question_number, question_text, question_type, interviewer_note, skip_pattern, universe, section, value_labels
- 处理特殊情况：表格题、矩阵题、多选题的分支（如 a1a, a1b）、嵌套跳转逻辑

**人工抽检**：
- 对关键年份（2003、2010、2017、2021）人工核对 20-30 道题
- 重点检查：变量名准确率、跳转逻辑完整性、值标签缺失值标注

---

### Step 3: JSON → SQLite

**脚本**：`scripts/step3_json_to_db.py`

**逻辑**：
1. 创建数据库（如不存在）
2. 执行 `schema.sql` 建表
3. 遍历 `data/json/` 下所有 JSON 文件
4. 写入 surveys、waves、variables、value_labels 表
5. 重建 FTS5 索引
6. 执行验证 SQL

**验证 SQL**（构建后必跑）：
```sql
-- 各波次变量数统计
SELECT s.name, w.year, COUNT(v.id) as var_count
FROM surveys s
JOIN waves w ON w.survey_id = s.id
JOIN variables v ON v.wave_id = w.id
GROUP BY s.name, w.year
ORDER BY w.year;

-- 检查有无变量缺失值标签
SELECT COUNT(*) FROM variables v
LEFT JOIN value_labels vl ON vl.variable_id = v.id
WHERE vl.id IS NULL AND v.question_type IN ('单选题', '多选题');
```

---

## 5. query.py — AI Agent 入口

### 使用方式

```bash
# 全文搜索
python scripts/query.py search "生育意愿"

# 精确查变量
python scripts/query.py var --survey CGSS --wave 2017 --var a1

# 模糊查变量名
python scripts/query.py var --survey CGSS --wave 2017 --like "a1*"

# 列出某调查所有波次
python scripts/query.py waves --survey CGSS

# 查看某波次所有模块
python scripts/query.py sections --survey CGSS --wave 2017

# 列出某模块所有变量
python scripts/query.py module --survey CGSS --wave 2017 --section "A部分：核心模块"

# 输出数据库统计
python scripts/query.py stats

# 导出某波次为CSV
python scripts/query.py export --survey CGSS --wave 2017 --output cgss2017.csv
```

### 输出格式

终端友好的表格格式，AI agent 直接阅读理解：

```
┌──────────┬──────────────────────────────────────┬──────────────────────┐
│ var_name │ question_text                        │ value_labels         │
├──────────┼──────────────────────────────────────┼──────────────────────┤
│ a1       │ 您的性别：                           │ 1=男, 2=女           │
│ a2       │ 您的出生日期（阳历）：____年____月    │ 开放题               │
│ a3a      │ 您目前的户口登记地是：               │ 1=本乡/镇/街道, ...   │
└──────────┴──────────────────────────────────────┴──────────────────────┘
```

---

## 6. 执行顺序

| 序号 | 步骤 | 产出 | 验证方式 |
|------|------|------|----------|
| 1 | 确认 PDF 路径 | CGSS全部年份PDF就位 | `ls data/pdf/` |
| 2 | 创建项目骨架 | 目录结构、schema.sql | 检查文件存在 |
| 3 | 跑 step1 | `data/markdown/*.md` | 抽查1-2个MD文件可读性 |
| 4 | 写 extraction prompt | `prompts/extraction.md` | 手动测1个年份JSON质量 |
| 5 | 跑 step2 | `data/json/*.json` | JSON schema验证 |
| 6 | 跑 step3 | `data/cgss.db` | 验证SQL跑通 |
| 7 | 写 query.py | 查询工具可用 | 跑 test_queries.py |
| 8 | 人工抽检 | 质量报告 | 抽检4个关键年份 |

---

## 7. 待决策/待提供

- [ ] **CGSS PDF 存放路径**：全部年份 PDF 现在在哪里？
- [ ] **独立 codebook**：除了问卷 PDF，是否有独立的变量编码表（.xlsx/.dta）？如有可大幅加速 step2
- [ ] **LLM 选择**：提取用 DeepSeek V4 Pro（已配置）还是其他模型？
- [ ] **缺失值编码规范**：不同年份的系统缺失值（97/98/99/999）需统一处理吗？
- [ ] **Git 仓库**：是否需要初始化 GitHub 仓库？`.gitignore` 应排除 `data/pdf/`（版权）和 `data/cgss.db`（二进制大文件）
