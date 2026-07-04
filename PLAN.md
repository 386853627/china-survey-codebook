# CGSS Codebook 机器可读元数据库 — 实施计划

> 项目：构建 AI agent 可调用的 CGSS/CFPS codebook 元数据库
> 启动日期：2026-07-04
> 状态：方案已确认（方案 B：多文件分层 JSON + SQLite 索引）

---

## 0. 项目背景

阿远（社会学博士）长期使用 CGSS、CFPS 等中国全国性社会科学调查数据。希望构建机器可读的 codebook 元数据库，作为调查数据的元数据层，供 AI agent 调用，实现：
- 根据研究问题推荐可行的实证方案
- 在提供原始数据后生成并执行 Stata 数据处理与计量分析代码

## 1. 需求确认

| 维度 | 决策 |
|---|---|
| AI 调用方式 | 静态文件（JSON）+ SQLite 索引 + CLI 工具（非 MCP server） |
| 首批数据 | CGSS（13 年 .dta 已就位） |
| Tag 体系 | 粗粒度主题标签起步 |
| 后续扩展 | CFPS |
| ETL 工具 | Python 3.13 + pandas（`read_stata` 读取 .dta） |

## 2. 数据盘点

cgss/ 目录下 13 个 .dta 文件：

| 年份 | 文件名 | 大小 |
|---|---|---|
| 2003 | CGSS2003.dta | 7.6 MB |
| 2005 | cgss2005.dta | 7.6 MB |
| 2006 | CGSS2006.dta | 22.8 MB |
| 2008 | CGSS2008.dta | 11.8 MB |
| 2010 | CGSS2010.dta | 13.3 MB |
| 2011 | CGSS2011.dta | 4.3 MB |
| 2012 | CGSS2012.dta | 54.6 MB |
| 2013 | CGSS2013.dta | 33.5 MB |
| 2015 | CGSS2015.dta | 84.2 MB |
| 2017 | cgss2017.dta | 45.9 MB |
| 2018 | CGSS2018.dta | 69.2 MB |
| 2021 | CGSS2021.dta | 7.6 MB |
| 2023 | CGSS2023.dta | 45.6 MB |

## 3. 选定方案：方案 B（多文件分层 JSON + SQLite 索引）

### 3.1 备选方案比较（决策记录）

| 方案 | 数据结构 | 检索方式 | 维护成本 | 扩展性 | 准确性 | AI 调用便利性 |
|---|---|---|---|---|---|---|
| A. 单一大 JSON | 扁平 | 全文搜 | 低 | 差 | 中 | 中 |
| **B. 多文件 JSON + SQLite** | 分层 | SQL + FTS | 中 | 好 | 高 | 高 |
| C. 纯 SQLite | 关系型 | SQL | 中 | 中 | 高 | 中 |
| D. Parquet + DuckDB | 列式 | SQL | 高 | 好 | 高 | 中 |

**选 B 的理由**：JSON 人类可读、Git 可 diff、版本可控；SQLite 作为索引层加速检索；Python pandas `read_stata` 直接读取 .dta 元数据，单一工具链便于维护。

### 3.2 目录结构

```
问卷codebook/
├── cgss/                          # 原始 .dta 文件（已就位）
├── data/
│   ├── codebook/                  # 元数据 JSON（每年一个文件）
│   │   ├── CGSS2003.json
│   │   ├── CGSS2010.json
│   │   └── ...
│   ├── codebook.db                # SQLite 索引（从 JSON 构建）
│   └── variable_mapping.json      # 跨年/跨调查变量映射
├── etl/
│   ├── extract_metadata.py        # Python ETL 主脚本（读取 .dta → JSON）
│   └── build_sqlite.py            # JSON → SQLite 索引构建
├── cli/
│   └── codebook.py                # 检索 CLI 工具
├── tags/
│   └── topic_tags.json            # 变量主题标签映射
├── docs/
│   ├── SCHEMA.md                  # JSON Schema 文档
│   └── USAGE.md                   # 使用说明
├── .workbuddy/
│   └── memory/                    # 工作日志
├── PLAN.md                        # 本文件
└── README.md
```

## 4. JSON Schema 设计

### 4.1 单变量元数据结构

```json
{
  "survey": "CGSS",
  "year": 2010,
  "module": "core",
  "varname": "a2",
  "label": "性别",
  "label_en": "Gender",
  "vtype": "numeric",
  "format": "%8.0g",
  "valuelabels": {
    "1": "男",
    "2": "女"
  },
  "missing_rules": {
    "system": [-1, -2, -3],
    "user": [98, 99]
  },
  "topic_tags": ["demographic", "gender"],
  "cross_year_match": {
    "same_var": ["CGSS2003:a2", "CGSS2005:a2", "CGSS2008:a2"]
  }
}
```

