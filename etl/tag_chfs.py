#!/usr/bin/env python3
"""
tag_chfs.py — 为 CHFS 高频变量自动打标

策略：
1. 扫描 CHFS household/master/individual JSON，统计每变量出现年份数
2. 对出现≥3年的变量，按 label 关键词匹配 tag 规则
3. 输出 4 段通配符键 CHFS:*:dataset:varname

需手动读入现有 tags/topic_tags.json，合并新 tag 后写回。
"""
import json
import glob
import os
from collections import defaultdict

# tag_definitions 新增 4 类
NEW_TAG_DEFS = {
    "finance": {
        "label": "金融产品",
        "label_en": "Financial Products",
        "description": "股票、基金、债券、理财、金融投资"
    },
    "credit": {
        "label": "信贷负债",
        "label_en": "Credit & Debt",
        "description": "信贷、借款、负债、贷款、抵押"
    },
    "asset": {
        "label": "资产财富",
        "label_en": "Assets & Wealth",
        "description": "房产、资产、财富、净资产、存款"
    },
    "housing": {
        "label": "住房",
        "label_en": "Housing",
        "description": "住房状况、面积、房贷、房产"
    },
}

# label 关键词 → tag 规则（按优先级）
KEYWORD_RULES = [
    # (关键词列表, [tags])
    (["性别", "出生年", "出生月", "年龄", "民族", "国籍", "婚姻", "户口", "政治面貌"],
     ["demographic"]),
    (["文化程度", "教育程度", "学历", "受教育"],
     ["education"]),
    (["总收入", "家庭收入", "个人收入", "工资", "薪酬", "收入"],
     ["income"]),
    (["就业", "工作", "职业", "工时", "打工", "务农", "全职", "兼职", "退休"],
     ["labor"]),
    (["健康", "就医", "医疗", "保险", "生病", "住院", "看病"],
     ["health"]),
    (["家庭", "子女", "孩子", "家务", "父母", "亲属", "家庭成员"],
     ["family"]),
    (["信任", "满意", "幸福", "阶层", "档次", "自评"],
     ["subjective"]),
    (["价值观", "态度", "看法", "认为"],
     ["attitude"]),
    # CHFS 特色：金融/信贷/资产/住房
    (["股票", "基金", "债券", "理财", "金融产品", "证券"],
     ["finance"]),
    (["贷款", "借款", "负债", "抵押", "信贷", "信用卡", "欠款"],
     ["credit"]),
    (["资产", "财富", "净资产", "存款", "储蓄", "财产"],
     ["asset"]),
    (["住房", "房产", "房子", "建筑面积", "使用面积", "居住", "拆迁", "装修", "租房", "自有住房", "住房套数"],
     ["housing"]),
]


def match_tags(label: str) -> list:
    """按关键词规则匹配 tag。返回去重后的 tag 列表。"""
    tags = []
    for keywords, tag_list in KEYWORD_RULES:
        for kw in keywords:
            if kw in label:
                tags.extend(tag_list)
                break  # 该规则组命中即跳到下一组
    # 去重保序
    seen = set()
    result = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    codebook_dir = os.path.join(project_root, "data", "codebook")
    tags_path = os.path.join(project_root, "tags", "topic_tags.json")

    # 1. 读现有 tags
    with open(tags_path, "r", encoding="utf-8") as f:
        tags_data = json.load(f)

    # 2. 加新 tag_definitions
    for k, v in NEW_TAG_DEFS.items():
        if k not in tags_data["tag_definitions"]:
            tags_data["tag_definitions"][k] = v
    print(f"tag_definitions: {len(tags_data['tag_definitions'])} 类")

    # 3. 扫描 CHFS JSON，统计变量出现年份数
    var_years = defaultdict(set)  # (dataset, varname) -> set(years)
    var_labels = {}  # (dataset, varname) -> label（取最新年）
    for jf in sorted(glob.glob(os.path.join(codebook_dir, "CHFS*.json"))):
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        dataset = data.get("dataset", "")
        for v in data["variables"]:
            key = (dataset, v["varname"])
            var_years[key].add(data["year"])
            var_labels[key] = v.get("label", "")

    print(f"CHFS 独立 (dataset, varname) 组合: {len(var_years)}")

    # 4. 对出现≥3年的变量打标
    new_tag_count = 0
    for (dataset, varname), years in var_years.items():
        if len(years) < 3:
            continue
        label = var_labels[(dataset, varname)]
        if not label:
            continue
        matched = match_tags(label)
        if not matched:
            continue
        tag_key = f"CHFS:*:{dataset}:{varname}"
        if tag_key not in tags_data["variable_tags"]:
            tags_data["variable_tags"][tag_key] = matched
            new_tag_count += 1

    print(f"新增 CHFS tag: {new_tag_count} 个变量")
    print(f"variable_tags 总数: {len(tags_data['variable_tags'])}")

    # 5. 统计各 tag 分布
    from collections import Counter
    tag_counter = Counter()
    for tags in tags_data["variable_tags"].values():
        for t in tags:
            tag_counter[t] += 1
    print("\n各 tag 变量数（含跨年展开前的通配符键）:")
    for tag, cnt in tag_counter.most_common():
        print(f"  {tag}: {cnt}")

    # 6. 写回
    with open(tags_path, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)
    print(f"\n已写入: {tags_path}")


if __name__ == "__main__":
    main()
