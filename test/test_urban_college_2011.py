"""
测试：基于 codebook JSON 库，查询 CHFS 2011 individual 中城镇户口大学生样本数。
条件：城镇户籍（a2022=2，非农业），学历在大专以上（a2012>=6）。

注意：
  - CHFS 2011 JSON 标签存在 GBK 乱码（latin-1 编码问题），需 .encode('latin-1').decode('gbk') 修复
  - a2022/a2012 在 codebook 中无取值标签（valuelabels 为空），编码含义参照问卷/后续年份
  - DTA 读入为 float64 数值（非 category），可直接数值比较
"""
import json
import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CODEBOOK_JSON = PROJECT / "data" / "codebook" / "CHFS2011_individual.json"
DTA_FILE = PROJECT / "chfs" / "chfs2011" / "chfs2011_individual.dta"


def fix_gbk(s: str) -> str:
    """修复 GBK 乱码：latin-1 字节串 -> GBK 解码"""
    try:
        return s.encode("latin-1").decode("gbk")
    except Exception:
        return s


# ── Step 1: 从 JSON codebook 中查找目标变量 ──
print("=" * 60)
print("Step 1: 从 codebook JSON 中查询变量定义")
print("=" * 60)

with open(CODEBOOK_JSON, "r", encoding="utf-8") as f:
    cb = json.load(f)

target_vars = {}
for var in cb["variables"]:
    if var["varname"] in ("a2022", "a2012"):
        var["_label_fixed"] = fix_gbk(var["label"])
        target_vars[var["varname"]] = var
        print(f"\n变量: {var['varname']}")
        print(f"  原始标签 (乱码): {var['label']}")
        print(f"  修复标签 (GBK):  {var['_label_fixed']}")
        print(f"  vtype: {var['vtype']}, format: {var['format']}")
        if var["valuelabels"]:
            print(f"  取值编码:")
            for k, v in sorted(var["valuelabels"].items(), key=lambda x: int(x[0])):
                print(f"    {k} = {fix_gbk(v)}")
        else:
            print(f"  取值编码: (空 — codebook 未记录)")

# 编码说明（基于 CHFS 问卷设计 + 后续年份对照）
print("\n编码说明 (基于问卷设计 + 后续年份对照):")
print("  a2022 是否农业户口: 1=是(农业), 2=否(非农业/城镇)")
print("  a2012 文化程度: 1=没上过学 ... 6=大专/高职, 7=本科, 8=硕士, 9=博士")

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

RURAL_CODE = 1   # 农业户口
URBAN_CODE = 2   # 非农业户口（城镇）
COLLEGE_MIN = 6  # 大专/高职及以上

print(f"\n筛选条件:")
print(f"  城镇户籍: a2022 == {URBAN_CODE} (非农业)")
print(f"  大专以上: a2012 >= {COLLEGE_MIN} (6=大专, 7=本科, 8=硕士, 9=博士)")

# 分布
total = len(df)
print(f"\n--- 户口类型分布 ---")
for val, cnt in df["a2022"].value_counts(dropna=False).sort_index().items():
    tag = "农业" if val == 1.0 else ("城镇" if val == 2.0 else "未知")
    pct = cnt / total * 100
    print(f"  {val:g} ({tag}): {cnt:>7,} ({pct:5.1f}%)")
nan_h = df["a2022"].isna().sum()
if nan_h:
    print(f"  缺失: {nan_h:>7,}")

print(f"\n--- 学历分布 ---")
edu_labels = {1:"没上过学",2:"小学",3:"初中",4:"高中",5:"中专/职高",
              6:"大专/高职",7:"大学本科",8:"硕士",9:"博士"}
for val, cnt in df["a2012"].value_counts(dropna=False).sort_index().items():
    if pd.isna(val):
        continue
    tag = edu_labels.get(int(val), f"编码{val:g}")
    pct = cnt / total * 100
    print(f"  {val:g} ({tag}): {cnt:>7,} ({pct:5.1f}%)")
nan_e = df["a2012"].isna().sum()
if nan_e:
    print(f"  缺失: {nan_e:>7,}")

# 核心统计
is_urban = df["a2022"] == URBAN_CODE
is_college = df["a2012"] >= COLLEGE_MIN

urban_count = is_urban.sum()
college_count = is_college.sum()
urban_college_count = (is_urban & is_college).sum()

print("\n" + "=" * 60)
print("核心结果: 城镇户口大学生样本数")
print("=" * 60)
print(f"\n  城镇户籍样本数:    {urban_count:>8,}  (占 {urban_count/total*100:.1f}%)")
print(f"  大专以上样本数:    {college_count:>8,}  (占 {college_count/total*100:.1f}%)")
print(f"  城镇大学生 (交集): {urban_college_count:>8,}")
print(f"  占总样本:          {urban_college_count/total*100:.2f}%")
if urban_count > 0:
    print(f"  占城镇户籍:        {urban_college_count/urban_count*100:.2f}%")

# 城镇大学生学历细分
print(f"\n--- 城镇大学生学历细分 ({urban_college_count:,} 人) ---")
urban_college_df = df[is_urban & is_college]
edu_labels = {6:"大专/高职",7:"大学本科",8:"硕士",9:"博士"}
for val, cnt in urban_college_df["a2012"].value_counts().sort_index().items():
    tag = edu_labels.get(int(val), f"编码{val:g}")
    print(f"  {val:g} ({tag}): {cnt:,}")

print("\n完成。未修改任何原始数据。")
