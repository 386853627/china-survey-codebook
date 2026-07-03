"""CGSS 问卷资料库 — 公共工具函数"""

import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    """返回项目根目录（scripts/ 的上级目录）"""
    return Path(__file__).resolve().parent.parent


def get_data_dir(subdir: str = "") -> Path:
    """返回 data/ 目录或其子目录"""
    p = get_project_root() / "data" / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_path() -> Path:
    """返回 SQLite 数据库路径"""
    return get_data_dir() / "cgss.db"


def get_env(key: str, default: str = "") -> str:
    """读取环境变量，优先 .env 文件，其次系统环境"""
    try:
        from dotenv import load_dotenv
        load_dotenv(get_project_root() / ".env")
    except ImportError:
        pass
    return os.environ.get(key, default)


def ensure_dirs():
    """确保所有必需目录存在"""
    for d in ["data/pdf", "data/markdown", "data/json"]:
        (get_project_root() / d).mkdir(parents=True, exist_ok=True)
