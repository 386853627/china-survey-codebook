#!/usr/bin/env python3
"""
extract_metadata.py — CGSS/CFPS codebook ETL 主脚本

用 pandas.read_stata 读取 .dta 文件元数据，输出符合 docs/SCHEMA.md 的 JSON。

用法:
    python etl/extract_metadata.py <year> <dta_path> [--output data/codebook/] [--survey CGSS]
    python etl/extract_metadata.py 2010 cgss/CGSS2010.dta
"""

import argparse
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# Stata 数值类型代码 -> vtype 判断
# b=byte, h=short, i=int, l=long, f=float, d=double (数值)
# O=string (旧版), L=long string (Stata 13+ 用 strN)
STRING_TYPE_CODES = {"O", "L"}


def _value_to_str(val) -> str:
    """Stata 取值标签的 key 转 JSON 友好字符串。numpy 标量 -> Python 标量 -> str。"""
    if isinstance(val, np.generic):
        val = val.item()
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def _infer_vtype(type_code: str) -> str:
    """Stata typlist 代码 -> vtype (numeric/string)。"""
    return "string" if type_code in STRING_TYPE_CODES else "numeric"


def extract_metadata(dta_path: str, year: int, survey: str = "CGSS") -> dict:
    """从 .dta 提取元数据，返回 SCHEMA.md 规范的字典。"""
    if not os.path.isfile(dta_path):
        raise FileNotFoundError(f"DTA 文件不存在: {dta_path}")

    reader = pd.read_stata(dta_path, iterator=True)
    try:
        var_labels = reader.variable_labels()       # {varname: 中文label}
        value_label_sets = reader.value_labels()    # {labelset_name: {value: label}}
        varlist = reader._varlist
        lbllist = reader._lbllist
        typlist = reader._typlist
        fmtlist = reader._fmtlist
        nobs = reader._nobs
    finally:
        # pandas 3.x 无 close()，用上下文管理器或显式释放
        if hasattr(reader, "_close_file"):
            reader._close_file()

    variables = []
    for i, varname in enumerate(varlist):
        lblset_name = lbllist[i] if i < len(lbllist) else ""
        # 取值标签：从 labelset 取该变量的全部取值
        valuelabels = {}
        if lblset_name and lblset_name in value_label_sets:
            raw = value_label_sets[lblset_name]
            valuelabels = {_value_to_str(k): v for k, v in raw.items()}

        variables.append({
            "varname": varname,
            "label": var_labels.get(varname, ""),
            "label_en": "",
            "vtype": _infer_vtype(typlist[i] if i < len(typlist) else ""),
            "format": fmtlist[i] if i < len(fmtlist) else "",
            "valuelabels": valuelabels,
            "missing_rules": {"system": [], "user": []},
            "topic_tags": [],
            "cross_year_match": {},
        })

    # source_file 用项目内相对路径
    return {
        "survey": survey,
        "year": year,
        "source_file": dta_path.replace("\\", "/"),
        "n_variables": len(varlist),
        "n_observations": nobs,
        "extracted_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "etl_version": "1.0",
        "variables": variables,
    }


def verify(output: dict, dta_path: str) -> None:
    """打印验证报告到 stdout。"""
    reader = pd.read_stata(dta_path, iterator=True)
    reader.variable_labels()  # 触发 header 读取
    expected_nvars = len(reader._varlist)
    expected_nobs = reader._nobs
    if hasattr(reader, "_close_file"):
        reader._close_file()

    print("\n=== 验证报告 ===")
    print(f"变量数: JSON={output['n_variables']}  Stata={expected_nvars}  "
          f"{'OK' if output['n_variables'] == expected_nvars else 'MISMATCH'}")
    print(f"观测数: JSON={output['n_observations']}  Stata={expected_nobs}  "
          f"{'OK' if output['n_observations'] == expected_nobs else 'MISMATCH'}")

    # 抽查 a2 / a7a
    print("\n--- 抽查变量 ---")
    by_name = {v["varname"]: v for v in output["variables"]}
    for name in ["a2", "a7a", "a3a"]:
        v = by_name.get(name)
        if v:
            print(f"{name}: label={v['label']!r}  vtype={v['vtype']}  "
                  f"fmt={v['format']}  valuelabels={len(v['valuelabels'])}条")
            if v["valuelabels"]:
                sample = list(v["valuelabels"].items())[:3]
                print(f"    取值样例: {sample}")
        else:
            print(f"{name}: 不存在")

    # labelset 覆盖统计
    has_lbl = sum(1 for v in output["variables"] if v["valuelabels"])
    print(f"\n取值标签覆盖: {has_lbl}/{output['n_variables']} 变量有取值标签")

    # 字段完整性
    required = {"varname", "label", "label_en", "vtype", "format",
                "valuelabels", "missing_rules", "topic_tags", "cross_year_match"}
    missing_fields = [v["varname"] for v in output["variables"]
                      if not required.issubset(v.keys())]
    print(f"字段完整性: {'OK' if not missing_fields else f'MISSING in {missing_fields[:5]}'}")
    print("=== 验证结束 ===\n")


def main():
    parser = argparse.ArgumentParser(description="Extract codebook metadata from .dta")
    parser.add_argument("year", type=int, help="调查年份")
    parser.add_argument("dta_path", help=".dta 文件路径")
    parser.add_argument("--output", default="data/codebook/", help="输出目录")
    parser.add_argument("--survey", default="CGSS", help="调查名")
    args = parser.parse_args()

    print(f"提取中: {args.survey} {args.year} <- {args.dta_path}")
    output = extract_metadata(args.dta_path, args.year, args.survey)

    os.makedirs(args.output, exist_ok=True)
    out_file = os.path.join(args.output, f"{args.survey}{args.year}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已写入: {out_file}  ({output['n_variables']} 变量, {output['n_observations']} 观测)")
    verify(output, args.dta_path)


if __name__ == "__main__":
    main()
