# 使用说明

> 本文档将在 Phase 3 完成 CLI 工具后补充。以下为设计预览。

## CLI 工具：`cli/codebook.py`

### 安装

```bash
# 无需安装，直接运行（依赖 Python 3.10+）
python cli/codebook.py --help
```

### 命令

```bash
# 1. 搜索变量（按关键词）
python cli/codebook.py search "性别"
python cli/codebook.py search "income" --survey CGSS --year 2010
python cli/codebook.py search "教育" --tag education

# 2. 查看变量详情
python cli/codebook.py variable CGSS 2010 a2
# 输出：label, valuelabels, missing_rules, topic_tags, cross_year_match

# 3. 跨年对比
python cli/codebook.py compare a2 --years 2003,2010,2018,2023
python cli/codebook.py compare a2 --years all

# 4. 按主题导出
python cli/codebook.py export --tag demographic --format json
python cli/codebook.py export --tag income --format csv

# 5. 列出所有调查年份
python cli/codebook.py surveys
```

### AI Agent 集成

AI agent 通过 CLI 获取结构化元数据：

```
# 伪代码
1. search("教育") → 得到变量列表
2. search("收入") → 得到变量列表
3. variable(CGSS, 2010, a7a) → 得到取值标签和缺失规则
4. compare(a7a, all) → 得到跨年可用性
5. 据此生成 Stata do 文件
```

---

_Phase 3 完成后更新本文档_
