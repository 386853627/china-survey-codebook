"""AI Agent 入口：CGSS 问卷查询工具

用法:
    python scripts/query.py search "关键词"          # 全文搜索
    python scripts/query.py var --wave 2017 --var a1  # 精确查变量
    python scripts/query.py waves                     # 列出所有波次
    python scripts/query.py sections --wave 2017      # 列出某波次模块
    python scripts/query.py module --wave 2017 --section "A部分"  # 列出某模块变量
    python scripts/query.py stats                     # 数据库统计
    python scripts/query.py export --wave 2017 --output cgss2017.csv  # 导出CSV
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

from utils import get_db_path


def get_conn():
    db_path = get_db_path()
    if not db_path.exists():
        print(f"错误: 数据库不存在 ({db_path})")
        print("请先运行 step3_json_to_db.py 建库。")
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def cmd_search(args):
    """全文搜索"""
    conn = get_conn()
    query = args.query
    limit = args.limit or 20

    rows = conn.execute("""
        SELECT v.id, v.var_name, v.question_text, v.section, w.year,
               v.question_type, v.universe
        FROM variables_fts fts
        JOIN variables v ON v.id = fts.rowid
        JOIN waves w ON w.id = v.wave_id
        WHERE variables_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit)).fetchall()

    _print_table(rows, ["var_name", "question_text", "year", "section", "question_type"])
    print(f"\n找到 {len(rows)} 条结果 (上限 {limit})")
    conn.close()


def cmd_var(args):
    """精确查变量"""
    conn = get_conn()
    name = args.var.replace("'", "''")

    if args.like:
        rows = conn.execute("""
            SELECT v.*, w.year, w.survey_id
            FROM variables v
            JOIN waves w ON w.id = v.wave_id
            WHERE v.var_name LIKE ? AND w.year = ?
            ORDER BY v.sort_order
        """, (name, args.wave)).fetchall()
    else:
        rows = conn.execute("""
            SELECT v.*, w.year, w.survey_id
            FROM variables v
            JOIN waves w ON w.id = v.wave_id
            WHERE v.var_name = ? AND w.year = ?
        """, (name, args.wave)).fetchall()

    if not rows:
        print(f"未找到变量: {args.var} (CGSS {args.wave})")
        conn.close()
        return

    for row in rows:
        print(f"\n{'=' * 60}")
        print(f"变量名: {row['var_name']}")
        print(f"题号:   {row['question_number']}")
        print(f"年份:   CGSS {row['year']}")
        print(f"模块:   {row['section']}")
        print(f"题型:   {row['question_type']}")
        print(f"题干:   {row['question_text']}")
        if row['universe']:
            print(f"适用:   {row['universe']}")
        if row['interviewer_note']:
            print(f"访题说明: {row['interviewer_note']}")
        if row['skip_pattern']:
            print(f"跳转:   {row['skip_pattern']}")

        # 值标签
        labels = conn.execute("""
            SELECT value, label, is_missing
            FROM value_labels
            WHERE variable_id = ?
            ORDER BY sort_order
        """, (row['id'],)).fetchall()

        if labels:
            print(f"\n值标签:")
            for vl in labels:
                marker = " [缺失]" if vl['is_missing'] else ""
                print(f"  {vl['value']:>4} = {vl['label']}{marker}")

    conn.close()


def cmd_waves(args):
    """列出所有波次"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT w.year, w.sample_size, w.questionnaire_type,
               COUNT(v.id) as var_count
        FROM waves w
        LEFT JOIN variables v ON v.wave_id = w.id
        GROUP BY w.id
        ORDER BY w.year
    """).fetchall()

    _print_table(rows, ["year", "var_count", "questionnaire_type", "sample_size"])
    print(f"\n共 {len(rows)} 个波次")
    conn.close()


def cmd_sections(args):
    """列出某波次的模块"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT section, COUNT(*) as var_count,
               MIN(sort_order) as first_q
        FROM variables v
        JOIN waves w ON w.id = v.wave_id
        WHERE w.year = ?
        GROUP BY section
        ORDER BY MIN(sort_order)
    """, (args.wave,)).fetchall()

    if not rows:
        print(f"CGSS {args.wave} 无数据")
        conn.close()
        return

    print(f"CGSS {args.wave} 模块分布:")
    for row in rows:
        print(f"  {row['section']}: {row['var_count']} 题")
    conn.close()


def cmd_module(args):
    """列出某模块所有变量"""
    conn = get_conn()
    section = args.section.replace("'", "''")
    rows = conn.execute("""
        SELECT v.var_name, v.question_number, v.question_text, v.question_type
        FROM variables v
        JOIN waves w ON w.id = v.wave_id
        WHERE w.year = ? AND v.section LIKE ?
        ORDER BY v.sort_order
    """, (args.wave, f"%{section}%")).fetchall()

    if not rows:
        print(f"未找到模块 '{args.section}' (CGSS {args.wave})")
        conn.close()
        return

    _print_table(rows, ["var_name", "question_number", "question_text", "question_type"], max_text_len=60)
    print(f"\n共 {len(rows)} 题")
    conn.close()


