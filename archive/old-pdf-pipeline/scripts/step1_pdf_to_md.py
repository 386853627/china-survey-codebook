"""Step 1: PDF → Markdown（通过 MinerU API）

用法:
    python scripts/step1_pdf_to_md.py [--year 2017]

环境变量:
    MINERU_API_KEY  MinerU API 密钥（优先 .env 文件，其次系统环境）
"""

import os
import time
import json
import argparse
from pathlib import Path
from typing import Optional

import requests

from utils import get_data_dir, get_env, get_project_root


MINERU_API_BASE = "https://mineru.net/api/v4"
MINERU_UPLOAD_URL = f"{MINERU_API_BASE}/file-urls/batch"
MINERU_EXTRACT_URL = f"{MINERU_API_BASE}/extract/task"
POLL_INTERVAL = 5  # 轮询间隔（秒）
MAX_POLL_TIME = 600  # 最大等待时间（秒）


def get_api_key() -> str:
    """获取 MinerU API Key"""
    key = get_env("MINERU_API_KEY", "")
    if not key:
        raise RuntimeError(
            "未找到 MINERU_API_KEY。请在 .env 文件中设置:\n"
            "  MINERU_API_KEY=your_key_here"
        )
    return key


def list_pdfs(year: Optional[int] = None) -> list[Path]:
    """列出 data/pdf/ 下待转换的 PDF 文件"""
    pdf_dir = get_data_dir("pdf")
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if year is not None:
        # 尝试匹配年份（支持 CGSS2017.pdf、CGSS2017_问卷.pdf 等命名）
        pdfs = [p for p in pdfs if str(year) in p.stem]
    return pdfs


def upload_pdf(filepath: Path, api_key: str) -> str:
    """上传 PDF，返回 file_url"""
    print(f"  [上传] {filepath.name} ...")
    with open(filepath, "rb") as f:
        resp = requests.post(
            MINERU_UPLOAD_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            files={"file": (filepath.name, f, "application/pdf")},
            data={"language": "ch"},
        )
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"上传失败: {result}")
    file_urls = result.get("data", {}).get("file_urls", [])
    if not file_urls:
        raise RuntimeError(f"上传成功但未返回 file_url: {result}")
    return file_urls[0]


def start_extraction(file_url: str, api_key: str) -> str:
    """启动解析任务，返回 task_id"""
    print(f"  [启动解析] ...")
    resp = requests.post(
        MINERU_EXTRACT_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "file_url": file_url,
            "enable_formula": True,
            "enable_table": True,
            "layout_model": "doclayout_yolo",
            "language": "ch",
        },
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"启动解析失败: {result}")
    task_id = result.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"未获取到 task_id: {result}")
    return task_id


def poll_extraction(task_id: str, api_key: str) -> Optional[str]:
    """轮询解析状态，完成时返回 Markdown 内容"""
    elapsed = 0
    while elapsed < MAX_POLL_TIME:
        resp = requests.get(
            f"{MINERU_EXTRACT_URL}/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        result = resp.json()
        status = result.get("data", {}).get("status", "")
        if status == "done":
            md_url = result.get("data", {}).get("md_file_url", "")
            if md_url:
                md_resp = requests.get(md_url)
                md_resp.raise_for_status()
                return md_resp.text
            else:
                # 有些版本直接返回 content
                return result.get("data", {}).get("content", "")
        elif status == "failed":
            raise RuntimeError(f"解析失败: {result}")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        print(f"    等待中... ({elapsed}s)")
    raise TimeoutError(f"解析超时 ({MAX_POLL_TIME}s)")


def extract_year_from_filename(filepath: Path) -> int:
    """从文件名提取年份，如 CGSS2017_问卷.pdf → 2017"""
    import re
    match = re.search(r"(\d{4})", filepath.stem)
    if match:
        return int(match.group(1))
    return 0


def process_pdf(filepath: Path, api_key: str) -> Path:
    """处理单个 PDF：上传 → 解析 → 保存 Markdown"""
    year = extract_year_from_filename(filepath)
    label = f"CGSS{year}" if year else filepath.stem

    file_url = upload_pdf(filepath, api_key)
    task_id = start_extraction(file_url, api_key)
    print(f"  [解析中] task_id={task_id}, 请等待...")
    md_content = poll_extraction(task_id, api_key)

    out_path = get_data_dir("markdown") / f"{label}.md"
    out_path.write_text(md_content, encoding="utf-8")
    print(f"  [完成] → {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="PDF → Markdown（MinerU API）")
    parser.add_argument("--year", type=int, help="仅转换指定年份")
    parser.add_argument("--file", type=str, help="仅转换指定文件")
    args = parser.parse_args()

    api_key = get_api_key()

    if args.file:
        pdfs = [Path(args.file)]
    else:
        pdfs = list_pdfs(year=args.year)

    if not pdfs:
        print("未找到 PDF 文件。请将问卷 PDF 放入 data/pdf/ 目录。")
        return

    print(f"待转换: {len(pdfs)} 个文件\n")

    results = []
    for i, pdf in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] {pdf.name}")
        try:
            out = process_pdf(pdf, api_key)
            results.append((pdf.name, "成功", str(out)))
        except Exception as e:
            print(f"  [失败] {e}")
            results.append((pdf.name, "失败", str(e)))
        print()

    # 汇总
    print("=" * 60)
    success = sum(1 for r in results if r[1] == "成功")
    print(f"完成: {success}/{len(results)}")


if __name__ == "__main__":
    main()
