# 使用说明

> China Survey Codebook CLI — 检索 CGSS/CFPS 变量元数据

## 快速开始

```bash
# 列出所有调查年份
python cli/codebook.py surveys

# 搜索变量
python cli/codebook.py search "性别"
python cli/codebook.py search "income" --survey CGSS --year 2010

# 查看变量详情
python cli/codebook.py variable CGSS 2010 a2

# 跨年对比
python cli/codebook.py compare a2 --years all

# 按主题导出
python cli/codebook.py export --tag demographic --format json
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
python cli/codebook.py search <keyword> [--survey S] [--year Y] [--tag T]
```

搜索范围：变量名、中文标签、英文标签（FTS5 全文检索，支持中文）。

```bash
# 搜索所有含"教育"的变量
python cli/codebook.py search "教育"

# 限定 2010 年
python cli/codebook.py search "教育" --year 2010

# 限定 education 主题标签
python cli/codebook.py search "教育" --tag education

# 组合过滤
python cli/codebook.py search "收入" --survey CGSS --year 2010 --tag income
```

输出列：调查、年份、变量名、标签、Tags。最多返回 200 条。

### 2. `variable` — 查看变量详情

```bash
python cli/codebook.py variable <survey> <year> <varname>
```

```bash
python cli/codebook.py variable CGSS 2010 a2
```

输出：
- 基本信息：标签、英文标签、类型、格式、源文件
- 主题标签
- 取值标签（全部 value-label 映射）
- 缺失规则（`missing_rules`，从 JSON 回读）
- 跨年匹配（`cross_year_match`，从 JSON 回读）

### 3. `compare` — 跨年对比同一变量

```bash
python cli/codebook.py compare <varname> --years Y1,Y2,...|all
```

```bash
# 对比所有年份
python cli/codebook.py compare a2 --years all

# 指定年份
python cli/codebook.py compare a62 --years 2010,2015,2018,2023
```

输出：
- 每年的标签、Tags、取值标签
- Label 一致性检测（跨年 label 是否变化）
- 取值标签一致性检测

**注意**：CGSS 变量命名跨年不一致（如 2003=sex, 2005=qa2_01, 2010+=a2），`compare` 仅对比变量名相同的年份。跨年同义变量映射见 `data/variable_mapping.json`。

### 4. `export` — 按主题导出

```bash
python cli/codebook.py export --tag <T> [--format json|csv]
```

```bash
# 导出所有 demographic 变量为 JSON
python cli/codebook.py export --tag demographic --format json

# 导出 income 变量为 CSV
python cli/codebook.py export --tag income --format csv
```

导出所有年份中带有该 tag 的变量，含取值标签。

可用 tag：`demographic` / `education` / `income` / `labor` / `health` / `family` / `political` / `trust` / `subjective` / `attitude`。

### 5. `surveys` — 列出所有调查年份

```bash
python cli/codebook.py surveys
```

输出每个调查-年份的变量数。

## 主题标签体系

| Tag | 中文 | 覆盖范围 |
|---|---|---|
| `demographic` | 人口学特征 | 性别、年龄、民族、户口、婚姻 |
| `education` | 教育 | 教育程度、学历、受教育年限 |
| `income` | 收入 | 个人/家庭收入、收入来源 |
| `labor` | 劳动就业 | 就业状态、职业、工时、工作性质 |
| `health` | 健康 | 自评健康、就医、医保、健康行为 |
| `family` | 家庭 | 家庭结构、子女、家务、家庭关系 |
| `political` | 政治参与 | 政治面貌、政治参与、政治态度 |
| `trust` | 社会信任 | 人际信任、制度信任 |
| `subjective` | 主观评价 | 主观阶层、幸福感、满意度 |
| `attitude` | 价值观态度 | 社会价值观、文化态度 |

标签定义见 `tags/topic_tags.json`。变量打标采用通配符键 `CGSS:*:varname`，适用于所有年份。

## AI Agent 集成

AI agent 通过 `--json` 开关获取结构化输出：

```bash
# 1. 搜索教育相关变量
python cli/codebook.py search "教育" --tag education --json

# 2. 查看变量详情（含取值标签和缺失码）
python cli/codebook.py variable CGSS 2010 a7a --json

# 3. 跨年可用性
python cli/codebook.py compare a7a --years all --json

# 4. 导出某主题全部变量
python cli/codebook.py export --tag income --format json
```

### 典型场景：研究"教育对收入的影响"

```bash
# Step 1: 找教育变量
python cli/codebook.py search "教育" --tag education --json
# → a7a（最高教育程度），2010-2023 都有

# Step 2: 找收入变量
python cli/codebook.py search "收入" --tag income --json
# → a62（家庭总收入）、a8a（个人总收入）

# Step 3: 查看取值标签和缺失码
python cli/codebook.py variable CGSS 2010 a7a --json
python cli/codebook.py variable CGSS 2010 a62 --json

# Step 4: 跨年对比
python cli/codebook.py compare a7a --years all --json
python cli/codebook.py compare a62 --years all --json

# Step 5: AI agent 据此生成 Stata do 文件
# （知道 a7a 取值 1-13 对应不同学历，a62 含 -1/-2/-3 缺失码）
```

## 数据覆盖

| 调查 | 年份 | 变量数 |
|---|---|---|
| CGSS | 2003 | 898 |
| CGSS | 2005 | 554 |
| CGSS | 2006 | 1610 |
| CGSS | 2008 | 1504 |
| CGSS | 2010 | 871 |
| CGSS | 2011 | 595 |
| CGSS | 2012 | 687 |
| CGSS | 2013 | 722 |
| CGSS | 2015 | 1398 |
| CGSS | 2017 | 783 |
| CGSS | 2018 | 1029 |
| CGSS | 2021 | 700 |
| CGSS | 2023 | 439 |
| **合计** | | **11790** |

CFPS 待接入（Phase 4）。

---

_Phase 3 完成于 2026-07-04_
