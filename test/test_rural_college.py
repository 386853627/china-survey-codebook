"""
测试：基于 codebook JSON 库，查询 CHFS 2021 individual 中农户大学生样本数。
条件：户口为农村户籍（a2022=农业），学历在大专以上（a2012>=大专/高职）。
说明：pandas read_stata 读入时变量值带标签 (如 "1 农业")，直接用字符串匹配。
"""
import json
import pandas as pd
from pathlib import Path

# 路径
PROJECT = Path(__file__).resolve().parent.parent
CODEBOOK_JSON = PROJECT / "data" / "codebook" / "CHFS2021_individual.json"
DTA_FILE = PROJECT / "chfs" / "chfs2021" / "chfs2021_individual.dta"

# ── Step 1: 从 JSON codebook 中查找目标变量 ──
print("=" * 60)
print("Step 1: 从 codebook JSON 中查询变量定义")
print("=" * 60)

with open(CODEBOOK_JSON, "r", encoding="utf-8") as f:
    cb = json.load(f)

target_vars = {}
for var in cb["variables"]:
    if var["varname"] in ("a2022", "a2012"):
        target_vars[var["varname"]] = var
        print(f"\n变量: {var['varname']}")
        print(f"  标签: {var['label']}")
        print(f"  Stata 值标签 (code -> label):")
        for val_code, val_label in sorted(var["valuelabels"].items(), key=lambda x: int(x[0])):
            print(f"    {val_code} -> \"{val_label}\"")

# 从 codebook 中提取条件对应的类别字符串
# a2022: 1 -> "1 农业"
# a2012: 6,7,8,9 -> "6 大专/高职", "7 大学本科", "8 硕士研究生", "9 博士研究生"
RURAL_LABEL = "1 农业"
COLLEGE_LABELS = {
    "6 大专/高职",
    "7 大学本科",
    "8 硕士研究生",
    "9 博士研究生",
}

# ── Step 2: 读取 DTA 数据 ──
print("\n" + "=" * 60)
print("Step 2: 读取 DTA 数据")
print("=" * 60)
print(f"文件: {DTA_FILE}")
print(f"数据集: {cb['survey']} {cb['year']} {cb['dataset']}")
print(f"元数据: {cb['n_observations']:,} obs x {cb['n_variables']} vars")

df = pd.read_stata(DTA_FILE, columns=["a2022", "a2012"])
print(f"成功读取: {len(df):,} 行, dtype: {df.dtypes.to_dict()}")

# ── Step 3: 条件筛选与统计 ──
print("\n" + "=" * 60)
print("Step 3: 条件筛选与统计")
print("=" * 60)

print(f"\n筛选条件 (基于 codebook 值标签):")
print(f"  农村户籍: a2022 == \"{RURAL_LABEL}\"")
print(f"  大专以上: a2012 in {sorted(COLLEGE_LABELS)}")

is_rural = df["a2022"] == RURAL_LABEL
is_college = df["a2012"].isin(COLLEGE_LABELS)

rural_count = is_rural.sum()
college_count = is_college.sum()
rural_college_count = (is_rural & is_college).sum()
total = len(df)

print(f"\n--- 分布概况 ---")
print(f"  总样本:               {total:>8,}")
print(f"  农村户籍 (a2022=1):    {rural_count:>8,}  ({rural_count/total*100:5.1f}%)")
print(f"  大专以上 (a2012>=6):   {college_count:>8,}  ({college_count/total*100:5.1f}%)")

print(f"\n--- 户口类型分布 ---")
for val, cnt in df["a2022"].value_counts().items():
    pct = cnt / total * 100
    print(f"  \"{val}\": {cnt:>7,} ({pct:5.1f}%)")
nan_h = df["a2022"].isna().sum()
if nan_h:
    print(f"  缺失: {nan_h:>7,}")

print(f"\n--- 学历分布 ---")
for val, cnt in df["a2012"].value_counts().items():
    pct = cnt / total * 100
    print(f"  \"{val}\": {cnt:>7,} ({pct:5.1f}%)")
nan_e = df["a2012"].isna().sum()
if nan_e:
    print(f"  缺失: {nan_e:>7,}")

# ── 核心结果 ──
print("\n" + "=" * 60)
print("核心结果: 农户大学生样本数")
print("=" * 60)
print(f"\n  农户大学生样本数: {rural_college_count:,}")
print(f"  占总样本:         {rural_college_count/total*100:.2f}%")
if rural_count > 0:
    print(f"  占农村户籍:       {rural_college_count/rural_count*100:.2f}%")

# ── 农户大学生学历细分 ──
print(f"\n--- 农户大学生学历细分 ({rural_college_count:,} 人) ---")
rural_college_df = df[is_rural & is_college]
for val, cnt in rural_college_df["a2012"].value_counts().items():
    print(f"  {val}: {cnt:,}")

print("\n完成。未修改任何原始数据。")
