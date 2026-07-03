"""Step 3: JSON → SQLite 建库写入

用法:
    python scripts/step3_json_to_db.py [--year 2017] [--reset]

如果 cgss.db 已存在，默认不覆盖。加 --reset 重建。
"""

import json
import sqlite3
import argparse
from pathlib import Path
from typing import Optional

from utils import get_data_dir, get_db_path, get_project_root


def load_schema(db_path: Path):
    """执行 schema.sql 建表"""
    schema_path = get_project_root() / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"找不到 {schema_path}")
    sql = schema_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db_path))
    conn.executescript(sql)
    conn.commit()
    return conn


def parse_year_from_filename(filename: str) -> int:
    """从文件名提取年份"""
    import re
    match = re.search(r"(\d{4})", filename)
    return int(match.group(1)) if match else 0


def ensure_survey(conn: sqlite3.Connection) -> int:
    """确保 CGSS 调查记录存在，返回 survey_id"""
    cur = conn.execute("SELECT id FROM surveys WHERE name = 'CGSS'")
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("""
        INSERT INTO surveys (name, full_name, name_cn, institution, website, description)
        VALUES ('CGSS', 'Chinese General Social Survey', '中国综合社会调查',
                '中国人民大学中国调查与数据中心 (NSRC)', 'http://cgss.ruc.edu.cn/',
                '中国第一个全国性、综合性、连续性的大型社会调查项目')
    """)
    conn.commit()
    return cur.lastrowid


def ensure_wave(conn: sqlite3.Connection, survey_id: int, year: int,
                source_file: str = "") -> int:
    """确保波次记录存在，返回 wave_id"""
    cur = conn.execute(
        "SELECT id FROM waves WHERE survey_id = ? AND year = ?",
        (survey_id, year)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        """INSERT INTO waves (survey_id, year, source_file, questionnaire_type)
           VALUES (?, ?, ?, '个人问卷')""",
        (survey_id, year, source_file)
    )
    conn.commit()
    return cur.lastrowid


def insert_variable(conn: sqlite3.Connection, wave_id: int,
                    item: dict, sort_order: int) -> int:
    """插入一条变量记录，返回 variable_id"""
    cur = conn.execute(
        """INSERT INTO variables
           (wave_id, var_name, section, question_number, question_text,
            question_type, interviewer_note, skip_pattern, universe,
            is_core_module, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            wave_id,
            item.get("var_name", ""),
            item.get("section", ""),
            item.get("question_number", ""),
            item.get("question_text", ""),
            item.get("question_type", ""),
            item.get("interviewer_note"),
            item.get("skip_pattern"),
            item.get("universe"),
            item.get("is_core_module", 0),
            sort_order,
        )
    )
    return cur.lastrowid


def insert_value_labels(conn: sqlite3.Connection, variable_id: int,
                        labels: list[dict]):
    """插入值标签"""
    for i, vl in enumerate(labels):
        conn.execute(
            """INSERT INTO value_labels (variable_id, value, label, is_missing, sort_order)
               VALUES (?, ?, ?, ?, ?)""",
            (
                variable_id,
                str(vl.get("value", "")),
                str(vl.get("label", "")),
                int(vl.get("is_missing", 0)),
                i,
            )
        )


def import_json(conn: sqlite3.Connection, json_path: Path) -> int:
    """导入单个 JSON 文件"""
    name = json_path.stem
    year = parse_year_from_filename(name)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError(f"{name}: JSON 根元素应为数组")

    survey_id = ensure_survey(conn)
    wave_id = ensure_wave(conn, survey_id, year, source_file=name)

    # 先删除该波次的旧数据（如果重复导入）
    conn.execute("DELETE FROM value_labels WHERE variable_id IN "
                 "(SELECT id FROM variables WHERE wave_id = ?)", (wave_id,))
    conn.execute("DELETE FROM variables WHERE wave_id = ?", (wave_id,))

    count = 0
    for i, item in enumerate(data):
        vid = insert_variable(conn, wave_id, item, i + 1)
        insert_value_labels(conn, vid, item.get("value_labels", []))
        count += 1

    conn.commit()
    return count


def rebuild_fts(conn: sqlite3.Connection):
    """重建 FTS5 全文索引"""
    conn.execute("INSERT INTO variables_fts(variables_fts) VALUES ('rebuild')")
    conn.commit()


def run_validation(conn: sqlite3.Connection):
    """输出数据库统计信息"""
    print("\n" + "=" * 60)
    print("数据库统计")
    print("=" * 60)

    for row in conn.execute("""
        SELECT w.year, COUNT(v.id) as var_count,
               COUNT(vl.id) as label_count
        FROM waves w
        JOIN variables v ON v.wave_id = w.id
        LEFT JOIN value_labels vl ON vl.variable_id = v.id
        GROUP BY w.year
        ORDER BY w.year
    """):
        print(f"  CGSS {row[0]:4d}: {row[1]:4d} 变量, {row[2]:5d} 值标签")

    # 模块分布
    print("\n模块分布:")
    for row in conn.execute("""
        SELECT section, COUNT(*) as cnt
        FROM variables
        GROUP BY section
        ORDER BY MIN(sort_order)
    """):
        print(f"  {row[0]}: {row[1]} 题")

    total_vars = conn.execute("SELECT COUNT(*) FROM variables").fetchone()[0]
    total_labels = conn.execute("SELECT COUNT(*) FROM value_labels").fetchone()[0]
    print(f"\n总计: {total_vars} 个变量, {total_labels} 个值标签")


def main():
    parser = argparse.ArgumentParser(description="JSON → SQLite 建库")
    parser.add_argument("--year", type=int, help="仅导入指定年份")
    parser.add_argument("--file", type=str, help="仅导入指定 JSON 文件")
    parser.add_argument("--reset", action="store_true", help="删除旧数据库，重建")
    args = parser.parse_args()

    db_path = get_db_path()

    # 处理 --reset
    if args.reset and db_path.exists():
        db_path.unlink()
        print(f"已删除旧数据库: {db_path}")

    is_new = not db_path.exists()

    if is_new:
        conn = load_schema(db_path)
        print(f"已创建数据库: {db_path}")
    else:
        conn = sqlite3.connect(str(db_path))

    # 加载 JSON
    json_dir = get_data_dir("json")
    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(json_dir.glob("*.json"))
        if args.year:
            files = [f for f in files if str(args.year) in f.stem]

    if not files:
        print("未找到 JSON 文件。请先运行 step2_md_to_json.py。")
        conn.close()
        return

    print(f"待导入: {len(files)} 个文件\n")

    total = 0
    for f in files:
        try:
            count = import_json(conn, f)
            print(f"  {f.name}: {count} 个变量")
            total += count
        except Exception as e:
            print(f"  {f.name}: 失败 - {e}")

    conn.commit()
    print(f"\n导入完成: {total} 个变量")

    # 重建 FTS5
    print("重建 FTS5 索引...")
    rebuild_fts(conn)

    # 验证
    run_validation(conn)

    conn.close()


if __name__ == "__main__":
    main()
