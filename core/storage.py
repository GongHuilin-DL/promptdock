# -*- coding: utf-8 -*-
"""本地多文件提示语库：扫描 / 读取 / 写回 / 类别 / 设置。

支持 .json / .jsonl / .csv / .txt / .db(sqlite)。
所有数据就是 data/prompts/ 下的普通文件，用户可以直接用文本编辑器改，
然后在界面点「重新扫描并读取」即可生效；大数据量可拆成任意多个文件。
"""
from __future__ import annotations

import copy
import csv
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .models import DEFAULTS, normalize, to_export

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SUPPORTED = {".json", ".jsonl", ".csv", ".txt", ".db", ".sqlite", ".sqlite3"}
FMT_OF = {".json": "json", ".jsonl": "jsonl", ".csv": "csv", ".txt": "txt",
          ".db": "db", ".sqlite": "db", ".sqlite3": "db"}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "page_size": 24,
    "page_size_options": [8, 12, 24, 48, 96],
    "global_weight": 1.0,
    "syntax_profile": "sd",
    "custom_tpl": "({w}:{v})",
    "default_target_file": "99_自定义提示语.json",
    "translate": {
        "enabled": True,
        "provider": "gtx",
        "custom_endpoint": "",
        "target": "zh-CN",
        "timeout": 8,
    },
    "negative_presets": {
        "完整版（通用 / SD1.5）": "(worst quality, low quality:1.4), (lowres:1.2), bad anatomy, bad hands, missing fingers, extra digits, fused fingers, too many fingers, missing limbs, extra limbs, malformed limbs, mutated hands, poorly drawn hands, poorly drawn face, poorly drawn feet, disfigured, deformed, mutation, textureless, blurry, jpeg artifacts, watermark, signature, username, text, error, cropped, out of frame, low quality, normal quality, bad composition, tiling, airbrush, multiple views, multiple panels, monochrome, oversaturated, undersaturated, bad perspective, distorted, unnatural pose, cross-eyed, lazy eye, bad eyes, extra pupils, missing eyes, asymmetrical eyes, long neck, duplicate, morbid, mutilated, amputation, incomplete, unfinished, (bad proportions:1.2), cloned face, gross proportions, malformed, unclear details, static, noise, pixelated, overexposed, underexposed, flat lighting, harsh lighting, artifacts, glitch, distortion, unnatural colors, ugly, duplicate face, duplicate body, extra heads, faceless",
        "精简版 · 写实 / 摄影向": "(worst quality, low quality:1.4), lowres, bad anatomy, bad hands, missing fingers, extra digits, blurry, jpeg artifacts, watermark, text, signature, username, deformed, disfigured, mutated, out of frame, cropped, duplicate, morbid, mutilated, bad proportions, ugly",
        "精简版 · 动漫 / 插画向": "(worst quality, low quality:1.4), lowres, bad anatomy, bad hands, missing fingers, extra digits, bad eyes, multiple tails, extra tail, monochrome, sketch, watermark, signature, username, text, blurry, jpeg artifacts, out of frame, cropped, bad proportions, deformed, mutated, ugly",
        "文生视频通用负向词": "worst quality, low quality, flicker, temporal inconsistency, jitter, motion blur artifacts, deformed hands, extra limbs, distorted face, inconsistent character, warped background, frame tearing, sudden zoom, camera shake, watermark, text, subtitle, logo, oversaturated, blurry, jpeg artifacts",
    },
}


@dataclass
class Source:
    path: str
    rel: str
    fmt: str
    size: int = 0
    mtime: float = 0.0
    count: int = 0
    default_kind: str = "image"
    meta: Dict[str, Any] = field(default_factory=dict)
    header_lines: List[str] = field(default_factory=list)
    error: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def safe_name(name: str) -> str:
    name = os.path.basename(str(name or "").strip().replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f/\\:*?\"<>|]", "_", name)
    name = name.strip(". ")
    if not name:
        raise ValueError("文件名不能为空")
    return name


