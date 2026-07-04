# JSON Schema — Codebook 元数据格式

> 本文档定义 `data/codebook/CGSS{year}.json` 的结构规范。

## 顶层结构（单年份文件）

```json
{
  "survey": "CGSS",
  "year": 2010,
  "source_file": "cgss/CGSS2010.dta",
  "n_variables": 700,
  "n_observations": 11783,
  "extracted_at": "2026-07-04T17:00:00+08:00",
  "etl_version": "1.0",
  "variables": [ ... ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `survey` | string | 调查名，如 `CGSS` / `CFPS` |
| `year` | integer | 调查年份 |
| `source_file` | string | 原始 .dta 文件相对路径 |
| `n_variables` | integer | 变量总数 |
| `n_observations` | integer | 观测值数量 |
| `extracted_at` | string | ETL 提取时间（ISO 8601） |
| `etl_version` | string | ETL 脚本版本 |
| `variables` | array | 变量元数据数组 |

## 单变量结构

```json
{
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
    "same_var": ["CGSS2003:a2", "CGSS2005:a2"]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `varname` | string | ✓ | Stata 变量名 |
| `label` | string | ✓ | 变量标签（中文） |
| `label_en` | string | | 英文标签（如有） |
| `vtype` | string | ✓ | `numeric` / `string` |
| `format` | string | | Stata 显示格式 |
| `valuelabels` | object | | 取值→标签映射 |
| `missing_rules` | object | | 缺失值规则 |
| `topic_tags` | array | | 主题标签 |
| `cross_year_match` | object | | 跨年同义变量映射 |

## 缺失值规则

```json
"missing_rules": {
  "system": [-1, -2, -3],    // 系统缺失（未回答/不适用）
  "user": [97, 98, 99]        // 用户定义（拒答/不知道/其他）
}
```

CGSS 常见缺失码：
- `-1` 不适用
- `-2` 拒答
- `-3` 不知道
- `97`/`98`/`99` 部分题目的拒答/不知道编码

## 主题标签体系（粗粒度）

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

---

_详细实施进度见 [PLAN.md](../PLAN.md)_
