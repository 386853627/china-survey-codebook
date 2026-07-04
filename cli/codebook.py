#!/usr/bin/env python3
"""
China Survey Codebook — CLI 检索工具

命令：
    search <keyword> [--survey S] [--year Y] [--tag T]
    variable <survey> <year> <varname>
    compare <varname> --years Y1,Y2,...
    export --tag T [--format json|csv]
    surveys

Phase 3 将实现完整逻辑，此处为占位。
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="China Survey Codebook CLI")
    subparsers = parser.add_subparsers(dest="command")

    # search
    p_search = subparsers.add_parser("search", help="按关键词搜索变量")
    p_search.add_argument("keyword")
    p_search.add_argument("--survey", default=None)
    p_search.add_argument("--year", type=int, default=None)
    p_search.add_argument("--tag", default=None)

    # variable
    p_var = subparsers.add_parser("variable", help="查看变量详情")
    p_var.add_argument("survey")
    p_var.add_argument("year", type=int)
    p_var.add_argument("varname")

    # compare
    p_cmp = subparsers.add_parser("compare", help="跨年对比")
    p_cmp.add_argument("varname")
    p_cmp.add_argument("--years", required=True, help="逗号分隔年份，或 all")

    # export
    p_exp = subparsers.add_parser("export", help="按主题导出")
    p_exp.add_argument("--tag", required=True)
    p_exp.add_argument("--format", default="json", choices=["json", "csv"])

    # surveys
    subparsers.add_parser("surveys", help="列出所有调查年份")

    args = parser.parse_args()
    print(f"[TODO] Phase 3 实现: {args}")


if __name__ == "__main__":
    main()
