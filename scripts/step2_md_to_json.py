"""Step 2: Markdown → 结构化JSON（通过 LLM API）

用法:
    python scripts/step2_md_to_json.py [--year 2017] [--dry-run]

环境变量:
    LLM_API_KEY     LLM API 密钥
    LLM_BASE_URL    API 端点 (默认 https://api.deepseek.com/v1)
    LLM_MODEL       模型名称 (默认 deepseek-chat)
"""

import json
import argparse
import re
from pathlib import Path
from typing import Optional

from openai import OpenAI

from utils import get_data_dir, get_env, get_project_root


def load_prompt() -> str:
    """加载提取 prompt 模板"""
    prompt_path = get_project_root() / "prompts" / "extraction.md"
    return prompt_path.read_text(encoding="utf-8")


def load_markdown(year: Optional[int] = None, filepath: Optional[Path] = None) -> list[tuple[str, str]]:
    """加载 Markdown 文件，返回 [(文件名, 内容)]"""
    if filepath:
        return [(filepath.stem, filepath.read_text(encoding="utf-8"))]

    md_dir = get_data_dir("markdown")
    files = sorted(md_dir.glob("*.md"))
    if year is not None:
        files = [f for f in files if str(year) in f.stem]
    return [(f.stem, f.read_text(encoding="utf-8")) for f in files]


def call_llm(prompt_template: str, md_content: str, client: OpenAI, model: str) -> str:
    """调用 LLM 提取结构化数据"""
    system_prompt = (
        prompt_template.replace("{questionnaire_markdown}", "")
        + "\n\n请严格按照上述规则，从以下问卷中提取所有变量信息。直接输出 JSON 数组，不要有任何其他文字。"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": f"问卷 Markdown 文本:\n\n{md_content}"},
        ],
        temperature=0.1,  # 低温度保证一致性
        max_tokens=16000,
    )

    raw = response.choices[0].message.content
    return raw.strip() if raw else ""


def extract_json(text: str) -> list[dict]:
    """从 LLM 回复中提取 JSON 数组"""
    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到最外层 [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从回复中提取 JSON 数组。回复前200字: {text[:200]}")


def validate_variables(data: list[dict]) -> list[str]:
    """验证 JSON schema，返回警告列表"""
    warnings = []
    required_fields = ["var_name", "section", "question_number", "question_text", "question_type"]
    valid_types = {"单选题", "多选题", "填空题", "开放题", "量表题",
                   "single", "multiple", "fill", "open", "scale"}

    for i, item in enumerate(data):
        # 必填字段
        for f in required_fields:
            if f not in item or not item[f]:
                warnings.append(f"  第{i+1}条: 缺少必填字段 '{f}'")

        # question_type 规范化
        if item.get("question_type", "").lower() in ("single", "单选题"):
            item["question_type"] = "单选题"
        elif item.get("question_type", "").lower() in ("multiple", "多选题"):
            item["question_type"] = "多选题"
        elif item.get("question_type", "").lower() in ("fill", "填空题"):
            item["question_type"] = "填空题"
        elif item.get("question_type", "").lower() in ("open", "开放题"):
            item["question_type"] = "开放题"
        elif item.get("question_type", "").lower() in ("scale", "量表题"):
            item["question_type"] = "量表题"

        # is_core_module 默认值
        if "is_core_module" not in item:
            item["is_core_module"] = 0

        # value_labels 确保是列表
        if "value_labels" not in item:
            item["value_labels"] = []

    return warnings


def process_markdown(name: str, content: str, client: OpenAI, model: str,
                     prompt: str, dry_run: bool = False) -> Optional[Path]:
    """处理单个 Markdown 文件"""
    print(f"  [{name}] 正在调用 LLM 提取...")
    if dry_run:
        print(f"  [Dry-run] 跳过 LLM 调用")
        return None

    raw = call_llm(prompt, content, client, model)
    data = extract_json(raw)

    # 验证 + 规范化
    warnings = validate_variables(data)
    if warnings:
        print(f"  [警告] 发现 {len(warnings)} 个问题:")
        for w in warnings[:10]:
            print(w)

    # 保存 JSON
    out_path = get_data_dir("json") / f"{name}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [完成] {len(data)} 个变量 → {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Markdown → JSON（LLM 提取）")
    parser.add_argument("--year", type=int, help="仅处理指定年份")
    parser.add_argument("--file", type=str, help="仅处理指定文件")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际调用 LLM")
    parser.add_argument("--model", type=str, default=None, help="覆盖模型名称")
    args = parser.parse_args()

    # API 配置
    api_key = get_env("LLM_API_KEY") or get_env("DEEPSEEK_API_KEY")
    base_url = get_env("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = args.model or get_env("LLM_MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("未找到 LLM_API_KEY 或 DEEPSEEK_API_KEY。请在 .env 文件中设置。")

    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = load_prompt()

    # 加载文件
    if args.file:
        md_list = load_markdown(filepath=Path(args.file))
    else:
        md_list = load_markdown(year=args.year)

    if not md_list:
        print("未找到 Markdown 文件。请先运行 step1_pdf_to_md.py。")
        return

    print(f"待处理: {len(md_list)} 个文件\n")

    for i, (name, content) in enumerate(md_list, 1):
        print(f"[{i}/{len(md_list)}]")
        try:
            process_markdown(name, content, client, model, prompt, args.dry_run)
        except Exception as e:
            print(f"  [失败] {e}")
        print()


if __name__ == "__main__":
    main()
