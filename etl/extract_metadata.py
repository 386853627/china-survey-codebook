#!/usr/bin/env python3
"""
extract_metadata.py — CGSS/CFPS codebook ETL 主脚本

用 pandas.read_stata 读取 .dta 文件，提取变量元数据，
输出符合 docs/SCHEMA.md 规范的 JSON 文件。

用法：
    python etl/extract_metadata.py <year> <dta_path> [--output data/codebook/]
    python etl/extract_metadata.py 2010 cgss/CGSS2010.dta

Phase 1 将实现完整逻辑，此处为占位。
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Extract codebook metadata from .dta")
    parser.add_argument("year", type=int)
    parser.add_argument("dta_path")
    parser.add_argument("--output", default="data/codebook/")
    parser.add_argument("--survey", default="CGSS")
    args = parser.parse_args()
    print(f"[TODO] Phase 1 实现: {args}")


if __name__ == "__main__":
    main()
