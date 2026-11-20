# -*- coding: utf-8 -*-
"""在线免费翻译（仅在用户手动点击时调用，绝不后台自动请求）。

默认走 Google 免费公开接口 gtx（无需 API Key），失败自动回退 MyMemory；
也可以在设置里填自建 / 公共 LibreTranslate 端点。全部使用标准库，无额外依赖。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Tuple

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 SD-Prompt-Manager/1.0"
GTX = "https://translate.googleapis.com/translate_a/single"
MYMEMORY = "https://api.mymemory.translated.net/get"

LANG_CHOICES = {
    "中文": "zh-CN", "英文": "en", "日文": "ja", "韩文": "ko",
    "法文": "fr", "德文": "de", "西班牙文": "es", "俄文": "ru",
}


def _http_get(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _http_post_json(url: str, payload: dict, timeout: int) -> str:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def looks_chinese(text: str) -> bool:
    sample = text[:600]
    if not sample:
        return False
    han = len(re.findall(r"[\u4e00-\u9fff]", sample))
    return han / max(1, len(sample)) > 0.12


def split_chunks(text: str, limit: int = 1800) -> list:
    """按行/句切块，避免单次请求过长；尽量不切断一条提示词。"""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    parts, buf = [], ""
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > limit and buf:
            parts.append(buf)
            buf = ""
        if len(line) > limit:
            for i in range(0, len(line), limit):
                parts.append(line[i:i + limit])
        else:
            buf += line
    if buf.strip():
        parts.append(buf)
    return parts


def _gtx(text: str, sl: str, tl: str, timeout: int) -> str:
    q = urllib.parse.urlencode({"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": text})
    raw = _http_get(GTX + "?" + q, timeout)
    data = json.loads(raw)
    out = []
    for seg in data[0] or []:
        if seg and isinstance(seg, list) and seg[0]:
            out.append(str(seg[0]))
    return "".join(out).strip()


def _mymemory(text: str, sl: str, tl: str, timeout: int) -> str:
    langpair = f"{sl}|{tl}"
    q = urllib.parse.urlencode({"q": text, "langpair": langpair})
    raw = _http_get(MYMEMORY + "?" + q, timeout)
    data = json.loads(raw)
    return str(data.get("responseData", {}).get("translatedText", "")).strip()


def _libre(text: str, sl: str, tl: str, endpoint: str, timeout: int) -> str:
    url = endpoint.strip().rstrip("/")
    if not url.endswith("/translate"):
        url += "/translate"
    raw = _http_post_json(url, {"q": text, "source": sl, "target": tl, "format": "text"}, timeout)
    data = json.loads(raw)
    return str(data.get("translatedText", "")).strip()


def translate(text: str, *, target: str = "zh-CN", provider: str = "gtx",
              custom_endpoint: str = "", timeout: int = 8,
              auto_reverse: bool = True) -> Tuple[bool, str, str]:
    """返回 (是否成功, 译文, 说明)。任何网络异常都会被收敛成可读提示。"""
    text = (text or "").strip()
    if not text:
        return False, "", "没有可翻译的内容。"
    if provider == "off":
        return False, "", "翻译已在设置中关闭。"

    src_cn = looks_chinese(text)
    tl = target if target in LANG_CHOICES.values() else "zh-CN"
    sl = "auto"
    if auto_reverse:
        # 自动互译：原文中文 → 译成英文；原文英文 → 译成所选目标（默认中文）
        if src_cn and tl.startswith("zh"):
            tl = "en"
        elif not src_cn and tl == "en":
            tl = "zh-CN"
    note = f"方向：{'中→英' if tl == 'en' else ('中/自动→' + tl)}"
    timeout = max(3, min(30, int(timeout or 8)))

    chunks = split_chunks(text)
    out, used = [], ""
    for ch in chunks:
        got = ""
        errors = []
        order = []
        if provider == "libre" and custom_endpoint:
            order = ["libre"]
        elif provider == "mymemory":
            order = ["mymemory", "gtx"]
        else:
            order = ["gtx", "mymemory"]
        for name in order:
            try:
                if name == "gtx":
                    got = _gtx(ch, sl, tl, timeout)
                elif name == "mymemory":
                    got = _mymemory(ch, "zh-CN" if src_cn else "en", tl, timeout)
                else:
                    got = _libre(ch, "auto" if sl == "auto" else sl, tl, custom_endpoint, timeout)
                if got:
                    used = {"gtx": "Google 免费接口 (gtx)", "mymemory": "MyMemory",
                            "libre": "LibreTranslate"}[name]
                    break
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}")
            got = ""
        if not got:
            return False, "", (f"翻译失败（{', '.join(errors) or '无可用端点'}）。"
                               "请检查网络，或在「设置」里切换翻译服务 / 填写自建端点。")
        out.append(got)
    return True, "\n".join(out), f"✅ 已通过 {used} 翻译 · {note} · 共 {len(chunks)} 段"
