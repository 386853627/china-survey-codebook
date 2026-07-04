# China Survey Codebook

> Machine-readable codebook metadata library for Chinese social science surveys — designed for AI agent consumption.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data: CGSS](https://img.shields.io/badge/Data-CGSS-blue.svg)](http://cgss.ruc.edu.cn/)
[![Status: WIP](https://img.shields.io/badge/Status-WIP-orange.svg)]()

## 这是什么

一个把 CGSS、CFPS 等中国全国性社会科学调查的 codebook 转换为**机器可读 JSON** 的项目，配以 **SQLite 索引** 和 **CLI 检索工具**，让 AI agent 能：

1. 根据研究问题，跨年份/跨调查推荐可用变量
2. 获取变量的取值标签、缺失值规则等元数据
3. 据此生成准确的 Stata 数据处理与计量分析代码

## 为什么需要

社会学/经济学研究者用 CGSS、CFPS 时痛点：
- codebook 是 PDF 或网页，AI 读不了
- 变量名跨年变化（`a2` → `b2`），难追踪
- 缺失值编码（-1/-2/-3, 97/98/99）不写清就 recode 出错
- AI agent 不知道某变量某年是否存在，瞎编代码

本项目把 codebook 变成结构化元数据层，解决以上问题。

## 项目结构

```
china-survey-codebook/
├── cgss/                      # 原始 .dta（gitignored，受使用协议保护）
├── data/
│   ├── codebook/              # 元数据 JSON（每年一个文件）
│   │   └── CGSS{year}.json
│   ├── codebook.db            # SQLite 索引（从 JSON 构建）
│   └── variable_mapping.json  # 跨年/跨调查变量映射
├── etl/
│   ├── extract_metadata.py    # Python ETL（pandas 读取 .dta → JSON）
│   └── build_sqlite.py        # JSON → SQLite 索引
├── cli/
│   └── codebook.py            # 检索 CLI 工具
├── tags/
│   └── topic_tags.json        # 变量主题标签
├── docs/
│   ├── SCHEMA.md              # JSON Schema 文档
│   └── USAGE.md               # 使用说明
├── PLAN.md                    # 实施计划
└── README.md
```

## 数据覆盖

### CGSS（中国综合社会调查）

| 年份 | 状态 |
|---|---|
| 2003, 2005, 2006, 2008 | 待入库 |
| 2010, 2011, 2012, 2013 | 待入库 |
| 2015, 2017, 2018, 2021, 2023 | 待入库 |

### CFPS（中国家庭追踪调查）

- 待接入

## 快速开始

```bash
# 克隆
git clone https://github.com/386853627/china-survey-codebook.git
cd china-survey-codebook

# 搜索变量
python cli/codebook.py search "性别"

# 查看变量详情
python cli/codebook.py variable CGSS 2010 a2

# 跨年对比
python cli/codebook.py compare a2 --years 2003,2010,2018
```

> ⚠️ **数据协议**：本项目**不含原始 .dta 数据**。CGSS/CFPS 数据需自行向数据发布方申请使用权限。

## 许可证

- **代码与元数据**：MIT License
- **原始调查数据**：归 CGSS/CFPS 项目方所有，本仓库不包含

## 致谢

- [CGSS](http://cgss.ruc.edu.cn/) — 中国人民大学社会调查中心
- [CFPS](https://www.isss.pku.edu.cn/cfps/) — 北京大学中国社会科学调查中心

## 进度

详见 [PLAN.md](./PLAN.md)。当前处于 Phase 1（Schema 设计 + ETL 试点）。

---

_本项目作为社会学计算社会科学研究的 AI 辅助基础设施，欢迎社区贡献。_
