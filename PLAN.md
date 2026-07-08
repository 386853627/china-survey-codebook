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
- [x] 写 `docs/SCHEMA.md`（完整 JSON Schema 文档）
- [x] 写 `etl/extract_metadata.py`（Python ETL 脚本，pandas 读取 .dta）
- [x] 用 CGSS2010 跑试点，生成 `data/codebook/CGSS2010.json`
- [x] 交叉验证字段完整性（变量数、标签数、取值标签对照）

**验证标准**：
- JSON 中变量数 = pandas `StataReader` 报告的变量数
- 取值标签完整无误
- 缺失值规则合理

**产出文件**：
- `docs/SCHEMA.md`
- `etl/extract_metadata.py`（Python ETL 脚本）
- `data/codebook/CGSS2010.json`

### Phase 2: 全量入库 + SQLite 索引 ✅ 完成（2026-07-04）

**前置**：Phase 1 完成

**任务清单**：
- [x] 批量跑 13 年 ETL
- [x] 写 `etl/build_sqlite.py`（JSON → SQLite）
- [x] 构建 `data/codebook.db`
- [x] 生成 `data/variable_mapping.json`（跨年同义变量）
- [x] 全量验证：每年变量数对账

**验证结果**：
- 13 个 JSON 全部生成（共 11790 变量）
- SQLite 11790 行 + valuelabels 182931 行 + FTS5 中文检索可用
- 13 年变量数对账全部 OK
- 跨年映射 955 条（id/weight 跨 10 年最多）
- codebook.db 17.5 MB
- CGSS2003 编码无乱码

**关键发现**：
- CGSS 变量命名跨年不一致：性别变量 2003=sex, 2005=qa2_01, 2006=qa01, 2010+=a2 → Phase 4 跨调查映射需处理
- 2005/2006 有 latin-1 fallback warning 但中文标签实际正确（UTF-8 字节验证通过）
- pandas 3.x 自动处理了所有 13 年 .dta 编码，无需手动指定

**产出文件**：
- `data/codebook/CGSS{2003,2005,...,2023}.json`（13 个）
- `data/codebook.db`
- `data/variable_mapping.json`
- `etl/build_sqlite.py`（重写）
- `etl/build_mapping.py`（新建）

### Phase 3: CLI 工具 + Tag 体系 ✅ 完成（2026-07-04）

**前置**：Phase 2 完成

**任务清单**：
- [x] 写 `cli/codebook.py`（5 个子命令）
- [x] 设计粗粒度 tag 体系（demographic/income/health/education/family/labor/political/trust 等）
- [x] 写 `tags/topic_tags.json`（变量 → tag 映射）
- [x] 对核心变量（前 200 个高频变量）打标
- [x] 写 `docs/USAGE.md`

**验证结果**：
- 5 个子命令（search/variable/compare/export/surveys）全部可用，支持 `--json` 全局开关
- 258 个高频变量（ny>=5）已打标，通配符键 `CGSS:*:varname`，build_sqlite 展开为 1802 条逐年记录
- 10 个 tag 类别全部覆盖：family(691)/labor(661)/demographic(324)/attitude(235)/political(99)/education(90)/income(73)/health(67)/subjective(46)/trust(16)
- DB 重建后 topic_tags 字段正确回填，2021 大写变量（A2）经大小写归一化也正确打标
- variable 命令回读 JSON 取 missing_rules/cross_year_match（DB 未存这两字段）

**关键决策**：
- `--json` 用 argparse parents 机制，可放子命令前或后
- a64（家庭经济档次）打双 tag: income + subjective
- a33/a34（信任量表）归 trust，a35/a38-a40/a421-a425 归 attitude
- trust/subjective 类别变量少是 CGSS 数据本身特点（核心模块信任题仅 2 个）

**产出文件**：
- `cli/codebook.py`（重写，5 子命令）
- `tags/topic_tags.json`（扩充至 258 条）
- `etl/build_sqlite.py`（修改，加 load_tags + resolve_tags 回填）
- `docs/USAGE.md`（重写）
- `data/codebook.db`（重建）

### Phase 4: CHFS 扩展 + 跨调查映射 + 文档完善 ✅ 完成（2026-07-06）

**前置**：Phase 3 完成

**任务清单**：
- [x] 接入 CHFS 数据（ETL 复用 Phase 1 脚本，加 --dataset 参数）
- [x] 构建 `data/codebook/CHFS{year}_{dataset}.json`（19 个文件）
- [x] 生成跨调查变量映射（CGSS ↔ CHFS）
- [x] 写 `README.md`（项目总览）
- [x] 端到端测试：模拟 AI agent 调用场景

