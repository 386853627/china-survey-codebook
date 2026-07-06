#!/usr/bin/env python3
"""
build_mapping.py — 生成跨年/跨调查同义变量映射（四段主键版）

算法: varname 精确匹配。同名变量归为一组，按 (survey, dataset) 分组去重，
出现在 ≥2 个 (survey, year, dataset) 组合的才纳入。
matches 格式: "survey:year:dataset:varname"（4 段）

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
        if os.path.basename(f) not in ("variable_mapping.json",
                                       "cross_survey_mapping.json")
    )
    if not json_files:
        raise FileNotFoundError(f"未找到 JSON: {json_dir}")

    # varname -> [(survey, year, dataset, label), ...]
    index = defaultdict(list)

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        survey = data["survey"]
        year = data["year"]
        dataset = data.get("dataset", "main")
        for v in data["variables"]:
            v_dataset = v.get("dataset", dataset)
            index[v["varname"]].append((survey, year, v_dataset, v.get("label", "")))

    mappings = []
    for varname, occurrences in index.items():
        # 按 (survey, dataset) 去重统计年份数，避免 CHFS 同名跨 dataset 虚高
        # 但 matches 保留全部 (survey, year, dataset) 记录
        unique_keys = {(s, ds) for s, _, ds, _ in occurrences}
        # 只在出现在 ≥2 条记录的才纳入
        if len(occurrences) < 2:
            continue
        # label 取频次最高（空 label 排除）
        labels = [l for _, _, _, l in occurrences if l]
        canonical_label = Counter(labels).most_common(1)[0][0] if labels else ""
        # matches 按年排序，4 段键
        occurrences_sorted = sorted(occurrences, key=lambda x: (x[1], x[0], x[2]))
        matches = [f"{s}:{y}:{ds}:{varname}" for s, y, ds, _ in occurrences_sorted]
        # n_years 改为去重年份数（同 survey 同 dataset 跨年才算）
        n_records = len(occurrences_sorted)
        mappings.append({
            "canonical_name": varname,
            "label": canonical_label,
            "n_records": n_records,
            "n_surveys": len({s for s, _, _, _ in occurrences}),
            "matches": matches,
        })

    # 按 n_records 降序，再按 canonical_name
    mappings.sort(key=lambda m: (-m["n_records"], m["canonical_name"]))

    output_data = {
        "description": "cross-survey variable mapping (varname exact match)",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "algorithm": "varname exact match; matches format: survey:year:dataset:varname",
        "n_mappings": len(mappings),
        "mappings": mappings,
    }

    os.makedirs(os.path.dirname(output), exist_ok=True) if os.path.dirname(output) else None
    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"生成 {len(mappings)} 条跨年/跨调查映射")
    print(f"覆盖记录最多的变量 top 5:")
    for m in mappings[:5]:
        print(f"  {m['canonical_name']}: {m['label']} ({m['n_records']}条, {m['n_surveys']}个调查)")
    print(f"已写入: {output}")


def main():
    parser = argparse.ArgumentParser(description="生成跨年/跨调查变量映射")
    parser.add_argument("--json-dir", default="data/codebook", help="JSON 输入目录")
    parser.add_argument("--output", default="data/variable_mapping.json", help="输出路径")
    args = parser.parse_args()
    build(args.json_dir, args.output)


if __name__ == "__main__":
    main()
