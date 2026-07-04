#!/usr/bin/env python3
"""
build_sqlite.py — 从 data/codebook/*.json 构建 SQLite 索引

用法:
    python etl/build_sqlite.py                      # 默认路径
    python etl/build_sqlite.py --json-dir data/codebook --output data/codebook.db

表结构:
    variables        — 变量元数据主表
    valuelabels      — 取值标签表（一变量一取值一行）
    variables_fts    — FTS5 全文检索（unicode61 按字分词，支持中文）
"""

import argparse
import glob
import json
import os
import sqlite3
from datetime import datetime, timezone


def load_tags(tags_path: str) -> dict:
    """加载 tags/topic_tags.json，返回 {varname_lower: [tags]} 映射。

    键格式 CGSS:*:a2 → 剥离前缀，varname 转小写（兼容 2021 大写变量）。
    """
    if not os.path.exists(tags_path):
        print(f"[WARN] 标签文件不存在: {tags_path}，topic_tags 字段将为空")
        return {}
    with open(tags_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tags_map = {}
    for key, tags in data.get("variable_tags", {}).items():
        # key 格式: CGSS:*:a2
        parts = key.split(":")
        if len(parts) == 3:
            varname = parts[2].lower()
            tags_map[varname] = tags
    return tags_map


def resolve_tags(json_tags: list, varname: str, tags_map: dict) -> list:
    """优先用 JSON 中的 topic_tags；为空则查 tags_map（通配符回填）。"""
    if json_tags:
        return json_tags
    return tags_map.get(varname.lower(), [])


def build(json_dir: str, output: str, tags_path: str) -> None:
    json_files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
    # 排除 variable_mapping.json（位于 data/ 而非 data/codebook/，但保险起见过滤）
    json_files = [f for f in json_files if os.path.basename(f) != "variable_mapping.json"]

    if not json_files:
        raise FileNotFoundError(f"未找到 JSON 文件: {json_dir}")

    # 加载主题标签
    tags_map = load_tags(tags_path)
    if tags_map:
        print(f"[OK] 加载 {len(tags_map)} 个变量主题标签")

    if os.path.exists(output):
        os.remove(output)

    conn = sqlite3.connect(output)
    cur = conn.cursor()

    # 建表
    cur.executescript("""
        DROP TABLE IF EXISTS variables;
        DROP TABLE IF EXISTS valuelabels;
        DROP TABLE IF EXISTS variables_fts;

        CREATE TABLE variables (
            survey     TEXT NOT NULL,
            year       INTEGER NOT NULL,
            varname    TEXT NOT NULL,
            label      TEXT,
            label_en   TEXT,
            vtype      TEXT,
            format     TEXT,
            source_file TEXT,
            topic_tags TEXT,
            PRIMARY KEY (survey, year, varname)
        );

        CREATE TABLE valuelabels (
            survey  TEXT NOT NULL,
            year    INTEGER NOT NULL,
            varname TEXT NOT NULL,
            value   TEXT NOT NULL,
            label   TEXT
        );

        CREATE VIRTUAL TABLE variables_fts USING fts5(
            survey, year UNINDEXED, varname, label, label_en, topic_tags,
            tokenize = 'unicode61'
        );

        CREATE INDEX idx_valuelabels_lookup ON valuelabels(survey, year, varname);
    """)

    total_vars = 0
    total_labels = 0
    per_year_stats = []

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)

        survey = data["survey"]
        year = data["year"]
        source_file = data.get("source_file", "")
        n_vars = data["n_variables"]
        year_vars = 0
        year_labels = 0

        cur.execute("BEGIN")
        for v in data["variables"]:
            varname = v["varname"]
            label = v.get("label", "")
            label_en = v.get("label_en", "")
            vtype = v.get("vtype", "")
            fmt = v.get("format", "")
            # 优先用 JSON 中的 topic_tags；为空则从 tags_map 回填（通配符展开）
            resolved_tags = resolve_tags(v.get("topic_tags", []), varname, tags_map)
            tags_json = json.dumps(resolved_tags, ensure_ascii=False)

            cur.execute(
                "INSERT INTO variables VALUES (?,?,?,?,?,?,?,?,?)",
                (survey, year, varname, label, label_en, vtype, fmt, source_file, tags_json),
            )

            cur.execute(
                "INSERT INTO variables_fts(survey, year, varname, label, label_en, topic_tags) VALUES (?,?,?,?,?,?)",
                (survey, year, varname, label, label_en, tags_json),
            )

            vl = v.get("valuelabels", {})
            for val, lbl in vl.items():
                cur.execute(
                    "INSERT INTO valuelabels VALUES (?,?,?,?,?)",
                    (survey, year, varname, str(val), str(lbl)),
                )
                year_labels += 1

            year_vars += 1

        conn.commit()
        total_vars += year_vars
        total_labels += year_labels
        per_year_stats.append((survey, year, year_vars, year_labels, n_vars))
        print(f"{survey}{year}: {year_vars}变量 / {year_labels}取值标签 (源文件声明 n_variables={n_vars})")

    # 一致性检查
    print("\n=== 构建完成 ===")
    print(f"JSON 文件数: {len(json_files)}")
    print(f"总变量数: {total_vars}")
    print(f"总取值标签数: {total_labels}")

    mismatches = [s for s in per_year_stats if s[2] != s[4]]
    if mismatches:
        print(f"[WARN] 变量数不一致的年份: {mismatches}")
    else:
        print("[OK] 所有年份变量数与源文件声明一致")

    conn.close()
    print(f"已写入: {output}")


def main():
    parser = argparse.ArgumentParser(description="从 JSON 构建 SQLite 索引")
    parser.add_argument("--json-dir", default="data/codebook", help="JSON 输入目录")
    parser.add_argument("--output", default="data/codebook.db", help="SQLite 输出路径")
    parser.add_argument("--tags", default="tags/topic_tags.json", help="主题标签 JSON 路径")
    args = parser.parse_args()
    build(args.json_dir, args.output, args.tags)


if __name__ == "__main__":
    main()