def cmd_stats(args):
    """数据库统计"""
    conn = get_conn()

    # 总览
    survey_count = conn.execute("SELECT COUNT(*) FROM surveys").fetchone()[0]
    wave_count = conn.execute("SELECT COUNT(*) FROM waves").fetchone()[0]
    var_count = conn.execute("SELECT COUNT(*) FROM variables").fetchone()[0]
    label_count = conn.execute("SELECT COUNT(*) FROM value_labels").fetchone()[0]

    print(f"调查数量: {survey_count}")
    print(f"波次数量: {wave_count}")
    print(f"变量数量: {var_count}")
    print(f"值标签数量: {label_count}")
    print()

    # 各波次详情
    rows = conn.execute("""
        SELECT w.year, COUNT(v.id) as vars
        FROM waves w
        LEFT JOIN variables v ON v.wave_id = w.id
        GROUP BY w.id
        ORDER BY w.year
    """).fetchall()

    print("波次 / 变量数:")
    for row in rows:
        bar = "█" * min(row['vars'] // 10, 40)
        print(f"  {row['year']:4d}: {row['vars']:4d} {bar}")

    conn.close()


def cmd_export(args):
    """导出某波次完整变量列表为 CSV"""
    conn = get_conn()
    out = args.output or f"cgss{args.wave}.csv"

    rows = conn.execute("""
        SELECT v.var_name, v.question_number, v.question_text,
               v.question_type, v.section, v.universe,
               v.interviewer_note, v.skip_pattern,
               GROUP_CONCAT(vl.value || '=' || vl.label, '; ') as labels
        FROM variables v
        JOIN waves w ON w.id = v.wave_id
        LEFT JOIN value_labels vl ON vl.variable_id = v.id
        WHERE w.year = ?
        GROUP BY v.id
        ORDER BY v.sort_order
    """, (args.wave,)).fetchall()

    if not rows:
        print(f"CGSS {args.wave} 无数据")
        conn.close()
        return

    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["变量名", "题号", "题干", "题型", "模块", "适用人群",
                         "访题说明", "跳转逻辑", "值标签"])
        for row in rows:
            writer.writerow([row[i] for i in range(len(row))])

    print(f"已导出 {len(rows)} 个变量 → {out}")
    conn.close()


# --- 工具函数 ---

def _print_table(rows, columns, max_text_len=100):
    """格式化打印表格"""
    if not rows:
        print("(无结果)")
        return

    # 计算列宽
    widths = {}
    for col in columns:
        widths[col] = len(col)
        for row in rows:
            text = str(row[col] or "")
            widths[col] = max(widths[col], min(len(text), max_text_len))

    total_width = sum(widths.values()) + len(columns) * 3 + 1
    separator = "─" * min(total_width, 120)

    # 表头
    header = "│ " + " │ ".join(col.ljust(widths[col]) for col in columns) + " │"
    print(separator)
    print(header)
    print(separator)

    # 数据行
    for row in rows:
        parts = []
        for col in columns:
            text = str(row[col] or "")
            if len(text) > max_text_len:
                text = text[:max_text_len - 3] + "..."
            parts.append(text.ljust(widths[col]))
        print("│ " + " │ ".join(parts) + " │")

    print(separator)


# --- 主入口 ---

def main():
    parser = argparse.ArgumentParser(description="CGSS 问卷查询工具")
    sub = parser.add_subparsers(dest="command")

    # search
    p = sub.add_parser("search", help="全文搜索")
    p.add_argument("query", type=str, help="搜索关键词")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_search)

    # var
    p = sub.add_parser("var", help="精确查变量")
    p.add_argument("--wave", type=int, required=True)
    p.add_argument("--var", type=str, required=True, help="变量名，如 a1")
    p.add_argument("--like", action="store_true", help="模糊匹配 (LIKE)")
    p.set_defaults(func=cmd_var)

    # waves
    p = sub.add_parser("waves", help="列出所有波次")
    p.set_defaults(func=cmd_waves)

    # sections
    p = sub.add_parser("sections", help="列出某波次模块")
    p.add_argument("--wave", type=int, required=True)
    p.set_defaults(func=cmd_sections)

    # module
    p = sub.add_parser("module", help="列出某模块变量")
    p.add_argument("--wave", type=int, required=True)
    p.add_argument("--section", type=str, required=True)
    p.set_defaults(func=cmd_module)

    # stats
    p = sub.add_parser("stats", help="数据库统计")
    p.set_defaults(func=cmd_stats)

    # export
    p = sub.add_parser("export", help="导出CSV")
    p.add_argument("--wave", type=int, required=True)
    p.add_argument("--output", type=str)
    p.set_defaults(func=cmd_export)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
