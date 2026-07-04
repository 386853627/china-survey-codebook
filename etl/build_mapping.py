#!/usr/bin/env python3
"""
build_mapping.py — 生成跨年/跨调查同义变量映射

算法: varname 精确匹配。同名变量归为一组，出现在 ≥2 年的才纳入。
canonical_name = varname 本身；label 取出现频次最高的。

用法:
    python etl/build_mapping.py
    python etl/build_mapping.py --json-dir data/codebook --output data/variable_mapping.json
"""

import argparse
import glob
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone


def build(json_dir: str, output: str) -> None:
    json_files = sorted(
        f for f in glob.glob(os.path.join(json_dir, "*.json"))
        if os.path.basename(f) != "variable_mapping.json"
    )
    if not json_files:
        raise FileNotFoundError(f"未找到 JSON: {json_dir}")

    # varname -> [(survey, year, label), ...]
    index = defaultdict(list)

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        survey = data["survey"]
        year = data["year"]
        for v in data["variables"]:
            index[v["varname"]].append((survey, year, v.get("label", "")))

    mappings = []
    for varname, occurrences in index.items():
        if len(occurrences) < 2:
            continue  # 只出现在一年的不纳入跨年映射
        # label 取频次最高（空 label 排除）
        labels = [l for _, _, l in occurrences if l]
        canonical_label = Counter(labels).most_common(1)[0][0] if labels else ""
        # matches 按年份排序
        occurrences_sorted = sorted(occurrences, key=lambda x: x[1])
        matches = [f"{s}:{y}:{varname}" for s, y, _ in occurrences_sorted]
        mappings.append({
            "canonical_name": varname,
            "label": canonical_label,
            "n_years": len(occurrences_sorted),
            "matches": matches,
        })

    # 按 n_years 降序，再按 canonical_name
    mappings.sort(key=lambda m: (-m["n_years"], m["canonical_name"]))

    output_data = {
        "survey": "cross-survey variable mapping",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "algorithm": "varname exact match",
        "n_mappings": len(mappings),
        "mappings": mappings,
    }

    os.makedirs(os.path.dirname(output), exist_ok=True) if os.path.dirname(output) else None
    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"生成 {len(mappings)} 条跨年映射")
    print(f"覆盖年份最多的变量 top 5:")
    for m in mappings[:5]:
        print(f"  {m['canonical_name']}: {m['label']} ({m['n_years']}年)")
    print(f"已写入: {output}")


def main():
    parser = argparse.ArgumentParser(description="生成跨年变量映射")
    parser.add_argument("--json-dir", default="data/codebook", help="JSON 输入目录")
    parser.add_argument("--output", default="data/variable_mapping.json", help="输出路径")
    args = parser.parse_args()
    build(args.json_dir, args.output)


if __name__ == "__main__":
    main()