**验证结果**：
- CHFS 6 wave × 3-4 dataset = 19 个 .dta → 19 个 JSON，共 17025 变量
- SQLite 四段主键 (survey, year, dataset, varname) 升级，CGSS+CHFS 统一入库，28815 变量，26.2MB DB
- CLI 5 子命令全部支持 --dataset，CHFS 检索正常
- tag 体系扩展至 14 类（新增 finance/credit/asset/housing），CHFS 747 变量打标
- variable_mapping.json 升级为 4 段键，4610 条映射（含 52 条跨调查同名）
- cross_survey_mapping.json 新建，18 个核心主题（gender/education/n_houses 等）
- README.md + SCHEMA.md + USAGE.md 全部更新

**关键决策**：
- CGSS dataset 统一标 "main"（不重跑 13 年 ETL，build_sqlite 回填）
- CHFS 2021 master 拆为 master_household + master_individual 两个 dataset
- CHFS missing_rules 不自动推断（负值正常值多）
- CHFS tag 键 4 段通配符 `CHFS:*:dataset:varname`
- 跨调查异名同义映射手工核对（18 主题），非自动推断

**产出文件**：
- `data/codebook/CHFS{year}_{dataset}.json` × 19
- `data/codebook.db`（重建，四段主键）
- `data/variable_mapping.json`（升级，4 段键）
- `data/cross_survey_mapping.json`（新建，18 主题）
- `etl/extract_metadata.py`（加 --dataset）
- `etl/build_sqlite.py`（四段主键 + tag 4 段解析）
- `etl/build_mapping.py`（升级去重 key）
- `etl/tag_chfs.py`（新建，CHFS 自动打标）
- `etl/run_chfs_etl.py`（新建，批量 ETL）
- `cli/codebook.py`（加 --dataset + UTF-8 强制）
- `tags/topic_tags.json`（14 类 + 1005 变量标签）
- `docs/SCHEMA.md` + `docs/USAGE.md` + `README.md`（全部重写）

### Phase 5: Codebook 质量修复 + 查询辅助层

> **触发原因**：通过三次端到端测试（CHFS 2021 农村大学生 / CHFS 2011 城镇大学生 / CGSS 2023 农村大学生）发现 codebook 存在标签乱码、取值标签缺失、字段不一致、缺乏查询辅助 API 等问题。

**前置**：Phase 4 完成 + 三次 codebook 查询测试

**测试发现的问题汇总**：

| # | 问题 | 影响范围 | 严重度 |
|---|------|----------|--------|
| P5-1 | CHFS 2011/2013 JSON 标签 GBK 乱码 | CHFS 2011/2013 全部变量 | 高 |
| P5-2 | CHFS 2011/2013 取值标签缺失（valuelabels 为空） | CHFS 2011/2013 全部变量 | 高 |
| P5-3 | CGSS JSON 缺少顶层 `dataset` 字段 | 13 个 CGSS JSON | 中 |
| P5-4 | pandas read_stata 行为不一致：值类型因年/调查而异（category 带数字前缀 / category 无前缀 / float64 裸数值） | 全部（用户侧） | 高 |
| P5-5 | 缺乏 Python 查询辅助层：每次查询需手动三步（搜变量→读编码→写匹配） | 全部（用户侧） | 高 |
| P5-6 | 跨调查编码不统一：教育 CHFS a2012(9级) vs CGSS a7a(14级)；户口 CHFS a2022 2011(二分) vs 2021(5类) vs CGSS a18(9类) | 跨调查映射 | 中 |

**任务清单**：

#### P5-1: 修复 CHFS 2011/2013 标签 GBK 乱码 ✅ 完成（2026-07-07）
- [x] 修改 `etl/extract_metadata.py`，增加编码检测逻辑
- [x] 对 CHFS 2011/2013 的 .dta 文件重跑 ETL，生成正确 UTF-8 标签
- [x] 验证：`fix_gkb(label)` 不再需要，JSON 标签直接可读
- [x] 重建 SQLite DB

**方案**：pandas `read_stata` 对 CHFS 2011/2013 .dta 文件以 latin-1 解码了 GBK 字节。需在 ETL 中检测并修复：`label.encode('latin-1').decode('gbk')`，或指定 `convert_categoricals=False` 后手动解码。

**实际做法**：创建 `etl/fix_chfs_labels.py`，用 CHFS 官方问卷 JSON（`chfs/chfs20XX/CHFS20XX_codebook.json`）覆盖乱码标签和填充空取值标签。问卷未匹配的变量再尝试 GBK→UTF-8 修复。CHFS 2011 household 补入 1085 条 valuelabels，CHFS 2013 household 补入 2399 条。