### 4.2 单年份文件结构

```json
{
  "survey": "CGSS",
  "year": 2010,
  "source_file": "cgss/CGSS2010.dta",
  "n_variables": 700,
  "n_observations": 11783,
  "extracted_at": "2026-07-04T17:00:00",
  "stata_version": "StataMP 19",
  "variables": [
    { "varname": "id", ... },
    { "varname": "a2", ... }
  ]
}
```

## 5. ETL 流程（Python pandas 读取 .dta → JSON）

### 5.1 Python ETL 主脚本（etl/extract_metadata.py）

单一 Python 脚本完成全流程，无需 Stata 或 CSV 中间格式：

- `pandas.read_stata()` 读取 .dta，通过 `iterator=True` 获取 `StataReader` 对象
- `reader.variable_labels()` → 变量标签
- `reader.value_labels()` → 取值标签
- `reader.variable_format()` → Stata 显示格式
- `reader.dtyplabs` / `reader.varlist` → 变量名与类型
- `reader.nobs` → 观测值数量
- 统计实际缺失值分布（前 N 条抽样），自动推断缺失码

**调用方式**：
```bash
python etl/extract_metadata.py <year> <dta_path> [--output data/codebook/]
# 例：
python etl/extract_metadata.py 2010 cgss/CGSS2010.dta
```

### 5.2 编码处理

- pandas `read_stata` 内部处理 .dta 文件编码（Stata 13+ 为 UTF-8，早期为 ASCII/GBK）
- 若遇乱码，回退方案：用 `read_stata(..., convert_categoricals=False)` 读取原始值，再手动映射标签
- 输出 JSON 统一 `ensure_ascii=False`，保留中文可读

### 5.3 缺失值规则自动推断

- 检测负值（-1, -2, -3 是 CGSS 常见缺失码）
- 检测 97/98/99 等高位"拒答/不知道"
- 写入 `missing_rules`，AI agent 据此自动 recode

## 6. SQLite 索引设计

```sql
CREATE TABLE variables (
    survey TEXT, year INTEGER, varname TEXT,
    label TEXT, label_en TEXT, vtype TEXT,
    topic_tags TEXT,  -- JSON array
    source_file TEXT,
    PRIMARY KEY (survey, year, varname)
);

CREATE TABLE valuelabels (
    survey TEXT, year INTEGER, varname TEXT,
    value TEXT, label TEXT
);

CREATE VIRTUAL TABLE variables_fts USING fts5(
    varname, label, label_en, topic_tags
);
```

**检索能力**：
- 按年份/变量名精确查
- 按中文/英文标签模糊查（FTS5）
- 按 topic_tag 分类查
- 跨年对比同一变量

## 7. CLI 工具（codebook.py）

```bash
# 按关键词搜索变量
python cli/codebook.py search "性别"
python cli/codebook.py search "income" --survey CGSS --year 2010

# 查看某变量详情（含取值标签、缺失规则）
python cli/codebook.py variable CGSS 2010 a2

# 跨年对比
python cli/codebook.py compare a2 --years 2003,2010,2018,2023

# 导出某主题所有变量（供 AI agent 消费）
python cli/codebook.py export --tag demographic --format json

# 列出所有调查年份
python cli/codebook.py surveys
```

## 8. 实施阶段（4 个 Phase）

> **重要**：本项目跨多个对话框完成。每个 Phase 可独立作为一个对话框的任务。开始前请先读本 PLAN.md 和 .workbuddy/memory/ 下的日志了解上下文。

### Phase 1: Schema 设计 + ETL 试点（CGSS2010）

**目标**：跑通从 .dta 到 JSON 的完整流程

**任务清单**：
- [ ] 写 `docs/SCHEMA.md`（完整 JSON Schema 文档）
- [ ] 写 `etl/extract_metadata.py`（Python ETL 脚本，pandas 读取 .dta）
- [ ] 用 CGSS2010 跑试点，生成 `data/codebook/CGSS2010.json`
- [ ] 交叉验证字段完整性（变量数、标签数、取值标签对照）

**验证标准**：
- JSON 中变量数 = pandas `StataReader` 报告的变量数
- 取值标签完整无误
- 缺失值规则合理

**产出文件**：
- `docs/SCHEMA.md`
- `etl/extract_metadata.py`（Python ETL 脚本）
- `data/codebook/CGSS2010.json`

### Phase 2: 全量入库 + SQLite 索引

**前置**：Phase 1 完成

**任务清单**：
- [ ] 批量跑 13 年 ETL
- [ ] 写 `etl/build_sqlite.py`（JSON → SQLite）
- [ ] 构建 `data/codebook.db`
- [ ] 生成 `data/variable_mapping.json`（跨年同义变量）
- [ ] 全量验证：每年变量数对账