class Library:
    def __init__(self, data_dir: Optional[str] = None):
        self.root = os.path.abspath(data_dir or os.path.join(ROOT, "data"))
        self.prompts_dir = os.path.join(self.root, "prompts")
        self.config_dir = os.path.join(self.root, "config")
        os.makedirs(self.prompts_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        self.lock = threading.RLock()
        self.sources: List[Source] = []
        self.items: List[Dict[str, Any]] = []
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.categories: List[Dict[str, str]] = []
        self.settings: Dict[str, Any] = {}
        self.last_scan: float = 0.0
        self.last_load: float = 0.0
        self.duplicates: int = 0
        self.notices: List[str] = []
        self._ensure_config_files()
        self.reload()

    # ------------------------------------------------------------ 配置文件
    def _cfg(self, name: str) -> str:
        return os.path.join(self.config_dir, name)

    def _ensure_config_files(self):
        if not os.path.exists(self._cfg("settings.json")):
            self._dump_json(self._cfg("settings.json"), DEFAULT_SETTINGS)
        if not os.path.exists(self._cfg("categories.json")):
            self._dump_json(self._cfg("categories.json"), {"categories": []})
        if not os.path.exists(self._cfg("model_guides.json")):
            from .syntax import DEFAULT_GUIDES
            self._dump_json(self._cfg("model_guides.json"), {"guides": DEFAULT_GUIDES})

    @staticmethod
    def _dump_json(path: str, obj: Any):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def load_settings(self) -> Dict[str, Any]:
        try:
            with open(self._cfg("settings.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = copy.deepcopy(DEFAULT_SETTINGS)
            for k, v in (data or {}).items():
                if k == "translate" and isinstance(v, dict):
                    merged["translate"].update(v)
                elif k == "negative_presets" and isinstance(v, dict):
                    merged["negative_presets"] = dict(v)
                else:
                    merged[k] = v
            self.settings = merged
        except Exception as e:
            self.settings = copy.deepcopy(DEFAULT_SETTINGS)
            self.notices.append(f"settings.json 读取失败，已使用默认设置：{e}")
        return self.settings

    def save_settings(self, patch: Dict[str, Any]):
        with self.lock:
            s = copy.deepcopy(self.settings)
            for k, v in (patch or {}).items():
                if k == "translate" and isinstance(v, dict):
                    s.setdefault("translate", {}).update(v)
                else:
                    s[k] = v
            self._dump_json(self._cfg("settings.json"), s)
            self.settings = s
        return self.settings

    def load_categories(self) -> List[Dict[str, str]]:
        try:
            with open(self._cfg("categories.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("categories", []) if isinstance(data, dict) else data
            out = []
            for c in raw:
                if isinstance(c, str):
                    out.append({"name": c.strip(), "kind": "both", "note": ""})
                elif isinstance(c, dict) and str(c.get("name", "")).strip():
                    out.append({"name": str(c["name"]).strip(),
                                "kind": str(c.get("kind", "both")),
                                "note": str(c.get("note", ""))})
            self.categories = out
        except Exception as e:
            self.categories = []
            self.notices.append(f"categories.json 读取失败：{e}")
        return self.categories

    def save_categories(self):
        self._dump_json(self._cfg("categories.json"), {"categories": self.categories})

    # ------------------------------------------------------------ 扫描 / 读取
    def scan(self) -> List[Source]:
        found: List[Source] = []
        cfg_abs = os.path.abspath(self.config_dir)
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".") and d not in ("config", "exports")]
            if os.path.abspath(dirpath) == cfg_abs:
                continue
            for fn in sorted(filenames, key=_natural_key):
                if fn.startswith(".") or fn.endswith(".tmp"):
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext not in SUPPORTED:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    stt = os.stat(p)
                except OSError:
                    continue
                found.append(Source(path=p, rel=os.path.relpath(p, self.root).replace("\\", "/"),
                                    fmt=FMT_OF[ext], size=stt.st_size, mtime=stt.st_mtime))
        found.sort(key=lambda s: _natural_key(s.rel))
        with self.lock:
            self.sources = found
            self.last_scan = time.time()
        return found

    def reload(self):
        """重新扫描 + 重新读取全部文件（用户在外部编辑器改完文件后点这个）。"""
        self.notices = []
        self.load_settings()
        self.load_categories()
        sources = self.scan()
        merged: List[Dict[str, Any]] = []
        by_id: Dict[str, Dict[str, Any]] = {}
        dups = 0
        for s in sources:
            try:
                raw_items, meta, headers = _read_source(s.path, s.fmt)
                s.meta, s.header_lines = meta, headers
                s.default_kind = str(meta.get("default_kind", "image"))
                norm = []
                for i, raw in enumerate(raw_items):
                    it = normalize(raw, source=s.rel, default_kind=s.default_kind, index=i)
                    if it:
                        norm.append(it)
                s.items = norm
                s.count = len(norm)
                for it in norm:
                    if it["id"] in by_id:
                        dups += 1
                        # 同 id 视为同一条：后出现的补充先出现的空字段
                        for k, v in it.items():
                            if not by_id[it["id"]].get(k) and v:
                                by_id[it["id"]][k] = v
                        continue
                    by_id[it["id"]] = it
                    merged.append(it)
            except Exception as e:
                s.error = f"{type(e).__name__}: {e}"
                self.notices.append(f"⚠️ {s.rel} 读取失败：{s.error}")
        with self.lock:
            self.items, self.by_id, self.duplicates = merged, by_id, dups
            self.last_load = time.time()
            # 把条目里出现、但类别表里没有的类别自动补登记
            names = {c["name"] for c in self.categories}
            changed = False
            for it in merged:
                if it["category"] not in names:
                    names.add(it["category"])
                    self.categories.append({"name": it["category"], "kind": it["kind"], "note": ""})
                    changed = True
            if changed:
                self.save_categories()
        return merged

    # ------------------------------------------------------------ 查询
    def all_items(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(x) for x in self.items]

    def get(self, item_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            it = self.by_id.get(str(item_id))
            return dict(it) if it else None

    def category_names(self, kind: str = "both") -> List[str]:
        with self.lock:
            out = []
            for c in self.categories:
                if kind == "both" or c.get("kind") in ("both", kind):
                    out.append(c["name"])
            for it in self.items:
                if (kind == "both" or it["kind"] == kind) and it["category"] not in out:
                    out.append(it["category"])
            return sorted(set(out))

    def choices(self, kind: str = "both") -> Dict[str, List[str]]:
        items = [x for x in self.all_items() if kind == "both" or x["kind"] == kind]
        def uniq(key):
            vals = set()
            for it in items:
                v = it.get(key)
                if isinstance(v, list):
                    vals.update(str(z) for z in v if str(z).strip())
                elif v and str(v).strip():
                    vals.add(str(v).strip())
            return ["ALL"] + sorted(vals)
        return {"category": ["ALL"] + self.category_names(kind),
                "tech": uniq("tech"), "model": uniq("model"),
                "tag": ["ALL"] + sorted({t for it in items for t in it.get("tags", [])})}

    # ------------------------------------------------------------ 写回
    def _source_for(self, rel: str) -> Source:
        for s in self.sources:
            if s.rel == rel:
                return s
        raise KeyError(f"数据文件不存在：{rel}")

    def _persist(self, rels: Iterable[str]):
        """把内存里属于这些文件的条目整文件写回。"""
        with self.lock:
            group: Dict[str, List[Dict[str, Any]]] = {r: [] for r in set(rels)}
            for it in self.items:
                if it["source"] in group:
                    group[it["source"]].append(it)
            for rel, its in group.items():
                s = self._source_for(rel)
                _write_source(s, [to_export(x) for x in its])
                s.items = its
                s.count = len(its)
                s.error = ""
                stt = os.stat(s.path)
                s.size, s.mtime = stt.st_size, stt.st_mtime

    def _target_source(self, kind: str) -> Source:
        name = str(self.settings.get("default_target_file") or DEFAULT_SETTINGS["default_target_file"])
        rel = os.path.join("prompts", safe_name(name)).replace("\\", "/")
        p = os.path.join(self.root, rel)
        if not os.path.exists(p):
            self._dump_json(p, {"description": "用户自定义提示语（可在界面或直接编辑本文件）",
                               "default_kind": kind, "items": []})
            self.scan()
        return self._source_for(rel)

    def add_item(self, data: Dict[str, Any], source_rel: str = "") -> Dict[str, Any]:
        with self.lock:
            it = normalize(dict(data), source=source_rel, default_kind=data.get("kind", "image"))
            if not it:
                raise ValueError("提示语内容不能为空")
            if it["id"] in self.by_id:
                it["id"] = it["id"] + "-" + str(int(time.time() * 1000) % 100000)
            s = self._source_for(source_rel) if source_rel else self._target_source(it["kind"])
            it["source"] = s.rel
            self.items.append(it)
            self.by_id[it["id"]] = it
            if it["category"] not in [c["name"] for c in self.categories]:
                self.categories.append({"name": it["category"], "kind": it["kind"], "note": ""})
                self.save_categories()
            self._persist([s.rel])
            return dict(it)

    def update_item(self, item_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            old = self.by_id.get(str(item_id))
            if not old:
                raise KeyError("条目不存在，可能已被删除或数据文件已改动，请重新扫描读取")
            old_rel = old["source"]
            merged = dict(old)
            merged.update({k: v for k, v in patch.items() if k != "id"})
            new = normalize(merged, source=old_rel, default_kind=merged.get("kind", "image"))
            new["id"] = old["id"]
            new["source"] = old_rel
            self.by_id[old["id"]] = new
            self.items = [new if x["id"] == old["id"] else x for x in self.items]
            if new["category"] not in [c["name"] for c in self.categories]:
                self.categories.append({"name": new["category"], "kind": new["kind"], "note": ""})
                self.save_categories()
            self._persist([old_rel])
            return dict(new)

    def toggle_flag(self, item_id: str, field_name: str, value: Optional[bool] = None):
        with self.lock:
            it = self.by_id.get(str(item_id))
            if not it:
                raise KeyError("条目不存在")
            it[field_name] = (not bool(it.get(field_name))) if value is None else bool(value)
            self._persist([it["source"]])
            return bool(it[field_name])

    def delete_item(self, item_id: str):
        with self.lock:
            it = self.by_id.pop(str(item_id), None)
            if not it:
                raise KeyError("条目不存在")
            self.items = [x for x in self.items if x["id"] != str(item_id)]
            self._persist([it["source"]])

    # ------------------------------------------------------------ 类别
    def add_category(self, name: str, kind: str = "both", note: str = "") -> str:
        name = str(name).strip()
        if not name:
            raise ValueError("类别名不能为空")
        with self.lock:
            if name in [c["name"] for c in self.categories]:
                raise ValueError(f"类别「{name}」已存在，已拒绝本次操作")
            self.categories.append({"name": name, "kind": kind, "note": note})
            self.save_categories()
        return name

    def rename_category(self, old: str, new: str) -> int:
        new = str(new).strip()
        if not new:
            raise ValueError("新类别名不能为空")
        with self.lock:
            if new != old and new in [c["name"] for c in self.categories]:
                raise ValueError(f"类别「{new}」已存在，已拒绝重命名")
            affected = 0
            rels = set()
            for c in self.categories:
                if c["name"] == old:
                    c["name"] = new
            for it in self.items:
                if it["category"] == old:
                    it["category"] = new
                    rels.add(it["source"])
                    affected += 1
            self.save_categories()
            if rels:
                self._persist(rels)
            return affected

    def delete_category(self, name: str) -> int:
        with self.lock:
            doomed = [x for x in self.items if x["category"] == name]
            rels = {x["source"] for x in doomed}
            ids = {x["id"] for x in doomed}
            self.items = [x for x in self.items if x["id"] not in ids]
            for i in ids:
                self.by_id.pop(i, None)
            self.categories = [c for c in self.categories if c["name"] != name]
            self.save_categories()
            if rels:
                self._persist(rels)
            return len(doomed)

    def category_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for it in self.items:
            out[it["category"]] = out.get(it["category"], 0) + 1
        return out

    # ------------------------------------------------------------ 数据文件
    def create_file(self, name: str, fmt: str = "json", kind: str = "image",
                    description: str = "") -> str:
        fn = safe_name(name)
        base, ext = os.path.splitext(fn)
        ext = ext.lower()
        if ext not in SUPPORTED:
            ext = {"json": ".json", "jsonl": ".jsonl", "csv": ".csv",
                   "txt": ".txt", "db": ".db"}.get(fmt, ".json")
            fn = base + ext
        p = os.path.join(self.prompts_dir, fn)
        if os.path.exists(p):
            raise ValueError(f"文件「{fn}」已存在，请换一个名字")
        if FMT_OF[ext] == "json":
            self._dump_json(p, {"description": description or "用户新增提示语数据文件",
                                "default_kind": kind, "items": []})
        elif FMT_OF[ext] == "jsonl":
            with open(p, "w", encoding="utf-8") as f:
                f.write("# 每行一个 JSON 对象，至少包含 prompt 字段\n")
        elif FMT_OF[ext] == "csv":
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow(["prompt", "category", "kind", "tip", "tech", "model"])
        elif FMT_OF[ext] == "txt":
            with open(p, "w", encoding="utf-8") as f:
                f.write(f"# 每行一条提示语，也可用 ||| 分隔：提示语 ||| 类别 ||| 技巧说明\n")
                f.write(f"# 本文件默认类型：{kind}\n")
        else:
            con = sqlite3.connect(p)
            con.execute("CREATE TABLE IF NOT EXISTS prompts (id TEXT PRIMARY KEY, payload TEXT)")
            con.commit()
            con.close()
        self.scan()
        return os.path.join("prompts", fn).replace("\\", "/")

    def delete_file(self, rel: str) -> int:
        with self.lock:
            s = self._source_for(rel)
            n = s.count
            os.remove(s.path)
            self.items = [x for x in self.items if x["source"] != rel]
            self.by_id = {k: v for k, v in self.by_id.items() if v["source"] != rel}
            self.scan()
            return n

    def read_raw(self, rel: str) -> str:
        s = self._source_for(rel)
        if s.fmt == "db":
            return ("[SQLite 数据库文件] 请用界面里的条目编辑功能修改，或用 SQLite 工具打开：\n"
                    + os.path.abspath(s.path) + "\n\n表 prompts(id TEXT, payload TEXT)")
        with open(s.path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()

    def save_raw(self, rel: str, text: str):
        s = self._source_for(rel)
        if s.fmt == "db":
            raise ValueError("SQLite 文件请在界面里通过条目编辑修改，不能直接写文本")
        tmp = s.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, s.path)
        self.reload()

    def source_rows(self) -> List[Dict[str, Any]]:
        return [dict(rel=s.rel, fmt=s.fmt, count=s.count, size=s.size,
                     mtime=s.mtime, error=s.error,
                     default_kind=s.default_kind,
                     path=os.path.abspath(s.path)) for s in self.sources]

    def stats(self) -> Dict[str, int]:
        with self.lock:
            return {"total": len(self.items),
                    "image": sum(1 for x in self.items if x["kind"] == "image"),
                    "video": sum(1 for x in self.items if x["kind"] == "video"),
                    "favorite": sum(1 for x in self.items if x.get("favorite")),
                    "like": sum(1 for x in self.items if x.get("like")),
                    "categories": len(self.categories),
                    "files": len(self.sources)}


# ---------------------------------------------------------------- 文件读写实现
def _read_source(path: str, fmt: str):
    meta: Dict[str, Any] = {}
    headers: List[str] = []
    if fmt == "json":
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data, meta, headers
        if isinstance(data, dict):
            meta = {k: v for k, v in data.items() if k != "items"}
            items = data.get("items", [])
            if isinstance(items, dict):
                items = list(items.values())
            return items, meta, headers
        raise ValueError("JSON 顶层必须是数组或含 items 的对象")
    if fmt == "jsonl":
        out = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                t = line.strip()
                if not t:
                    continue
                if t.startswith("#"):
                    headers.append(line.rstrip("\n"))
                    continue
                out.append(json.loads(t))
        return out, meta, headers
    if fmt == "csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f)), meta, headers
    if fmt == "txt":
        out = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                if line.lstrip().startswith("#"):
                    headers.append(line.rstrip("\n"))
                    continue
                t = line.strip()
                if t:
                    out.append(t)
        # 从注释里猜 default_kind
        for h in headers:
            if "video" in h.lower() or "视频" in h:
                meta["default_kind"] = "video"
        return out, meta, headers
    if fmt == "db":
        con = sqlite3.connect(path)
        try:
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            if "prompts" not in tables:
                return [], meta, headers
            cur = con.execute("SELECT * FROM prompts")
            cols = [d[0] for d in cur.description]
            rows = []
            for r in cur.fetchall():
                d = dict(zip(cols, r))
                if "payload" in d and d["payload"]:
                    try:
                        d = json.loads(d["payload"])
                    except Exception:
                        pass
                rows.append(d)
            return rows, meta, headers
        finally:
            con.close()
    raise ValueError(f"不支持的格式：{fmt}")


def _write_source(s: Source, items: List[Dict[str, Any]]):
    p = s.path
    if s.fmt == "json":
        if s.meta:
            obj = dict(s.meta)
            obj["items"] = items
        else:
            obj = items
        Library._dump_json(p, obj)
    elif s.fmt == "jsonl":
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for h in s.header_lines:
                f.write(h + "\n")
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        os.replace(tmp, p)
    elif s.fmt == "csv":
        cols: List[str] = []
        for it in items:
            for k in it:
                if k not in cols:
                    cols.append(k)
        if not cols:
            cols = ["prompt", "category", "kind"]
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for it in items:
                row = {}
                for k in cols:
                    v = it.get(k, "")
                    row[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                w.writerow(row)
        os.replace(tmp, p)
    elif s.fmt == "txt":
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for h in s.header_lines:
                f.write(h + "\n")
            for it in items:
                f.write(str(it.get("prompt", "")).replace("\n", " ") + "\n")
        os.replace(tmp, p)
    elif s.fmt == "db":
        con = sqlite3.connect(p)
        try:
            con.execute("CREATE TABLE IF NOT EXISTS prompts (id TEXT PRIMARY KEY, payload TEXT)")
            con.execute("DELETE FROM prompts")
            con.executemany("INSERT OR REPLACE INTO prompts(id,payload) VALUES(?,?)",
                            [(str(it.get("id")), json.dumps(it, ensure_ascii=False)) for it in items])
            con.commit()
        finally:
            con.close()
    else:
        raise ValueError(f"不支持写回：{s.fmt}")