#### P5-2: 补全 CHFS 2011/2013 取值标签 ✅ 完成（2026-07-07）
- [x] 排查 CHFS 2011/2013 .dta 中 valuelabels 缺失原因（DTA 文件本身无标签 vs pandas 未读取）
- [x] 若 DTA 本身有标签集（labelset）但未绑定变量，手工建立变量→编码映射
- [x] 若 DTA 本身无标签，参照 CHFS 问卷文档补录核心变量（a2012 文化程度 / a2022 户口等）的编码
- [x] 写入 JSON 并重建 DB

#### P5-3: CGSS JSON 补 dataset 字段
- [ ] 批量给 13 个 CGSS JSON 顶层加 `"dataset": "main"`
- [ ] 给每个 variable 元素加 `"dataset": "main"` 字段
- [ ] 重建 SQLite DB（验证 dataset 列非空）

#### P5-4: 统一值类型处理策略
- [ ] 在 ETL 中记录每个变量的 `value_type` 元数据：`labeled_category`（有标签的 category）/ `numeric`（裸数值）
- [ ] 在 JSON 中增加 `value_encoding` 字段，标注 DTA 实际读取时的类型
- [ ] 验证：CHFS 2021 = `labeled_category` / CHFS 2011 = `numeric` / CGSS 2023 = `labeled_category`

#### P5-5: 构建 Python 查询辅助层
- [ ] 新建 `lib/codebook_query.py`，封装常见查询模式
- [ ] 核心 API 设计：
  ```python
  from lib.codebook_query import Codebook

  cb = Codebook(db_path="data/codebook.db", json_dir="data/codebook")

  # 按语义查找变量
  cb.search("CHFS", 2021, "individual", keywords=["户口", "户籍"])

  # 获取变量定义（含取值标签）
  cb.get_variable("CGSS", 2023, "main", "a7a")

  # 获取筛选条件：传入语义条件，返回可用于 pandas 的 filter dict
  cb.build_filter("CGSS", 2023, "main",
      hukou="农业户口",       # 自动匹配 a18 == "农业户口"
      education="大专以上"    # 自动匹配 a7a in [9..13]
  )

  # 直接统计数据
  cb.count(dta_path, filters={"hukou": "农业户口", "education": "大专以上"})
  ```
- [ ] 支持"语义条件 → 变量编码 → pandas 筛选"的自动映射
- [ ] 将 test/ 下三个脚本改为调用辅助层，验证可用性

#### P5-6: 跨调查编码归一映射
- [ ] 扩展 `data/cross_survey_mapping.json`，增加编码归一规则
- [ ] 教育编码归一：CGSS a7a(14级) → 统一级别(9级)；CHFS a2012(9级) → 统一级别(9级)
- [ ] 户口编码归一：CGSS a18(9类) / CHFS a2022-2011(二分) / CHFS a2022-2021(5类) → 统一三分类(农业/非农/统一)
- [ ] 在辅助层中提供 `cb.normalize(varname, value, target_scheme="unified")` 方法

**验证标准**：
- CHFS 2011/2013 JSON 标签无乱码，取值标签非空（至少核心变量）
- CGSS JSON 顶层 dataset 字段存在
- `lib/codebook_query.py` 可一行完成"农村大学生"统计，无需手写三步
- 跨调查编码归一后，CHFS 2011 + CGSS 2023 可用统一条件查询

**产出文件**：
- `etl/extract_metadata.py`（修改，编码修复）
- `data/codebook/CHFS{2011,2013}_*.json`（重生成）
- `data/codebook/CGSS*.json`（回填 dataset）
- `data/codebook.db`（重建）
- `lib/codebook_query.py`（新建，查询辅助层）
- `data/cross_survey_mapping.json`（扩展，编码归一）
- `test/`（三个测试脚本改为调用辅助层）

## 9. AI Agent 调用场景示例

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
| 1. Schema + ETL 试点 | ✅ 完成 | 2026-07-04 | CGSS2010: 871变量/11783观测 |
| 2. 全量入库 + SQLite | ✅ 完成 | 2026-07-04 | 13年/11790变量/17.5MB DB/955映射 |
| 3. CLI + Tag 体系 | ✅ 完成 | 2026-07-04 | 258变量打标/5子命令/DB回填 |
| 4. CHFS + 文档 | ✅ 完成 | 2026-07-06 | CHFS 6年19文件/17025变量/14类tag/18跨调查映射 |
| 5. 质量修复 + 查询辅助层 | 🔄 进行中 | — | P5-1/P5-2 ✅, P5-3~P5-6 📋 |

---

_最后更新：2026-07-06（Phase 5 计划制定）_
