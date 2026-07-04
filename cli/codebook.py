#!/usr/bin/env python3
"""
China Survey Codebook — CLI 检索工具

命令:
    search <keyword> [--survey S] [--year Y] [--tag T]
    variable <survey> <year> <varname>
    compare <varname> --years Y1,Y2,...|all
    export --tag T [--format json|csv]
    surveys

全局参数:
    --json              输出 JSON（供 AI agent 消费）
    --db PATH           SQLite 路径（默认 data/codebook.db）
    --codebook-dir PATH JSON 目录（默认 data/codebook，variable 命令回读用）
"""

import argparse
import csv
import io
import json
import os
import sqlite3
import sys


# ---------- 工具函数 ----------

def connect_db(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def parse_tags(tags_json: str) -> list:
    """解析 topic_tags JSON 字符串为 list。"""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def load_json_variable(codebook_dir: str, survey: str, year: int, varname: str) -> dict:
    """从年份 JSON 文件回读单变量完整信息（missing_rules/cross_year_match 等 DB 未存的字段）。"""
    json_path = os.path.join(codebook_dir, f"{survey}{year}.json")
    if not os.path.exists(json_path):
        # 尝试小写
        json_path = os.path.join(codebook_dir, f"{survey.lower()}{year}.json")
    if not os.path.exists(json_path):
        return {}
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for v in data.get("variables", []):
        if v["varname"] == varname:
            return v
    return {}


def print_json(obj):
    """输出 JSON 到 stdout。"""
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def print_table(rows: list, columns: list, headers: list = None):
    """简易表格输出（不依赖外部库）。rows 为 dict 列表，columns 为键名。"""
    if not rows:
        print("(无结果)")
        return
    if headers is None:
        headers = columns
    # 计算列宽
    widths = []
    for i, col in enumerate(columns):
        w = max(
            len(str(headers[i])),
            max(len(str(r.get(col, ""))) for r in rows) if rows else 0
        )
        widths.append(min(w, 60))  # 限制最大宽度
    # 打印表头
    header_line = " | ".join(str(h)[:w].ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-+-".join("-" * w for w in widths))
    # 打印行
    for r in rows:
        line = " | ".join(str(r.get(col, ""))[:w].ljust(w) for col, w in zip(columns, widths))
        print(line)


# ---------- 子命令实现 ----------

def cmd_search(args, conn):
    """按关键词搜索变量。"""
    keyword = args.keyword
    sql = """
        SELECT v.survey, v.year, v.varname, v.label, v.label_en, v.topic_tags
        FROM variables v
        WHERE 1=1
    """
    params = []
    if args.tag:
        sql += " AND v.topic_tags LIKE ?"
        params.append(f'%"{args.tag}"%')
    if args.survey:
        sql += " AND v.survey = ?"
        params.append(args.survey)
    if args.year:
        sql += " AND v.year = ?"
        params.append(args.year)
    # FTS 搜索 label/label_en/varname
    sql += """
        AND (
            v.varname LIKE ?
            OR v.label LIKE ?
            OR v.label_en LIKE ?
            OR v.rowid IN (
                SELECT rowid FROM variables_fts
                WHERE variables_fts MATCH ?
            )
        )
        ORDER BY v.survey, v.year, v.varname
        LIMIT 200
    """
    kw_like = f"%{keyword}%"
    fts_query = keyword  # FTS5 直接用关键词
    params.extend([kw_like, kw_like, kw_like, fts_query])

    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    # 解析 topic_tags
    for r in rows:
        r["topic_tags"] = parse_tags(r.get("topic_tags", "[]"))

    if args.json:
        print_json(rows)
    else:
        print(f"找到 {len(rows)} 个变量:")
        print_table(
            rows,
            columns=["survey", "year", "varname", "label", "topic_tags"],
            headers=["调查", "年份", "变量名", "标签", "Tags"],
        )


def cmd_variable(args, conn):
    """查看变量详情。"""
    # 从 DB 取基本信息
    cur = conn.execute(
        "SELECT * FROM variables WHERE survey=? AND year=? AND varname=?",
        (args.survey, args.year, args.varname),
    )
    row = cur.fetchone()
    if not row:
        print(f"[ERROR] 变量不存在: {args.survey} {args.year} {args.varname}", file=sys.stderr)
        sys.exit(1)
    var_data = dict(row)
    var_data["topic_tags"] = parse_tags(var_data.get("topic_tags", "[]"))

    # 从 DB 取取值标签
    cur = conn.execute(
        "SELECT value, label FROM valuelabels WHERE survey=? AND year=? AND varname=? ORDER BY CAST(value AS REAL)",
        (args.survey, args.year, args.varname),
    )
    valuelabels = {r["value"]: r["label"] for r in cur.fetchall()}
    var_data["valuelabels"] = valuelabels

    # 从 JSON 回读 missing_rules / cross_year_match（DB 未存）
    json_var = load_json_variable(args.codebook_dir, args.survey, args.year, args.varname)
    var_data["missing_rules"] = json_var.get("missing_rules", {})
    var_data["cross_year_match"] = json_var.get("cross_year_match", {})

    if args.json:
        print_json(var_data)
    else:
        print(f"=== {var_data['survey']}{var_data['year']} : {var_data['varname']} ===")
        print(f"标签: {var_data.get('label', '')}")
        print(f"英文标签: {var_data.get('label_en', '') or '(空)'}")
        print(f"类型: {var_data.get('vtype', '')}  格式: {var_data.get('format', '')}")
        print(f"主题标签: {', '.join(var_data['topic_tags']) if var_data['topic_tags'] else '(无)'}")
        print(f"源文件: {var_data.get('source_file', '')}")
        if valuelabels:
            print(f"\n取值标签 ({len(valuelabels)} 个):")
            for val, lbl in valuelabels.items():
                print(f"  {val:>6} = {lbl}")
        if var_data["missing_rules"]:
            print(f"\n缺失规则:")
            for k, v in var_data["missing_rules"].items():
                print(f"  {k}: {v}")
        if var_data["cross_year_match"]:
            print(f"\n跨年匹配:")
            for k, v in var_data["cross_year_match"].items():
                print(f"  {k}: {v}")


def cmd_compare(args, conn):
    """跨年对比同一变量。"""
    varname = args.varname
    if args.years.lower() == "all":
        cur = conn.execute(
            "SELECT survey, year, varname, label, label_en, topic_tags FROM variables WHERE varname=? ORDER BY year",
            (varname,),
        )
    else:
        years = [int(y.strip()) for y in args.years.split(",")]
        placeholders = ",".join("?" * len(years))
        cur = conn.execute(
            f"SELECT survey, year, varname, label, label_en, topic_tags FROM variables WHERE varname=? AND year IN ({placeholders}) ORDER BY year",
            [varname] + years,
        )
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        print(f"[ERROR] 未找到变量 {varname}", file=sys.stderr)
        sys.exit(1)

    # 收集每年的 valuelabels
    for r in rows:
        cur2 = conn.execute(
            "SELECT value, label FROM valuelabels WHERE survey=? AND year=? AND varname=? ORDER BY CAST(value AS REAL)",
            (r["survey"], r["year"], r["varname"]),
        )
        r["valuelabels"] = {row["value"]: row["label"] for row in cur2.fetchall()}
        r["topic_tags"] = parse_tags(r.get("topic_tags", "[]"))

    # 检测 label 一致性
    labels = set(r["label"] for r in rows)
    label_consistent = len(labels) == 1

    # 检测 valuelabels 一致性
    vl_sets = [json.dumps(r["valuelabels"], sort_keys=True) for r in rows]
    vl_consistent = len(set(vl_sets)) == 1

    if args.json:
        result = {
            "varname": varname,
            "n_years": len(rows),
            "label_consistent": label_consistent,
            "valuelabels_consistent": vl_consistent,
            "years": {str(r["year"]): {
                "survey": r["survey"],
                "label": r["label"],
                "label_en": r["label_en"],
                "topic_tags": r["topic_tags"],
                "valuelabels": r["valuelabels"],
            } for r in rows},
        }
        print_json(result)
    else:
        print(f"=== {varname} 跨年对比 ({len(rows)} 年) ===")
        print(f"Label 一致: {'是' if label_consistent else '否 ⚠'}")
        print(f"取值标签一致: {'是' if vl_consistent else '否 ⚠'}")
        print()
        print_table(
            rows,
            columns=["year", "label", "topic_tags"],
            headers=["年份", "标签", "Tags"],
        )
        if not label_consistent:
            print("\n[!] Label 跨年不一致，使用时注意:")
            for r in rows:
                print(f"  {r['year']}: {r['label']}")
        if not vl_consistent:
            print("\n[!] 取值标签跨年不一致，使用时注意:")
            for r in rows:
                print(f"  {r['year']}: {r['valuelabels']}")


def cmd_export(args, conn):
    """按主题导出变量。"""
    tag = args.tag
    cur = conn.execute(
        """SELECT v.survey, v.year, v.varname, v.label, v.label_en, v.vtype, v.format, v.topic_tags, v.source_file
           FROM variables v
           WHERE v.topic_tags LIKE ?
           ORDER BY v.survey, v.year, v.varname""",
        (f'%"{tag}"%',),
    )
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["topic_tags"] = parse_tags(r.get("topic_tags", "[]"))
        # 附带 valuelabels
        cur2 = conn.execute(
            "SELECT value, label FROM valuelabels WHERE survey=? AND year=? AND varname=? ORDER BY CAST(value AS REAL)",
            (r["survey"], r["year"], r["varname"]),
        )
        r["valuelabels"] = {row["value"]: row["label"] for row in cur2.fetchall()}

    if args.format == "json":
        result = {
            "tag": tag,
            "n_variables": len(rows),
            "variables": rows,
        }
        print_json(result)
    elif args.format == "csv":
        if not rows:
            print("(无结果)")
            return
        output = io.StringIO()
        # 扁平化：valuelabels 合并为字符串
        flat_rows = []
        for r in rows:
            flat = {
                "survey": r["survey"],
                "year": r["year"],
                "varname": r["varname"],
                "label": r["label"],
                "label_en": r["label_en"],
                "vtype": r["vtype"],
                "format": r["format"],
                "topic_tags": ";".join(r["topic_tags"]),
                "valuelabels": "; ".join(f"{k}={v}" for k, v in r["valuelabels"].items()),
                "source_file": r["source_file"],
            }
            flat_rows.append(flat)
        writer = csv.DictWriter(output, fieldnames=flat_rows[0].keys())
        writer.writeheader()
        writer.writerows(flat_rows)
        print(output.getvalue(), end="")


def cmd_surveys(args, conn):
    """列出所有调查年份。"""
    cur = conn.execute(
        "SELECT survey, year, COUNT(*) as n_vars FROM variables GROUP BY survey, year ORDER BY survey, year"
    )
    rows = [dict(r) for r in cur.fetchall()]
    if args.json:
        print_json(rows)
    else:
        print(f"共 {len(rows)} 个调查年份:")
        print_table(
            rows,
            columns=["survey", "year", "n_vars"],
            headers=["调查", "年份", "变量数"],
        )


# ---------- 主入口 ----------

def main():
    # 公共参数（可放在子命令前或后）
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="输出 JSON 格式（供 AI agent 消费）")
    common.add_argument("--db", default=None, help="SQLite 路径（默认: 相对项目根的 data/codebook.db）")
    common.add_argument("--codebook-dir", default=None, help="JSON 目录（默认: 相对项目根的 data/codebook）")

    parser = argparse.ArgumentParser(
        description="China Survey Codebook CLI — 检索 CGSS/CFPS 变量元数据",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="按关键词搜索变量", parents=[common])
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--survey", default=None, help="调查名（如 CGSS）")
    p_search.add_argument("--year", type=int, default=None, help="年份")
    p_search.add_argument("--tag", default=None, help="主题标签过滤")

    # variable
    p_var = subparsers.add_parser("variable", help="查看变量详情", parents=[common])
    p_var.add_argument("survey", help="调查名（如 CGSS）")
    p_var.add_argument("year", type=int, help="年份")
    p_var.add_argument("varname", help="变量名")

    # compare
    p_cmp = subparsers.add_parser("compare", help="跨年对比同一变量", parents=[common])
    p_cmp.add_argument("varname", help="变量名")
    p_cmp.add_argument("--years", required=True, help="逗号分隔年份（如 2010,2018）或 all")

    # export
    p_exp = subparsers.add_parser("export", help="按主题导出变量", parents=[common])
    p_exp.add_argument("--tag", required=True, help="主题标签")
    p_exp.add_argument("--format", default="json", choices=["json", "csv"], help="输出格式")

    # surveys
    subparsers.add_parser("surveys", help="列出所有调查年份", parents=[common])

    args = parser.parse_args()

    # 推断项目根目录（cli/ 的父目录）
    proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = args.db or os.path.join(proj_root, "data", "codebook.db")
    codebook_dir = args.codebook_dir or os.path.join(proj_root, "data", "codebook")
    args.db = db_path
    args.codebook_dir = codebook_dir

    conn = connect_db(db_path)

    try:
        if args.command == "search":
            cmd_search(args, conn)
        elif args.command == "variable":
            cmd_variable(args, conn)
        elif args.command == "compare":
            cmd_compare(args, conn)
        elif args.command == "export":
            cmd_export(args, conn)
        elif args.command == "surveys":
            cmd_surveys(args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
