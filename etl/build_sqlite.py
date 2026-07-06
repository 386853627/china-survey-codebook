#!/usr/bin/env python3
"""
build_sqlite.py — 从 data/codebook/*.json 构建 SQLite 索引（四段主键版）

主键: (survey, year, dataset, varname) — 支持 CHFS 每 wave 多 dataset 结构。
CGSS 旧 JSON 无 dataset 字段时自动回填 "main"。

用法:
    python etl/build_sqlite.py
    python etl/build_sqlite.py --json-dir data/codebook --output data/codebook.db

表结构:
    variables        — 变量元数据主表（四段主键）
    valuelabels      — 取值标签表
    variables_fts    — FTS5 全文检索（unicode61 按字分词，支持中文）
"""

import argparse
import glob
import json
import os
import sqlite3


def load_tags(tags_path: str) -> dict:
    """加载 tags/topic_tags.json，返回 {(survey, dataset): {varname_lower: [tags]}} 映射。

    支持两种键格式：
      - 3 段: CGSS:*:a2          → (CGSS, main): {a2: tags}   # CGSS 默认 dataset=main
      - 4 段: CHFS:*:household:x → (CHFS, household): {x: tags}
    """
    if not os.path.exists(tags_path):
        print(f"[WARN] 标签文件不存在: {tags_path}，topic_tags 字段将为空")
        return {}
    with open(tags_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tags_map = {}  # {(survey, dataset): {varname_lower: tags}}
    for key, tags in data.get("variable_tags", {}).items():
        parts = key.split(":")
        if len(parts) == 3:
            # CGSS:*:a2 → survey=CGSS, dataset=main
            survey, _, varname = parts
            dataset = "main"
        elif len(parts) == 4:
            # CHFS:*:household:varname
            survey, _, dataset, varname = parts
        else:
            print(f"[WARN] 跳过格式异常的 tag 键: {key}")
            continue
        tags_map.setdefault((survey, dataset), {})[varname.lower()] = tags
    return tags_map


def resolve_tags(json_tags: list, survey: str, dataset: str,
                 varname: str, tags_map: dict) -> list:
    """优先用 JSON 中的 topic_tags；为空则查 tags_map（通配符回填）。

    匹配键: (survey, dataset) → varname_lower
    """
    if json_tags:
        return json_tags
    survey_map = tags_map.get((survey, dataset), {})
    return survey_map.get(varname.lower(), [])


def build(json_dir: str, output: str, tags_path: str) -> None:
    json_files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
    # 排除非 codebook 的 JSON
    json_files = [f for f in json_files
                  if os.path.basename(f) not in ("variable_mapping.json",
                                                 "cross_survey_mapping.json")]

    if not json_files:
        raise FileNotFoundError(f"未找到 JSON 文件: {json_dir}")

    # 加载主题标签
    tags_map = load_tags(tags_path)
    if tags_map:
        n_tag_keys = sum(len(m) for m in tags_map.values())
        print(f"[OK] 加载 {len(tags_map)} 个 (survey,dataset) 组 / {n_tag_keys} 个变量主题标签")

    if os.path.exists(output):
        os.remove(output)

    conn = sqlite3.connect(output)
    cur = conn.cursor()

    # 建表（四段主键）
    cur.executescript("""
        DROP TABLE IF EXISTS variables;
        DROP TABLE IF EXISTS valuelabels;
        DROP TABLE IF EXISTS variables_fts;

        CREATE TABLE variables (
            survey      TEXT NOT NULL,
            year        INTEGER NOT NULL,
            dataset     TEXT NOT NULL,
            varname     TEXT NOT NULL,
            label       TEXT,
            label_en    TEXT,
            vtype       TEXT,
            format      TEXT,
            source_file TEXT,
            n_observations INTEGER,
            topic_tags  TEXT,
            PRIMARY KEY (survey, year, dataset, varname)
        );

        CREATE TABLE valuelabels (
            survey  TEXT NOT NULL,
            year    INTEGER NOT NULL,
            dataset TEXT NOT NULL,
            varname TEXT NOT NULL,
            value   TEXT NOT NULL,
            label   TEXT
        );

        CREATE VIRTUAL TABLE variables_fts USING fts5(
            survey, year UNINDEXED, dataset UNINDEXED,
            varname, label, label_en, topic_tags,
            tokenize = 'unicode61'
        );

        CREATE INDEX idx_valuelabels_lookup ON valuelabels(survey, year, dataset, varname);
    """)

    total_vars = 0
    total_labels = 0
    per_file_stats = []

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)

        survey = data["survey"]
        year = data["year"]
        # 兼容旧 CGSS JSON（无 dataset 字段）→ 回填 main
        dataset = data.get("dataset", "main")
        source_file = data.get("source_file", "")
        n_obs = data.get("n_observations")
        n_vars = data["n_variables"]
        file_vars = 0
        file_labels = 0

        cur.execute("BEGIN")
        for v in data["variables"]:
            varname = v["varname"]
            v_dataset = v.get("dataset", dataset)  # 变量级 dataset 优先
            label = v.get("label", "")
            label_en = v.get("label_en", "")
            vtype = v.get("vtype", "")
            fmt = v.get("format", "")
            resolved_tags = resolve_tags(
                v.get("topic_tags", []), survey, v_dataset, varname, tags_map
            )
            tags_json = json.dumps(resolved_tags, ensure_ascii=False)

            cur.execute(
                "INSERT INTO variables VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (survey, year, v_dataset, varname, label, label_en,
                 vtype, fmt, source_file, n_obs, tags_json),
            )

            cur.execute(
                "INSERT INTO variables_fts(survey, year, dataset, varname, label, label_en, topic_tags) "
                "VALUES (?,?,?,?,?,?,?)",
                (survey, year, v_dataset, varname, label, label_en, tags_json),
            )

            vl = v.get("valuelabels", {})
            for val, lbl in vl.items():
                cur.execute(
                    "INSERT INTO valuelabels VALUES (?,?,?,?,?,?)",
                    (survey, year, v_dataset, varname, str(val), str(lbl)),
                )
                file_labels += 1

            file_vars += 1

        conn.commit()
        total_vars += file_vars
        total_labels += file_labels
        per_file_stats.append((survey, year, dataset, file_vars, file_labels, n_vars))
        print(f"{survey}{year}_{dataset}: {file_vars}变量 / {file_labels}取值标签 "
              f"(源声明 n_variables={n_vars})")

    # 一致性检查
    print("\n=== 构建完成 ===")
    print(f"JSON 文件数: {len(json_files)}")
    print(f"总变量数: {total_vars}")
    print(f"总取值标签数: {total_labels}")

    mismatches = [s for s in per_file_stats if s[3] != s[5]]
    if mismatches:
        print(f"[WARN] 变量数不一致: {mismatches}")
    else:
        print("[OK] 所有文件变量数与源声明一致")

    # DB 大小
    db_size = os.path.getsize(output) / 1024 / 1024
    print(f"DB 大小: {db_size:.1f} MB")

    conn.close()
    print(f"已写入: {output}")


def main():
    parser = argparse.ArgumentParser(description="从 JSON 构建 SQLite 索引（四段主键）")
    parser.add_argument("--json-dir", default="data/codebook", help="JSON 输入目录")
    parser.add_argument("--output", default="data/codebook.db", help="SQLite 输出路径")
    parser.add_argument("--tags", default="tags/topic_tags.json", help="主题标签 JSON 路径")
    args = parser.parse_args()
    build(args.json_dir, args.output, args.tags)


if __name__ == "__main__":
    main()
