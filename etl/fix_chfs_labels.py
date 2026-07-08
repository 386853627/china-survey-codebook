#!/usr/bin/env python3
"""
fix_chfs_labels.py — 修复 CHFS 2011/2013 codebook JSON 的 label 乱码 + 填充 valuelabels

问题：
  CHFS 2011/2013 的 .dta 文件中中文 label 被 pandas 以 latin-1 解码了 GBK 字节，
  导致 JSON 中 label 全是 mojibake（如 "±¾·¿ÎÝ¾Ó×¡¼ÒÍ¥Êý" 应为 "本房屋居住家庭数"）。
  valuelabels 基本为空（CHFS 取值标签多在 master，household/individual 用数值编码）。

方案：
  用用户从问卷手工提取的标签数据（chfs/chfs20XX/CHFS20XX_codebook.json）覆盖
  现有 codebook JSON 的 label 字段，并填充空的 valuelabels。
  问卷未覆盖的变量（如 hhid/weight 等系统变量）尝试 latin-1->GBK 兜底修复。

用法:
    python etl/fix_chfs_labels.py
"""

import json
import os
import sys

# Windows 终端 GBK 坑：强制 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")

# 项目根目录（脚本位于 etl/ 下）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 问卷数据 -> codebook JSON 的映射
YEAR_MAP = {
    2011: {
        "survey_file": "chfs/chfs2011/CHFS2011_codebook.json",
        "datasets": ["household", "individual", "master"],
    },
    2013: {
        "survey_file": "chfs/chfs2013/CHFS2013_codebook.json",
        "datasets": ["household", "individual", "master"],
    },
}


def try_fix_gbk(s: str) -> str:
    """latin-1 字节串 -> GBK 解码，修复 mojibake。纯 ASCII 和空串安全。"""
    if not s or s.isascii():
        return s
    try:
        return s.encode("latin-1").decode("gbk")
    except Exception:
        return s  # 修复失败保留原样


def is_mojibake(s: str) -> bool:
    """粗略判断字符串是否是 GBK mojibake：含 latin-1 高字节区字符且非正常中文。"""
    if not s or s.isascii():
        return False
    # mojibake 特征：大量 0xC0-0xFF 区间的 latin-1 字符（À-ÿ）
    high_latin = sum(1 for c in s if "\u00c0" <= c <= "\u00ff")
    return high_latin > len(s) * 0.3


def load_survey_data(path: str) -> dict:
    """加载问卷数据: {varname: {label, question, values}}"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fix_one_file(codebook_path: str, survey_data: dict) -> dict:
    """修复单个 codebook JSON 文件，返回统计信息。"""
    with open(codebook_path, "r", encoding="utf-8") as f:
        codebook = json.load(f)

    stats = {
        "total": len(codebook["variables"]),
        "matched": 0,
        "label_fixed": 0,
        "valuelabels_filled": 0,
        "fallback_fixed": 0,
        "unmatched_mojibake": [],
    }

    for var in codebook["variables"]:
        varname = var["varname"]
        old_label = var["label"]

        if varname in survey_data:
            q = survey_data[varname]
            stats["matched"] += 1

            # 修复 label（问卷优先）
            new_label = q.get("label", "")
            if new_label and new_label != old_label:
                var["label"] = new_label
                stats["label_fixed"] += 1

            # 填充 valuelabels（仅当现有为空且问卷有 values）
            q_values = q.get("values")
            if not var["valuelabels"] and q_values:
                var["valuelabels"] = dict(q_values)
                stats["valuelabels_filled"] += 1
        else:
            # 未匹配变量：尝试 latin-1->GBK 兜底修复乱码 label
            if is_mojibake(old_label):
                fixed = try_fix_gbk(old_label)
                if fixed != old_label:
                    var["label"] = fixed
                    stats["fallback_fixed"] += 1
                else:
                    stats["unmatched_mojibake"].append(varname)

    # 原地覆盖保存
    with open(codebook_path, "w", encoding="utf-8") as f:
        json.dump(codebook, f, ensure_ascii=False, indent=2)

    return stats


def main():
    print("=" * 70)
    print("CHFS 2011/2013 标签修复")
    print("=" * 70)

    for year, cfg in YEAR_MAP.items():
        survey_path = os.path.join(ROOT, cfg["survey_file"])
        if not os.path.isfile(survey_path):
            print(f"[WARN] 问卷数据不存在: {survey_path}，跳过 {year}")
            continue

        survey_data = load_survey_data(survey_path)
        print(f"\n[{year}] 问卷数据: {len(survey_data)} 变量 <- {cfg['survey_file']}")

        for dataset in cfg["datasets"]:
            codebook_path = os.path.join(ROOT, "data", "codebook",
                                          f"CHFS{year}_{dataset}.json")
            if not os.path.isfile(codebook_path):
                print(f"  [{dataset}] 文件不存在，跳过")
                continue

            stats = fix_one_file(codebook_path, survey_data)

            print(f"\n  [{dataset}] {codebook_path}")
            print(f"    总变量: {stats['total']}")
            print(f"    问卷匹配: {stats['matched']} "
                  f"({stats['matched'] * 100 // stats['total']}%)")
            print(f"    label 修复 (问卷): {stats['label_fixed']}")
            print(f"    valuelabels 填充: {stats['valuelabels_filled']}")
            print(f"    label 兜底修复 (GBK): {stats['fallback_fixed']}")
            if stats["unmatched_mojibake"]:
                print(f"    [WARN] 仍有 {len(stats['unmatched_mojibake'])} 个未匹配且兜底失败的乱码变量:")
                for name in stats["unmatched_mojibake"][:20]:
                    print(f"      - {name}")
                if len(stats["unmatched_mojibake"]) > 20:
                    print(f"      ... 等共 {len(stats['unmatched_mojibake'])} 个")

    print("\n" + "=" * 70)
    print("修复完成。下一步: 运行 build_sqlite.py 重建 DB")
    print("=" * 70)


if __name__ == "__main__":
    main()
