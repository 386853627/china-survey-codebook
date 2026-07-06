#!/usr/bin/env python3
"""
China Survey Codebook — CLI 检索工具（四段主键版）

主键: (survey, year, dataset, varname)
CGSS dataset=main；CHFS dataset=household/master/individual/master_household/master_individual

命令:
    search <keyword> [--survey S] [--year Y] [--dataset D] [--tag T]
    variable <survey> <year> <varname> [--dataset D]
    compare <varname> --years Y1,Y2,...|all [--survey S] [--dataset D]
    export --tag T [--survey S] [--dataset D] [--format json|csv]
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

# Windows 终端默认 GBK，强制 stdout/stderr UTF-8 避免中文乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ---------- 工具函数 ----------

def connect_db(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def parse_tags(tags_json: str) -> list:
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def load_json_variable(codebook_dir: str, survey: str, year: int,
                       dataset: str, varname: str) -> dict:
    """从年份 JSON 文件回读单变量完整信息（missing_rules/cross_year_match 等 DB 未存的字段）。

    文件命名: {survey}{year}_{dataset}.json（如 CHFS2011_household.json）
    兼容旧 CGSS 文件名 {survey}{year}.json（无 dataset 后缀）。
    """
    # 优先尝试带 dataset 的文件名
    candidates = [
        os.path.join(codebook_dir, f"{survey}{year}_{dataset}.json"),
        os.path.join(codebook_dir, f"{survey.lower()}{year}_{dataset}.json"),
    ]
    # 兼容旧 CGSS JSON（无 dataset 后缀）
    if dataset == "main":
        candidates.extend([
            os.path.join(codebook_dir, f"{survey}{year}.json"),
            os.path.join(codebook_dir, f"{survey.lower()}{year}.json"),
        ])
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for v in data.get("variables", []):
                if v["varname"] == varname:
                    return v
            break
    return {}


def print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def print_table(rows: list, columns: list, headers: list = None):
    if not rows:
        print("(无结果)")
        return
    if headers is None:
        headers = columns
    widths = []
    for i, col in enumerate(columns):
        w = max(
            len(str(headers[i])),
            max(len(str(r.get(col, ""))) for r in rows) if rows else 0
        )
        widths.append(min(w, 60))
    header_line = " | ".join(str(h)[:w].ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        line = " | ".join(str(r.get(col, ""))[:w].ljust(w) for col, w in zip(columns, widths))
        print(line)


# ---------- 子命令实现 ----------

def cmd_search(args, conn):
    keyword = args.keyword
    sql = """
        SELECT v.survey, v.year, v.dataset, v.varname, v.label, v.label_en, v.topic_tags
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
    if args.dataset:
        sql += " AND v.dataset = ?"
        params.append(args.dataset)
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
        ORDER BY v.survey, v.year, v.dataset, v.varname
        LIMIT 200
    """
    kw_like = f"%{keyword}%"
    params.extend([kw_like, kw_like, kw_like, keyword])

    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["topic_tags"] = parse_tags(r.get("topic_tags", "[]"))

    if args.json:
        print_json(rows)
    else:
        print(f"找到 {len(rows)} 个变量:")
        print_table(
            rows,
            columns=["survey", "year", "dataset", "varname", "label"],
            headers=["调查", "年份", "数据集", "变量名", "标签"],
        )


def cmd_variable(args, conn):
    dataset = args.dataset or "main"
    cur = conn.execute(
        "SELECT * FROM variables WHERE survey=? AND year=? AND dataset=? AND varname=?",
        (args.survey, args.year, dataset, args.varname),
    )
    row = cur.fetchone()
    if not row:
        print(f"[ERROR] 变量不存在: {args.survey} {args.year} {dataset} {args.varname}",
              file=sys.stderr)
        sys.exit(1)
    var_data = dict(row)
    var_data["topic_tags"] = parse_tags(var_data.get("topic_tags", "[]"))

    cur = conn.execute(
        "SELECT value, label FROM valuelabels WHERE survey=? AND year=? AND dataset=? AND varname=? "
        "ORDER BY CAST(value AS REAL)",
        (args.survey, args.year, dataset, args.varname),
    )
    valuelabels = {r["value"]: r["label"] for r in cur.fetchall()}
    var_data["valuelabels"] = valuelabels

    json_var = load_json_variable(args.codebook_dir, args.survey, args.year,
                                  dataset, args.varname)
    var_data["missing_rules"] = json_var.get("missing_rules", {})
    var_data["cross_year_match"] = json_var.get("cross_year_match", {})

    if args.json:
        print_json(var_data)
    else:
        print(f"=== {var_data['survey']}{var_data['year']}_{var_data['dataset']} : {var_data['varname']} ===")
        print(f"标签: {var_data.get('label', '')}")
        print(f"英文标签: {var_data.get('label_en', '') or '(空)'}")
        print(f"类型: {var_data.get('vtype', '')}  格式: {var_data.get('format', '')}")
        print(f"主题标签: {', '.join(var_data['topic_tags']) if var_data['topic_tags'] else '(无)'}")
        print(f"源文件: {var_data.get('source_file', '')}")
        if valuelabels:
            print(f"\n取值标签 ({len(valuelabels)} 个):")
            for val, lbl in valuelabels.items():
                print(f"  {val:>6} = {lbl}")
        if var_data["missing_rules"] and (var_data["missing_rules"].get("system") or var_data["missing_rules"].get("user")):
            print(f"\n缺失规则:")
            for k, v in var_data["missing_rules"].items():
                if v:
                    print(f"  {k}: {v}")
        if var_data["cross_year_match"]:
            print(f"\n跨年匹配:")
            for k, v in var_data["cross_year_match"].items():
                print(f"  {k}: {v}")


def cmd_compare(args, conn):
    varname = args.varname
    sql = """
        SELECT survey, year, dataset, varname, label, label_en, topic_tags
        FROM variables WHERE varname=?
    """
    params = [varname]
    if args.survey:
        sql += " AND survey=?"
        params.append(args.survey)
    if args.dataset:
        sql += " AND dataset=?"
        params.append(args.dataset)
    if args.years.lower() != "all":
        years = [int(y.strip()) for y in args.years.split(",")]
        placeholders = ",".join("?" * len(years))
        sql += f" AND year IN ({placeholders})"
        params.extend(years)
    sql += " ORDER BY survey, year, dataset"
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        print(f"[ERROR] 未找到变量 {varname}", file=sys.stderr)
        sys.exit(1)

    for r in rows:
        cur2 = conn.execute(
            "SELECT value, label FROM valuelabels WHERE survey=? AND year=? AND dataset=? AND varname=? "
            "ORDER BY CAST(value AS REAL)",
            (r["survey"], r["year"], r["dataset"], r["varname"]),
        )
        r["valuelabels"] = {row["value"]: row["label"] for row in cur2.fetchall()}
        r["topic_tags"] = parse_tags(r.get("topic_tags", "[]"))

    labels = set(r["label"] for r in rows)
    label_consistent = len(labels) == 1
    vl_sets = [json.dumps(r["valuelabels"], sort_keys=True) for r in rows]
    vl_consistent = len(set(vl_sets)) == 1

    if args.json:
        result = {
            "varname": varname,
            "n_records": len(rows),
            "label_consistent": label_consistent,
            "valuelabels_consistent": vl_consistent,
            "records": [{
                "survey": r["survey"],
                "year": r["year"],
                "dataset": r["dataset"],
                "label": r["label"],
                "label_en": r["label_en"],
                "topic_tags": r["topic_tags"],
                "valuelabels": r["valuelabels"],
            } for r in rows],
        }
        print_json(result)
    else:
        print(f"=== {varname} 跨年/跨数据集对比 ({len(rows)} 条) ===")
        print(f"Label 一致: {'是' if label_consistent else '否'}")
        print(f"取值标签一致: {'是' if vl_consistent else '否'}")
        print()
        print_table(
            rows,
            columns=["survey", "year", "dataset", "label"],
            headers=["调查", "年份", "数据集", "标签"],
        )
        if not label_consistent:
            print("\n[!] Label 不一致:")
            for r in rows:
                print(f"  {r['survey']} {r['year']} {r['dataset']}: {r['label']}")
        if not vl_consistent:
            print("\n[!] 取值标签不一致，使用时注意")


def cmd_export(args, conn):
    tag = args.tag
    sql = """
        SELECT v.survey, v.year, v.dataset, v.varname, v.label, v.label_en,
               v.vtype, v.format, v.topic_tags, v.source_file
        FROM variables v
        WHERE v.topic_tags LIKE ?
    """
    params = [f'%"{tag}"%']
    if args.survey:
        sql += " AND v.survey = ?"
        params.append(args.survey)
    if args.dataset:
        sql += " AND v.dataset = ?"
        params.append(args.dataset)
    sql += " ORDER BY v.survey, v.year, v.dataset, v.varname"
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["topic_tags"] = parse_tags(r.get("topic_tags", "[]"))
        cur2 = conn.execute(
            "SELECT value, label FROM valuelabels WHERE survey=? AND year=? AND dataset=? AND varname=? "
            "ORDER BY CAST(value AS REAL)",
            (r["survey"], r["year"], r["dataset"], r["varname"]),
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
        flat_rows = []
        for r in rows:
            flat = {
                "survey": r["survey"],
                "year": r["year"],
                "dataset": r["dataset"],
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
    cur = conn.execute(
        "SELECT survey, year, dataset, COUNT(*) as n_vars "
        "FROM variables GROUP BY survey, year, dataset "
        "ORDER BY survey, year, dataset"
    )
    rows = [dict(r) for r in cur.fetchall()]
    if args.json:
        print_json(rows)
    else:
        print(f"共 {len(rows)} 个调查-年份-数据集组合:")
        print_table(
            rows,
            columns=["survey", "year", "dataset", "n_vars"],
            headers=["调查", "年份", "数据集", "变量数"],
        )


# ---------- 主入口 ----------

def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="输出 JSON 格式（供 AI agent 消费）")
    common.add_argument("--db", default=None, help="SQLite 路径（默认: 相对项目根的 data/codebook.db）")
    common.add_argument("--codebook-dir", default=None, help="JSON 目录（默认: 相对项目根的 data/codebook）")

    parser = argparse.ArgumentParser(
        description="China Survey Codebook CLI — 检索 CGSS/CHFS 变量元数据",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="按关键词搜索变量", parents=[common])
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--survey", default=None, help="调查名（CGSS/CHFS）")
    p_search.add_argument("--year", type=int, default=None, help="年份")
    p_search.add_argument("--dataset", default=None, help="数据集（main/household/master/individual）")
    p_search.add_argument("--tag", default=None, help="主题标签过滤")

    # variable
    p_var = subparsers.add_parser("variable", help="查看变量详情", parents=[common])
    p_var.add_argument("survey", help="调查名（CGSS/CHFS）")
    p_var.add_argument("year", type=int, help="年份")
    p_var.add_argument("varname", help="变量名")
    p_var.add_argument("--dataset", default=None, help="数据集（CGSS 默认 main；CHFS 必填）")

    # compare
    p_cmp = subparsers.add_parser("compare", help="跨年/跨数据集对比同一变量", parents=[common])
    p_cmp.add_argument("varname", help="变量名")
    p_cmp.add_argument("--years", required=True, help="逗号分隔年份（如 2010,2018）或 all")
    p_cmp.add_argument("--survey", default=None, help="限定调查名")
    p_cmp.add_argument("--dataset", default=None, help="限定数据集")

    # export
    p_exp = subparsers.add_parser("export", help="按主题导出变量", parents=[common])
    p_exp.add_argument("--tag", required=True, help="主题标签")
    p_exp.add_argument("--survey", default=None, help="限定调查名")
    p_exp.add_argument("--dataset", default=None, help="限定数据集")
    p_exp.add_argument("--format", default="json", choices=["json", "csv"], help="输出格式")

    # surveys
    subparsers.add_parser("surveys", help="列出所有调查-年份-数据集", parents=[common])

    args = parser.parse_args()

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
