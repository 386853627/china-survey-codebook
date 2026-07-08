# China Survey Codebook

> Machine-readable codebook metadata library for Chinese social science surveys — designed for AI agent consumption.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data: CGSS](https://img.shields.io/badge/Data-CGSS-blue.svg)](http://cgss.ruc.edu.cn/)
[![Data: CHFS](https://img.shields.io/badge/Data-CHFS-green.svg)](https://chfs.swufe.edu.cn/)
[![Status: Phase 4](https://img.shields.io/badge/Status-Phase_4-brightgreen.svg)]()

## 这是什么

一个把 CGSS、CHFS 等中国全国性社会科学调查的 codebook 转换为**机器可读 JSON** 的项目，配以 **SQLite 索引** 和 **CLI 检索工具**，让 AI agent 能：

1. 根据研究问题，跨年份/跨调查推荐可用变量
2. 获取变量的取值标签、缺失值规则等元数据
3. 据此生成准确的 Stata 数据处理与计量分析代码

## 为什么需要

社会学/经济学研究者用 CGSS、CHFS 时痛点：
- codebook 是 PDF 或网页，AI 读不了
- 变量名跨年变化（CGSS `a2` → `b2`；CHFS `a2003` 性别 vs CGSS `a2` 性别），难追踪
- 缺失值编码（CGSS -1/-2/-3；CHFS -3/-8 等）不写清就 recode 出错
- AI agent 不知道某变量某年是否存在，瞎编代码
- CHFS 每 wave 有 household/master/individual 三个文件，变量归属复杂

本项目把 codebook 变成结构化元数据层，解决以上问题。

## 项目结构

```
china-survey-codebook/
├── cgss/                          # CGSS 原始 .dta（gitignored）
├── chfs/                          # CHFS 原始 .dta（gitignored）
├── data/
│   ├── codebook/                  # 元数据 JSON
│   │   ├── CGSS{year}_main.json
│   │   └── CHFS{year}_{dataset}.json
│   ├── codebook.db                # SQLite 索引（四段主键）
│   ├── variable_mapping.json      # 同名变量跨年/跨调查映射
│   └── cross_survey_mapping.json  # CGSS↔CHFS 异名同义映射
├── etl/
│   ├── extract_metadata.py        # ETL（pandas 读 .dta → JSON）
│   ├── build_sqlite.py            # JSON → SQLite（四段主键）
│   ├── build_mapping.py           # 跨年/跨调查映射生成
│   ├── tag_chfs.py                # CHFS 自动打标
│   └── run_chfs_etl.py            # CHFS 批量 ETL
├── cli/
│   └── codebook.py                # 检索 CLI（5 子命令）
├── tags/
│   └── topic_tags.json            # 变量主题标签（14 类）
├── docs/
│   ├── SCHEMA.md                  # JSON Schema 文档
│   └── USAGE.md                   # 使用说明
├── test/
│   ├── README.md                  # 测试场景说明
│   ├── test_rural_college.py              # CHFS 2021 农村大学生测试
│   ├── test_urban_college_2011.py         # CHFS 2011 城镇大学生测试
│   └── test_rural_college_cgss2023.py     # CGSS 2023 农村大学生测试
└── README.md
```

## 数据覆盖

### CGSS（中国综合社会调查）

13 个 wave（2003-2023），每年单文件，共 **11790 变量**。

### CHFS（中国家庭金融调查）

6 个 wave（2011-2021），每 wave 含 household/master/individual 三类数据（2021 master 拆为户主家庭级 + 户主个人级），共 19 个 .dta 文件，**17025 变量**。

### 合计

**CGSS + CHFS = 28815 变量**，统一 SQLite 索引，四段主键 `(survey, year, dataset, varname)`。

## 快速开始

```bash
# 克隆
git clone https://github.com/386853627/china-survey-codebook.git
cd china-survey-codebook

# 列出所有调查-年份-数据集
python cli/codebook.py surveys

# 搜索变量（跨调查）
python cli/codebook.py search "性别"
python cli/codebook.py search "住房" --survey CHFS --dataset household

# 查看变量详情
python cli/codebook.py variable CGSS 2010 a2
python cli/codebook.py variable CHFS 2017 a2003 --dataset individual

# 跨年对比
python cli/codebook.py compare a2 --years all --survey CGSS

# 按主题导出
python cli/codebook.py export --tag housing --survey CHFS --format json
```

详细用法见 [docs/USAGE.md](docs/USAGE.md)。

> ⚠️ **数据协议**：本项目**不含原始 .dta 数据**。CGSS/CHFS 数据需自行向数据发布方申请使用权限。

## 主题标签体系（14 类）

| Tag | 中文 | 覆盖范围 |
|---|---|---|
| `demographic` | 人口学特征 | 性别、年龄、民族、户口、婚姻 |
| `education` | 教育 | 教育程度、学历 |
| `income` | 收入 | 个人/家庭收入 |
| `labor` | 劳动就业 | 就业、职业、工时 |
| `health` | 健康 | 自评健康、就医、医保 |
| `family` | 家庭 | 家庭结构、子女、家务 |
| `political` | 政治参与 | 政治面貌、参与 |
| `trust` | 社会信任 | 人际信任、制度信任 |
| `subjective` | 主观评价 | 主观阶层、幸福感 |
| `attitude` | 价值观态度 | 社会价值观、态度 |
| `finance` | 金融产品 | 股票、基金、理财（CHFS 特色） |
| `credit` | 信贷负债 | 贷款、借款、抵押（CHFS 特色） |
| `asset` | 资产财富 | 房产、资产、存款（CHFS 特色） |
| `housing` | 住房 | 住房状况、面积、房贷（CHFS 特色） |

## 技术栈

- **ETL**：Python 3.13 + pandas `read_stata`（直接读 .dta 元数据，无 CSV 中间格式）
- **索引**：SQLite + FTS5（unicode61 中文按字分词）
- **CLI**：Python argparse，5 子命令，支持 `--json` 输出供 AI agent 消费
- **主键**：`(survey, year, dataset, varname)` 四段，支持多 dataset 调查

## AI Agent 调用示例

**场景**：研究"住房资产对家庭收入的影响"，AI agent 流程：

```bash
# 1. 找住房变量
python cli/codebook.py search "住房" --survey CHFS --tag housing --json

# 2. 查看取值标签和缺失码
python cli/codebook.py variable CHFS 2017 c2001 --dataset household --json

# 3. 跨年可用性
python cli/codebook.py compare c2002 --years all --survey CHFS --dataset household --json

# 4. 导出 housing 主题全部变量
python cli/codebook.py export --tag housing --survey CHFS --format json

# 5. AI agent 据此生成 Stata do 文件
#    （知道 c2001 取值 0/1，c2002 住房套数，2015-2021 都有）
```

## 测试验证与演示

> 三个端到端测试验证 codebook 元数据在实际研究场景中的可用性。
> 详见 [test/README.md](test/README.md)。

| 测试 | 调查 | 年份 | 场景 | 验证点 |
|---|---|---|---|---|
| CHFS 2021 农村大学生 | CHFS | 2021 | 农业户口 + 大专以上样本量 | 标签正常、取值标签完整、category 读入 |
| CHFS 2011 城镇大学生 | CHFS | 2011 | 非农业户口 + 大专以上样本量 | GBK 乱码修复、取值标签缺失兜底、float64 读入 |
| CGSS 2023 农村大学生 | CGSS | 2023 | 农业户口 + 大专以上样本量 | UTF-8 标签、跨调查户口变量映射 |

**测试 1：CHFS 2021 农村大学生**

从 codebook 查询变量编码 → 读 DTA → 按条件统计，验证元数据完整可用。

```bash
# 从 codebook 查到 a2022（户口）取值：1=农业, 2=非农业, 3=统一居民户口
# 查到 a2012（教育）取值：6=大专/高职, 7=本科, ..., 9=博士
python cli/codebook.py variable CHFS 2021 a2022 --dataset individual
python cli/codebook.py variable CHFS 2021 a2012 --dataset individual
```

```python
# 验证脚本（约 100 行）的核心逻辑
df = pd.read_stata("chfs/chfs2021/chfs2021_individual.dta", columns=["a2022", "a2012"])
is_rural = df["a2022"] == "1 农业"
is_college = df["a2012"].isin({"6 大专/高职", "7 大学本科", "8 硕士研究生", "9 博士研究生"})
rural_college_count = (is_rural & is_college).sum()
# → 成功统计农户大学生样本量，codebook 元数据与 DTA 实际数据一致
```

**测试 2：CHFS 2011 城镇大学生**

验证 label 乱码修复机制（`encode('latin-1').decode('gbk')`）和取值标签缺失时的兜底策略。

```python
# 乱码修复（CHFS 2011/2013 特有）
def fix_gbk(s):
    return s.encode("latin-1").decode("gbk")

# 取值标签缺失时，参照 CHFS 问卷手工指定编码
# a2022: 1=农业, 2=非农业
# a2012: 1..5=中学及以下, 6=大专, 7=本科, 8=硕士, 9=博士
df = pd.read_stata("chfs/chfs2011/chfs2011_individual.dta", columns=["a2022", "a2012"])
is_urban = df["a2022"] == 2
is_college = df["a2012"] >= 6
# → 即使 codebook 元数据不完美，测试场景仍然可执行
```

**测试 3：CGSS 2023 农村大学生**

验证 CGSS 跨调查覆盖，确认 codebook 中 CGSS 和 CHFS 都有对应的户口变量（a18 ↔ a2022）和学历变量（a7a ↔ a2012）。

```python
# CGSS 2023 取值标签无数字前缀，直接字符串比较
# a18: 1=农业户口, 2=非农业户口, 3=居民户口
# a7a: 9=大专, 10=本科, 11=硕士, 12=博士, 13=博士(与 12 区分)
df = pd.read_stata("cgss/CGSS2023.dta", columns=["a18", "a7a"])
is_rural = df["a18"] == "农业户口"
is_college = df["a7a"].isin({"大专", "大学本科", "硕士研究生", "博士"})
# → 与 CHFS 测试形成对照，验证跨调查一致性
```

三个测试覆盖了 2 个调查 × 3 种 DTA 读入行为 × 2 种编码场景，验证了 codebook 元数据在生产研究中的可用性。

## 许可证

- **代码与元数据**：MIT License
- **原始调查数据**：归 CGSS/CHFS 项目方所有，本仓库不包含

## 致谢

- [CGSS](http://cgss.ruc.edu.cn/) — 中国人民大学社会调查中心
- [CHFS](https://chfs.swufe.edu.cn/) — 西南财经大学中国家庭金融调查中心

## 进度

| Phase | 状态 | 内容 |
|---|---|---|
| 1 | ✅ | Schema + ETL 试点（CGSS2010） |
| 2 | ✅ | 全量入库 + SQLite（CGSS 13 年） |
| 3 | ✅ | CLI + Tag 体系（CGSS） |
| 4 | ✅ | CHFS 扩展 + 跨调查映射 + 文档 |

---

_本项目作为社会学计算社会科学研究的 AI 辅助基础设施，欢迎社区贡献。_
