"""测试脚本：验证数据库查询功能"""

import sys
from pathlib import Path

# 加 scripts 到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from utils import get_db_path


def test_db_exists():
    """检查数据库是否存在"""
    db = get_db_path()
    if not db.exists():
        print(f"SKIP: 数据库不存在 ({db})，请先运行 step3_json_to_db.py")
        return False
    print(f"OK: 数据库存在 ({db})")
    return True


def test_basic_query():
    """基础查询测试"""
    import sqlite3
    conn = sqlite3.connect(str(get_db_path()))

    # 总变量数
    count = conn.execute("SELECT COUNT(*) FROM variables").fetchone()[0]
    print(f"OK: 总变量数 = {count}")

    # FTS5 搜索
    if count > 0:
        results = conn.execute(
            "SELECT COUNT(*) FROM variables_fts WHERE variables_fts MATCH '性别'"
        ).fetchone()[0]
        print(f"OK: FTS5 搜索 '性别' = {results} 条")

    # 值标签覆盖率
    total_vars = conn.execute("SELECT COUNT(*) FROM variables").fetchone()[0]
    vars_with_labels = conn.execute(
        "SELECT COUNT(DISTINCT variable_id) FROM value_labels"
    ).fetchone()[0]
    coverage = vars_with_labels / total_vars * 100 if total_vars > 0 else 0
    print(f"OK: 值标签覆盖率 = {coverage:.1f}% ({vars_with_labels}/{total_vars})")

    conn.close()


if __name__ == "__main__":
    if test_db_exists():
        test_basic_query()
