# 贡献指南

## 如何贡献

### 1. 贡献 codebook 元数据

如果你有其他 CGSS 年份或 CFPS/CLDS 等调查的 .dta 文件：

1. Fork 本仓库
2. 安装依赖：`pip install pandas`
3. 运行 ETL 脚本生成 JSON：
   ```bash
   python etl/extract_metadata.py <year> <dta_path>
   # 例：python etl/extract_metadata.py 2010 cgss/CGSS2010.dta
   ```
4. 提交 `data/codebook/CGSS{year}.json`
5. 发 PR

### 2. 贡献变量标签

在 `tags/topic_tags.json` 的 `variable_tags` 中添加条目：

```json
"CGSS:2010:a2": ["demographic", "gender"]
```

### 3. 贡献代码

- CLI 工具改进
- ETL 脚本优化
- 跨调查变量映射

## 注意事项

- **不要提交原始 .dta 数据**（已在 .gitignore 中排除）
- CGSS/CFPS 数据受使用协议保护，不得公开传播
- 本仓库只含元数据（变量名、标签、取值标签），不含微观数据
