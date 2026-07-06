# JSON Schema — Codebook 元数据格式

> 本文档定义 `data/codebook/{survey}{year}_{dataset}.json` 的结构规范。

## 文件命名

```
data/codebook/CGSS2010_main.json         # CGSS 单文件，dataset=main
data/codebook/CHFS2011_household.json    # CHFS household 表
data/codebook/CHFS2011_master.json       # CHFS master 表
data/codebook/CHFS2011_individual.json   # CHFS individual 表
data/codebook/CHFS2021_master_household.json   # CHFS 2021 户主家庭级
data/codebook/CHFS2021_master_individual.json  # CHFS 2021 户主个人级
```

## 顶层结构（单文件）

```json
{
  "survey": "CHFS",
  "year": 2011,
  "dataset": "household",
  "source_file": "chfs/chfs2011/chfs2011_household.dta",
  "n_variables": 1207,
  "n_observations": 8438,
  "extracted_at": "2026-07-06T10:30:00+08:00",
  "etl_version": "1.1",
  "variables": [ ... ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `survey` | string | 调查名：`CGSS` / `CHFS` |
| `year` | integer | 调查年份 |
| `dataset` | string | 数据集类型（见下表） |
| `source_file` | string | 原始 .dta 文件相对路径 |
| `n_variables` | integer | 变量总数 |
| `n_observations` | integer | 观测值数量 |
| `extracted_at` | string | ETL 提取时间（ISO 8601） |
| `etl_version` | string | ETL 脚本版本（当前 1.1） |
| `variables` | array | 变量元数据数组 |

## dataset 字段取值

| survey | dataset | 说明 |
|---|---|---|
| CGSS | `main` | CGSS 每年单文件，统一标 main |
| CHFS | `household` | 家户数据（家庭级变量） |
| CHFS | `master` | 户主数据（2011-2019） |
| CHFS | `individual` | 个人数据（家庭成员级） |
| CHFS | `master_household` | 2021 户主家庭级数据 |
| CHFS | `master_individual` | 2021 户主个人级数据 |

**注意**：CHFS 2017/2019 的 master 表观测数与 individual 一致（个人级），这是数据本身特点。

## 单变量结构

```json
{
  "varname": "a2",
  "dataset": "main",
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
  "topic_tags": ["demographic"],
  "cross_year_match": {
    "same_var": ["CGSS:2003:main:a2", "CGSS:2005:main:qa2_01"]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `varname` | string | ✓ | Stata 变量名 |
| `dataset` | string | ✓ | 数据集类型（继承自顶层） |
| `label` | string | ✓ | 变量标签（中文） |
| `label_en` | string | | 英文标签（如有） |
| `vtype` | string | ✓ | `numeric` / `string` |
| `format` | string | | Stata 显示格式 |
| `valuelabels` | object | | 取值→标签映射 |
| `missing_rules` | object | | 缺失值规则 |
| `topic_tags` | array | | 主题标签 |
| `cross_year_match` | object | | 跨年同义变量映射 |

## SQLite 主键

```
PRIMARY KEY (survey, year, dataset, varname)
```

四段主键，支持 CHFS 每 wave 多 dataset 结构。CGSS 旧 JSON 无 dataset 字段时 build_sqlite 自动回填 `"main"`。

## 缺失值规则

```json
"missing_rules": {
  "system": [-1, -2, -3],    // 系统缺失
  "user": [97, 98, 99]        // 用户定义
}
```

CGSS 常见缺失码：`-1` 不适用 / `-2` 拒答 / `-3` 不知道。
CHFS 缺失码体系不同（`-3` 不适用 / `-8` 无人回答等），且负值可能为正常值（负收入/负资产），本项目**不自动推断**，留空待手工补。

## 主题标签体系（14 类）

### 基础 10 类（CGSS/CHFS 通用）

| Tag | 覆盖范围 |
|---|---|
| `demographic` | 性别、年龄、民族、户口、婚姻 |
| `education` | 教育程度、学历 |
| `income` | 个人/家庭收入 |
| `labor` | 就业、职业、工时 |
| `health` | 自评健康、就医、保险 |
| `family` | 家庭结构、子女、家务 |
| `political` | 政治面貌、参与 |
| `trust` | 社会信任 |
| `subjective` | 主观阶层、幸福感 |
| `attitude` | 价值观、态度 |

### CHFS 特色 4 类（Phase 4 新增）

| Tag | 覆盖范围 |
|---|---|
| `finance` | 股票、基金、债券、理财、金融投资 |
| `credit` | 信贷、借款、负债、贷款、抵押 |
| `asset` | 房产、资产、财富、净资产、存款 |
| `housing` | 住房状况、面积、房贷、房产 |

## Tag 键格式

- CGSS：3 段 `CGSS:*:varname`（通配符跨年）
- CHFS：4 段 `CHFS:*:dataset:varname`（通配符跨年，含 dataset）

build_sqlite 解析时按 (survey, dataset) 分组匹配 varname_lower。

---

_详细实施进度见 [PLAN.md](../PLAN.md)_
