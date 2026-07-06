#!/usr/bin/env python3
"""
run_chfs_etl.py — 批量跑 CHFS 全部 19 个 .dta 的 ETL

遍历 chfs/chfs{year}/ 下的 .dta，按文件名识别 dataset 类型，调用 extract_metadata。
"""
import os
import subprocess
import sys

# CHFS 数据集映射：文件名片段 -> dataset 名
# 2011-2019: household / master / individual
# 2021: household / master_household / master_individual / individual
DATASET_PATTERNS = [
    ("master_household",  "master_household"),
    ("master_individual", "master_individual"),
    ("household",         "household"),
    ("master",            "master"),
    ("individual",        "individual"),
]

def identify_dataset(filename: str) -> str:
    """从文件名识别 dataset 类型。filename 形如 chfs2011_household.dta"""
    name_lower = filename.lower()
    for frag, ds in DATASET_PATTERNS:
        if frag in name_lower:
            return ds
    raise ValueError(f"无法识别 dataset: {filename}")

def extract_year(filename: str) -> int:
    """chfs2011_household.dta -> 2011"""
    # 匹配 chfs 后的 4 位年份
    import re
    m = re.search(r'chfs(\d{4})', filename.lower())
    if not m:
        raise ValueError(f"无法识别年份: {filename}")
    return int(m.group(1))

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chfs_root = os.path.join(project_root, "chfs")
    python_exe = sys.executable
    etl_script = os.path.join(project_root, "etl", "extract_metadata.py")

    if not os.path.isdir(chfs_root):
        print(f"[ERR] chfs 目录不存在: {chfs_root}")
        return 1

    tasks = []
    for wave_dir in sorted(os.listdir(chfs_root)):
        wave_path = os.path.join(chfs_root, wave_dir)
        if not os.path.isdir(wave_path):
            continue
        for fname in sorted(os.listdir(wave_path)):
            if not fname.lower().endswith(".dta"):
                continue
            dta_path = os.path.join(wave_path, fname)
            try:
                year = extract_year(fname)
                dataset = identify_dataset(fname)
            except ValueError as e:
                print(f"[SKIP] {fname}: {e}")
                continue
            tasks.append((year, dataset, dta_path))

    print(f"共 {len(tasks)} 个 .dta 待处理")
    for i, (year, dataset, dta_path) in enumerate(tasks, 1):
        rel_path = os.path.relpath(dta_path, project_root)
        print(f"\n[{i}/{len(tasks)}] {year} {dataset} <- {rel_path}")
        cmd = [python_exe, etl_script, str(year), dta_path,
               "--survey", "CHFS", "--dataset", dataset]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", cwd=project_root)
        # 只打印关键行（已写入/变量数/验证结果）
        for line in result.stdout.splitlines():
            if any(k in line for k in ["已写入", "变量数:", "观测数:", "MISMATCH", "MISSING", "[ERR]"]):
                print(f"  {line}")
        if result.returncode != 0:
            print(f"  [ERR] 退出码 {result.returncode}")
            print(f"  stderr: {result.stderr[:500]}")

    print("\n=== 全部完成 ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
