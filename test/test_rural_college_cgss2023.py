"""
测试：基于 codebook JSON 库，查询 CGSS 2023 中农村户口大学生样本数。
条件：农业户口（a18=1），学历大专以上（a7a in 9..13）。

CGSS 2023 codebook 标签正常（UTF-8），取值标签完整。
DTA 读入为 category 字符串（如 "农业户口"），不含数字前缀。
"""
import json
import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CODEBOOK_JSON = PROJECT / "data" / "codebook" / "CGSS2023.json"
DTA_FILE = PROJECT / "cgss" / "CGSS2023.dta"

# ── Step 1: 从 JSON codebook 中查找目标变量 ──
print("=" * 60)
print("Step 1: 从 codebook JSON 中查询变量定义")
print("=" * 60)

with open(CODEBOOK_JSON, "r", encoding="utf-8") as f:
    cb = json.load(f)

target_vars = {}
for var in cb["variables"]:
    if var["varname"] in ("a18", "a7a"):
        target_vars[var["varname"]] = var
        print(f"\n变量: {var['varname']}")
        print(f"  标签: {var['label']}")
        print(f"  取值编码:")
        for code, lbl in sorted(var["valuelabels"].items(), key=lambda x: int(x[0])):
            print(f"    {code} = {lbl}")

# 从 codebook 中提取条件对应的类别字符串
# a18: 1 -> "农业户口"
# a7a: 9,10,11,12,13 -> 大专以上（不含 14=其他）
RURAL_LABEL = target_vars["a18"]["valuelabels"]["1"]  # "农业户口"

COLLEGE_CODES = ["9", "10", "11", "12", "13"]
COLLEGE_LABELS = {target_vars["a7a"]["valuelabels"][c] for c in COLLEGE_CODES}

# ── Step 2: 读取 DTA 数据 ──
print("\n" + "=" * 60)
print("Step 2: 读取 DTA 数据")
print("=" * 60)
print(f"文件: {DTA_FILE}")
print(f"数据集: {cb['survey']} {cb['year']} {cb.get('dataset', 'main')}")
print(f"元数据: {cb['n_observations']:,} obs x {cb['n_variables']} vars")

df = pd.read_stata(DTA_FILE, columns=["a18", "a7a"])
print(f"成功读取: {len(df):,} 行")

# ── Step 3: 条件筛选与统计 ──
print("\n" + "=" * 60)
print("Step 3: 条件筛选与统计")
print("=" * 60)

print(f"\n筛选条件 (基于 codebook 值标签):")
print(f"  农村户籍: a18 == \"{RURAL_LABEL}\"")
print(f"  大专以上: a7a in {sorted(COLLEGE_LABELS)}")

is_rural = df["a18"] == RURAL_LABEL
is_college = df["a7a"].isin(COLLEGE_LABELS)

rural_count = is_rural.sum()
college_count = is_college.sum()
rural_college_count = (is_rural & is_college).sum()
total = len(df)

# 分布
print(f"\n--- 户口类型分布 ---")
for val, cnt in df["a18"].value_counts().items():
    pct = cnt / total * 100
    print(f"  {val}: {cnt:>6,} ({pct:5.1f}%)")
nan_h = df["a18"].isna().sum()
if nan_h:
    print(f"  缺失: {nan_h:>6,}")

print(f"\n--- 学历分布 ---")
for val, cnt in df["a7a"].value_counts().items():
    pct = cnt / total * 100
    print(f"  {val}: {cnt:>6,} ({pct:5.1f}%)")
nan_e = df["a7a"].isna().sum()
if nan_e:
    print(f"  缺失: {nan_e:>6,}")

# ── 核心结果 ──
print("\n" + "=" * 60)
print("核心结果: 农村户口大学生样本数")
print("=" * 60)
print(f"\n  农业户口样本数:    {rural_count:>6,}  (占 {rural_count/total*100:.1f}%)")
print(f"  大专以上样本数:    {college_count:>6,}  (占 {college_count/total*100:.1f}%)")
print(f"  农村大学生 (交集): {rural_college_count:>6,}")
print(f"  占总样本:          {rural_college_count/total*100:.2f}%")
if rural_count > 0:
    print(f"  占农业户口:        {rural_college_count/rural_count*100:.2f}%")

# 学历细分
print(f"\n--- 农村大学生学历细分 ({rural_college_count:,} 人) ---")
rural_college_df = df[is_rural & is_college]
for val, cnt in rural_college_df["a7a"].value_counts().items():
    print(f"  {val}: {cnt:,}")

print("\n完成。未修改任何原始数据。")
