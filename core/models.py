# -*- coding: utf-8 -*-
"""提示语条目模型：宽松 schema，允许用户手写的文件缺字段、加字段。"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable

KINDS = ("image", "video")
KIND_LABEL = {"image": "文生图", "video": "文生视频"}

# 缺字段时的默认值。用户文件里没写的字段会自动补齐；用户多写的字段原样保留。
DEFAULTS: Dict[str, Any] = {
    "id": "",
    "kind": "image",
    "category": "未分类",
    "prompt": "",
    "negative": "",
    "tip": "",
    "tech": "自定义",
    "tags": [],
    "model": "通用",
    "syntax": "",          # 空 = 跟随全局权重语法配置
    "subject": "",         # 主体短语，用于「主体前置权重」滑块
    "camera": "",          # 文生视频：运镜 / 镜头运动
    "duration": "",        # 文生视频：时长
    "motion": "",          # 文生视频：运动强度
    "fps": "",
    "like": False,
    "favorite": False,
    "source": "",          # 所属数据文件（相对路径），由加载器写入
}

BOOL_FIELDS = ("like", "favorite")
LIST_FIELDS = ("tags",)


def stable_id(item: Dict[str, Any], source: str = "") -> str:
    """没有显式 id 时，用内容生成稳定 id：用户调整顺序不会导致收藏状态丢失。"""
    raw = f"{item.get('kind','image')}|{item.get('prompt','')}|{source}"
    return "p-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def normalize(raw: Any, *, source: str = "", default_kind: str = "image",
              index: int = 0) -> Dict[str, Any] | None:
    """把任意来源的一行数据归一化成条目 dict；无法识别时返回 None。"""
    if raw is None:
        return None
    if isinstance(raw, str):
        line = raw.strip()
        if not line or line.startswith("#"):
            return None
        # 纯文本 / CSV 的一行：支持 "prompt ||| category ||| tip" 简易写法
        parts = [p.strip() for p in line.split("|||")]
        raw = {"prompt": parts[0], "category": parts[1] if len(parts) > 1 else "",
               "tip": parts[2] if len(parts) > 2 else ""}
    if not isinstance(raw, dict):
        return None

    it: Dict[str, Any] = dict(raw)          # 保留用户自定义字段
    for k, v in DEFAULTS.items():
        if k not in it or it[k] is None or it[k] == "":
            it[k] = (list(v) if isinstance(v, list) else v)

    prompt = str(it.get("prompt", "")).strip()
    if not prompt:
        return None
    it["prompt"] = prompt
    it["kind"] = str(it.get("kind") or default_kind).strip().lower()
    if it["kind"] not in KINDS:
        it["kind"] = "image"
    it["category"] = str(it.get("category") or "未分类").strip()
    it["tech"] = str(it.get("tech") or "自定义").strip()
    it["model"] = str(it.get("model") or "通用").strip()
    it["subject"] = str(it.get("subject") or _guess_subject(prompt)).strip()
    for b in BOOL_FIELDS:
        it[b] = _as_bool(it.get(b))
    for lf in LIST_FIELDS:
        it[lf] = _as_list(it.get(lf))
    it["source"] = source
    if not str(it.get("id", "")).strip():
        it["id"] = stable_id(it, source)
    it["id"] = str(it["id"]).strip()
    return it


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on", "是", "收藏", "喜欢")


def _as_list(v: Any) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if v is None or v == "":
        return []
    s = str(v).strip()
    return [x.strip() for x in re.split(r"[,，;；|]+", s) if x.strip()]


def _guess_subject(prompt: str) -> str:
    """取第一个逗号前的短语做主体，去掉权重括号。"""
    head = prompt.split(",")[0].strip()
    head = re.sub(r"[()\[\]{}<>]", "", head).split(":")[0].strip()
    return head[:60]


def to_export(it: Dict[str, Any]) -> Dict[str, Any]:
    """写回文件时剔除内部字段，保留用户自定义字段。"""
    out = {k: v for k, v in it.items() if k != "source"}
    return out


def iter_brief(items: Iterable[Dict[str, Any]]) -> str:
    return "\n".join(f"#{it['id']} [{it['category']}] {it['prompt']}" for it in items)
