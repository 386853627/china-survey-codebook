# 使用说明

> China Survey Codebook CLI — 检索 CGSS/CHFS 变量元数据

## 快速开始

```bash
# 列出所有调查-年份-数据集
python cli/codebook.py surveys

# 搜索变量（跨调查）
python cli/codebook.py search "性别"
python cli/codebook.py search "住房" --survey CHFS --dataset household

# 查看变量详情（CHFS 需指定 --dataset）
python cli/codebook.py variable CGSS 2010 a2
python cli/codebook.py variable CHFS 2017 a2003 --dataset individual

# 跨年对比
python cli/codebook.py compare a2 --years all --survey CGSS
python cli/codebook.py compare a2003 --years all --survey CHFS --dataset individual

# 按主题导出
python cli/codebook.py export --tag housing --survey CHFS --format json
```

## 全局参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--json` | 输出 JSON 格式（供 AI agent 消费） | 关闭（人类可读表格） |
| `--db PATH` | SQLite 路径 | `data/codebook.db` |
| `--codebook-dir PATH` | JSON 目录（variable 命令回读用） | `data/codebook` |

`--json` 可放在子命令前或后：

```bash
python cli/codebook.py --json search "性别"
python cli/codebook.py search "性别" --json
```

## 命令详解

### 1. `search` — 按关键词搜索变量

```bash
python cli/codebook.py search <keyword> [--survey S] [--year Y] [--dataset D] [--tag T]
```

搜索范围：变量名、中文标签、英文标签（FTS5 全文检索，支持中文）。

```bash
# 搜索所有含"教育"的变量
python cli/codebook.py search "教育"

# 限定 CHFS household 表
python cli/codebook.py search "住房" --survey CHFS --dataset household

# 限定 housing 主题标签
python cli/codebook.py search "面积" --tag housing

# 组合过滤
python cli/codebook.py search "收入" --survey CHFS --year 2017
```

输出列：调查、年份、数据集、变量名、标签。最多返回 200 条。

### 2. `variable` — 查看变量详情

```bash
python cli/codebook.py variable <survey> <year> <varname> [--dataset D]
```

```bash
# CGSS（dataset 默认 main）
python cli/codebook.py variable CGSS 2010 a2

# CHFS（必须指定 --dataset）
python cli/codebook.py variable CHFS 2017 a2003 --dataset individual
python cli/codebook.py variable CHFS 2015 c2002 --dataset household
python cli/codebook.py variable CHFS 2011 province --dataset master
```

输出：
- 基本信息：标签、英文标签、类型、格式、源文件
- 主题标签
- 取值标签（全部 value-label 映射）
- 缺失规则（`missing_rules`，从 JSON 回读）
- 跨年匹配（`cross_year_match`，从 JSON 回读）

### 3. `compare` — 跨年/跨数据集对比同一变量

```bash
python cli/codebook.py compare <varname> --years Y1,Y2,...|all [--survey S] [--dataset D]
```

```bash
# CGSS 性别变量跨年对比
python cli/codebook.py compare a2 --years all --survey CGSS

# CHFS 性别变量跨年对比（限定 individual 表）
python cli/codebook.py compare a2003 --years all --survey CHFS --dataset individual

# 指定年份
python cli/codebook.py compare a62 --years 2010,2015,2018,2023 --survey CGSS
```

输出：
- 每条记录的 survey、year、dataset、label、取值标签
- Label 一致性检测
- 取值标签一致性检测

**注意**：CHFS 同名变量可能跨 dataset 出现（如 master 和 individual 都有 hhid），不加 `--dataset` 会返回全部记录。

### 4. `export` — 按主题导出

```bash
python cli/codebook.py export --tag <T> [--survey S] [--dataset D] [--format json|csv]
```

```bash
# 导出所有 housing 变量（CHFS 为主）
python cli/codebook.py export --tag housing --format json

# 仅导出 CHFS household 表的 asset 变量
python cli/codebook.py export --tag asset --survey CHFS --dataset household --format csv

# 导出 CGSS demographic 变量
python cli/codebook.py export --tag demographic --survey CGSS --format json
```

