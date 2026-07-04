* ============================================================
* extract_metadata.do
* CGSS Codebook ETL — Stata 侧
* 从 .dta 提取变量元数据，导出为 CSV 供 Python 组装 JSON
* ============================================================
*
* 用法（命令行批量模式）：
*   "D:/Software/Stata19/StataMP-64.exe" /e do "etl/extract_metadata.do" <year> <dta_path> <output_dir>
*
* 例如：
*   "D:/Software/Stata19/StataMP-64.exe" /e do "etl/extract_metadata.do" 2010 "cgss/CGSS2010.dta" "etl/tmp"
*
* 输出（output_dir 下）：
*   - variables_<year>.csv    变量列表（varname, label, vtype, format）
*   - valuelabels_<year>.csv  取值标签（varname, value, label）
*   - meta_<year>.txt         元信息（变量数、观测数）
*
* Phase 1 将实现完整逻辑，此处为占位。
* ============================================================

* TODO: Phase 1 实现