**验证标准**：
- 13 个 JSON 文件生成完毕
- SQLite 可查询，FTS 可检索
- 跨年映射至少覆盖核心人口学变量

**产出文件**：
- `data/codebook/CGSS{2003,2005,...,2023}.json`（13 个）
- `data/codebook.db`
- `data/variable_mapping.json`
- `etl/build_sqlite.py`

### Phase 3: CLI 工具 + Tag 体系

**前置**：Phase 2 完成

**任务清单**：
- [ ] 写 `cli/codebook.py`（5 个子命令）
- [ ] 设计粗粒度 tag 体系（demographic/income/health/education/family/labor/political/trust 等）
- [ ] 写 `tags/topic_tags.json`（变量 → tag 映射）
- [ ] 对核心变量（前 200 个高频变量）打标
- [ ] 写 `docs/USAGE.md`

**验证标准**：
- `search` / `variable` / `compare` / `export` / `surveys` 五个命令可用
- 核心变量有 tag

**产出文件**：
- `cli/codebook.py`
- `tags/topic_tags.json`
- `docs/USAGE.md`

### Phase 4: CFPS 扩展 + 跨调查映射 + 文档完善

**前置**：Phase 3 完成

**任务清单**：
- [ ] 接入 CFPS 数据（ETL 复用 Phase 1 脚本）
- [ ] 构建 `data/codebook/CFPS*.json`
- [ ] 生成跨调查变量映射（CGSS ↔ CFPS）
- [ ] 写 `README.md`（项目总览）
- [ ] 端到端测试：模拟 AI agent 调用场景

**验证标准**：
- CFPS 可检索
- 跨调查对比可用
- AI agent 能根据研究问题推荐变量并生成 Stata 代码

**产出文件**：
- `data/codebook/CFPS*.json`
- `data/variable_mapping.json`（含跨调查映射）
- `README.md`

## 9. AI Agent 调用场景示例

**场景**：你问"我想研究教育对收入的影响，CGSS 哪些年份有相关变量？"

```
Agent 流程：
1. cli/codebook.py search "教育" --tag education
2. cli/codebook.py search "收入" --tag income
3. cli/codebook.py compare a7a --years all  # 教育程度变量跨年
4. cli/codebook.py compare a62 --years all  # 收入变量跨年
5. 返回：2010-2018 都有 a7a（教育程度）和 a62（总收入），
        2021 后改用 b7a/b62，给出映射
6. 生成 Stata do 文件：合并多年 + recode 缺失值 + 回归
```

**关键**：AI agent 通过 CLI 拿到结构化元数据，知道每个变量的取值范围和缺失码，生成的 Stata 代码准确率大幅提升。

## 10. 关键设计决策

1. **JSON 优先于纯 SQLite**：JSON 人类可读、Git 可 diff、易于版本管理；SQLite 作为索引层加速检索
2. **Python pandas ETL**：`read_stata` 直接读取 .dta 元数据，单一工具链便于维护，避免 Stata 批量模式的编码坑和 CSV 中间格式开销
3. **无中间格式**：pandas 直接输出 JSON，不再经过 CSV 中转
4. **粗粒度 tag 起步**：demographic/income/health/education/family/labor/political/trust 等 8-10 个大类，后续按需细化
5. **跨年映射最后做**：需要全量入库后才能识别同义变量
6. **静态文件 + CLI 而非 MCP**：零服务依赖，AI agent 直接读文件或调 CLI

## 11. 跨对话框协作约定

由于 context 长度有限，本项目分多对话框完成。每个新对话框开始时：

1. **AI agent 应先读**：
   - `PLAN.md`（本文件，了解整体计划）
   - `.workbuddy/memory/YYYY-MM-DD.md`（最新工作日志，了解进度）
   - 当前 Phase 对应的产出文件（了解已有成果）

2. **用户会在新对话框开头说明**：
   - 当前要执行哪个 Phase
   - 或给出具体任务

3. **每个对话框结束时应**：
   - 更新 `.workbuddy/memory/YYYY-MM-DD.md`（记录本次完成的工作）
   - 勾选 PLAN.md 中已完成的任务项
   - 说明下一对话框应从哪里接续

## 12. 进度追踪

| Phase | 状态 | 完成日期 | 备注 |
|---|---|---|---|
| 1. Schema + ETL 试点 | ⬜ 未开始 | - | 下一步 |
| 2. 全量入库 + SQLite | ⬜ 未开始 | - | - |
| 3. CLI + Tag 体系 | ⬜ 未开始 | - | - |
| 4. CFPS + 文档 | ⬜ 未开始 | - | - |

---

_最后更新：2026-07-04_