可用 tag（14 类）：
- 基础：`demographic` / `education` / `income` / `labor` / `health` / `family` / `political` / `trust` / `subjective` / `attitude`
- CHFS 特色：`finance` / `credit` / `asset` / `housing`

### 5. `surveys` — 列出所有调查-年份-数据集

```bash
python cli/codebook.py surveys
```

输出每个 (survey, year, dataset) 组合的变量数。

## 跨调查映射

### variable_mapping.json（同名变量映射）

`data/variable_mapping.json` 记录所有同名变量跨年/跨调查的出现情况，matches 格式 `survey:year:dataset:varname`。

```bash
# 查看哪些变量名跨 CGSS+CHFS 都存在
python -c "
import json
d = json.load(open('data/variable_mapping.json', encoding='utf-8'))
cross = [m for m in d['mappings'] if m['n_surveys'] >= 2]
print(f'跨调查同名变量: {len(cross)} 个')
"
```

### cross_survey_mapping.json（异名同义映射）

`data/cross_survey_mapping.json` 记录 CGSS↔CHFS 异名但同义的变量映射（如 CGSS a2 性别 ↔ CHFS a2003 性别）。

当前覆盖 18 个核心主题：gender / birth_year / education / hukou_status / marital_status / family_total_income / family_economic_level / n_houses / house_area_built / house_area_used / own_house / house_mortgage / house_value_other / house_repair_expense / family_member_relation / household_id / province / rural / sampling_weight。

## AI Agent 集成

AI agent 通过 `--json` 开关获取结构化输出：

```bash
# 1. 搜索住房相关变量（CHFS）
python cli/codebook.py search "住房" --survey CHFS --tag housing --json

# 2. 查看变量详情（含取值标签和缺失码）
python cli/codebook.py variable CHFS 2017 c2002 --dataset household --json

# 3. 跨年可用性
python cli/codebook.py compare c2002 --years all --survey CHFS --dataset household --json

# 4. 导出某主题全部变量
python cli/codebook.py export --tag housing --survey CHFS --format json
```

### 典型场景：研究"住房资产对家庭收入的影响"（CHFS）

```bash
# Step 1: 找住房变量
python cli/codebook.py search "住房" --survey CHFS --tag housing --json
# → c2001（是否自有住房）、c2002（住房套数）、c2003_1（建筑面积）

# Step 2: 找收入变量
python cli/codebook.py search "收入" --survey CHFS --tag income --json

# Step 3: 查看取值标签
python cli/codebook.py variable CHFS 2017 c2001 --dataset household --json
python cli/codebook.py variable CHFS 2017 c2002 --dataset household --json

# Step 4: 跨年对比
python cli/codebook.py compare c2002 --years all --survey CHFS --dataset household --json

# Step 5: AI agent 据此生成 Stata do 文件
# （知道 c2001 取值 0/1，c2002 为住房套数，2015-2021 都有）
```

## 数据覆盖

### CGSS（中国综合社会调查）

| 年份 | dataset | 变量数 |
|---|---|---|
| 2003, 2005, 2006, 2008, 2010, 2011, 2012, 2013, 2015, 2017, 2018, 2021, 2023 | main | 11790 |
| **合计** | | **11790** |

### CHFS（中国家庭金融调查）

| 年份 | dataset | 变量数 |
|---|---|---|
| 2011 | household / master / individual | 1207 + 5 + 239 |
| 2013 | household / master / individual | 2018 + 6 + 315 |
| 2015 | household / master / individual | 3011 + 8 + 309 |
| 2017 | household / master / individual | 2457 + 15 + 387 |
| 2019 | household / master / individual | 2656 + 54 + 423 |
| 2021 | household / individual / master_household / master_individual | 3443 + 408 + 57 + 7 |
| **合计** | | **17025** |

**CGSS + CHFS 总变量数：28815**

---

_Phase 4 完成于 2026-07-06_
