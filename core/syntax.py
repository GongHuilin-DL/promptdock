# -*- coding: utf-8 -*-
"""权重语法画像 + 主流模型/推理框架的撰写规范。

设计要点：不同模型的权重写法不同，本模块把「解析正则」和「渲染模板」抽成画像，
卡片里的滑块、复制文本、导出的提示词都走同一套模板，因此换模型不用改 UI。
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(HERE), "data", "config")


@dataclass
class Profile:
    key: str
    name: str
    pattern: Optional[str]          # 数值权重的正则；None = 该模型不用数值权重
    tpl: str                        # 滑块改写时使用的模板，含 {w} {v}
    allow_prefix: bool              # 是否允许「主体前置权重」滑块
    note: str = ""
    neg_label: str = "负面提示词"

    def render(self, word: str, value: float) -> str:
        return self.tpl.replace("{w}", word).replace("{v}", fmt(value))

    def render_lora(self, word: str, value: float) -> str:
        return f"<lora:{word}:{fmt(value)}>"


def fmt(v: float) -> str:
    s = f"{float(v):.2f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


PROFILES: Dict[str, Profile] = {
    "sd": Profile(
        "sd", "Stable Diffusion / WebUI / ComfyUI  ·  (word:1.2)",
        r"\(([^()<>]*?):(\d*\.?\d+)\)", "({w}:{v})", True,
        "最通用的加权写法；>1 加强、<1 压低；(word)≈1.1、[word]≈0.9、((word))≈1.21。",
        "负面提示词（Negative Prompt）"),
    "flux": Profile(
        "flux", "FLUX.1 / SD3 / Sora / Kling  ·  自然语言长句",
        None, "({w}:{v})", False,
        "这类模型偏好完整描述句，堆权重词反而伤画质；靠「主体—环境—光—镜头—风格」顺序控制重点。",
        "负向描述（部分模型不支持，可留空）"),
    "mj": Profile(
        "mj", "Midjourney  ·  word::1.2  +  --参数",
        r"([^\s,，:：()]+)::(\d*\.?\d+)", "{w}::{v}", False,
        "多重提示用 :: 分配权重，画面参数写在末尾 --ar 16:9 --stylize 250 --no ...。",
        "--no 排除项"),
    "comfy": Profile(
        "comfy", "ComfyUI 条件加权  ·  (word:1.2) + 分步语法",
        r"\(([^()<>]*?):(\d*\.?\d+)\)", "({w}:{v})", True,
        "与 WebUI 一致，额外可用 (A:B:0.6) 分步混合、[from:to:0.5] 分步替换、AND / BREAK。",
        "负面条件节点"),
    "wan": Profile(
        "wan", "Wan / HunyuanVideo / CogVideoX  ·  中英长句 + 运镜",
        None, "({w}:{v})", False,
        "视频模型重点写「主体动作 + 镜头运动 + 时间变化 + 光影连贯」，避免堆静态画质词。",
        "负向提示（motion artifacts 等）"),
    "custom": Profile(
        "custom", "自定义模板  ·  使用设置里的 {w} / {v}",
        r"\(([^()<>]*?):(\d*\.?\d+)\)", "({w}:{v})", True,
        "解析沿用 (word:1.2)，但滑块改写时按你在设置里自定义的模板输出。",
        "负面提示词"),
}

LORA_RE = re.compile(r"<lora:([^:>]+):(\d*\.?\d+)>")
STEP_RE = re.compile(r"\[([^\[\]:]+):([^\[\]:]+):(\d*\.?\d+)\]")


@dataclass
class Token:
    start: int
    end: int
    raw: str
    word: str
    value: float
    type: str = "w"          # w | lora | step
    tpl: str = "({w}:{v})"


def get_profile(key: str, custom_tpl: str = "({w}:{v})") -> Profile:
    p = PROFILES.get(key or "sd", PROFILES["sd"])
    if key == "custom":
        tpl = (custom_tpl or "({w}:{v})").strip()
        if "{w}" not in tpl or "{v}" not in tpl:
            tpl = "({w}:{v})"
        # 用 dataclasses.replace 生成副本，避免污染全局
        import copy
        p = copy.copy(p)
        p.tpl = tpl
    return p


def tokenize(prompt: str, profile: Profile) -> List[Token]:
    """把提示词里可调权重的片段切成 token，供卡片滑块与高亮使用。"""
    found: List[Token] = []
    for m in LORA_RE.finditer(prompt):
        found.append(Token(m.start(), m.end(), m.group(0), m.group(1),
                           float(m.group(2)), "lora", "<lora:{w}:{v}>"))
    for m in STEP_RE.finditer(prompt):
        found.append(Token(m.start(), m.end(), m.group(0), m.group(1),
                           float(m.group(3)), "step", "[{w}:" + m.group(2) + ":{v}]"))
    if profile.pattern:
        for m in re.finditer(profile.pattern, prompt):
            word = m.group(1).strip()
            # (A:B:0.6) 是分步混合语法，不是权重块，跳过
            if ":" in word or word.startswith("<"):
                continue
            try:
                val = float(m.group(2))
            except ValueError:
                continue
            found.append(Token(m.start(), m.end(), m.group(0), word, val, "w", profile.tpl))
    # 去掉被更大 token 包住的重叠项，按出现顺序排列
    found.sort(key=lambda t: (t.start, -(t.end - t.start)))
    keep: List[Token] = []
    last = -1
    for t in found:
        if t.start >= last:
            keep.append(t)
            last = t.end
    return keep


def rebuild(prompt: str, tokens: List[Token], values: Dict[int, float],
            global_mul: float = 1.0, profile: Optional[Profile] = None) -> str:
    """按滑块值重建提示词（后端导出 / 预览用，与前端 JS 逻辑一致）。"""
    profile = profile or PROFILES["sd"]
    out, cur = [], 0
    for i, t in enumerate(tokens):
        out.append(prompt[cur:t.start])
        v = values.get(i, t.value)
        if t.type == "w":
            v = v * global_mul
        if t.type == "lora":
            out.append(f"<lora:{t.word}:{fmt(v)}>")
        elif t.type == "step":
            out.append(t.tpl.replace("{w}", t.word).replace("{v}", fmt(v)))
        else:
            out.append(profile.render(t.word, v) if t.tpl == profile.tpl
                       else t.tpl.replace("{w}", t.word).replace("{v}", fmt(v)))
        cur = t.end
    out.append(prompt[cur:])
    return "".join(out)


def apply_prefix(prompt: str, subject: str, value: float) -> str:
    if abs(value - 1.0) < 1e-6 or not subject:
        return prompt
    return f"({subject}:{fmt(value)}), {prompt}"


# ------------------------------------------------------------------ 模型指南
DEFAULT_GUIDES = [
    {"name": "SD 1.5", "type": "image", "syntax": "sd",
     "structure": "(masterpiece, best quality:1.2), 主体, 细节, 环境, 光线, 镜头, 风格, 8k",
     "negative": "强依赖负面词，建议用完整版。",
     "tips": "画质前缀非常有效；75 token 分段可用 BREAK；负面词影响大。",
     "example": "(masterpiece, best quality:1.2), (1girl:1.2), garden, soft light, 85mm, film grain"},
    {"name": "SDXL / SDXL-Turbo", "type": "image", "syntax": "sd",
     "structure": "自然语言短句 + 主体细节 + 光线 + 风格，画质词精简",
     "negative": "依赖降低，保留 worst quality / blurry / watermark 即可。",
     "tips": "支持双文本编码器；过长负面词反而压画质；分辨率建议 1024 起。",
     "example": "A close-up portrait of an elderly fisherman, golden hour rim light, 85mm, photorealistic"},
    {"name": "FLUX.1 / SD3", "type": "image", "syntax": "flux",
     "structure": "一整段完整描述句：主体 → 动作 → 环境 → 光线 → 镜头 → 风格 → 细节",
     "negative": "多数实现无负面栏，靠正向描述规避问题。",
     "tips": "不用权重括号、不堆 masterpiece；写具体材质与光，别写抽象画质词。",
     "example": "A highly detailed photograph of a glassblower at work in a warm workshop, soft directional window light, natural skin texture, shallow depth of field"},
    {"name": "Pony / 动漫系", "type": "image", "syntax": "sd",
     "structure": "score_9, score_8_up, 主体标签, 表情, 服装, 背景, 光线",
     "negative": "建议补 bad eyes / extra tail / monochrome。",
     "tips": "评分触发词放最前；标签式逗号分隔优于长句。",
     "example": "score_9, score_8_up, anime, 1girl, expressive eyes, cel shading, cherry blossoms"},
    {"name": "Midjourney v6 / v7", "type": "image", "syntax": "mj",
     "structure": "描述句, 风格与镜头词 --ar 16:9 --stylize 250 --no 排除项",
     "negative": "用 --no 参数，不设独立负面栏。",
     "tips": "多概念权重 word::2；参数全部写在末尾；--iw 控制参考图权重。",
     "example": "cinematic portrait of a diver, bioluminescent water::2, 85mm --ar 3:4 --no text, watermark"},
    {"name": "Qwen-Image / 即梦 / 国产中文模型", "type": "image", "syntax": "flux",
     "structure": "中文完整描述：主体 + 细节 + 环境 + 光线 + 构图 + 风格",
     "negative": "按平台实现，通常可选。",
     "tips": "中文语义理解好，写具体名词与空间关系；文字渲染可直接在提示词里加引号。",
     "example": "一位穿汉服的女子站在雨后的苏州园林里，柔和的午后侧光，浅景深，写实摄影"},
    {"name": "Sora 2 / OpenAI 视频", "type": "video", "syntax": "flux",
     "structure": "一段完整的镜头描述：主体 + 连续动作 + 镜头运动 + 环境变化 + 光线 + 时长/节奏",
     "negative": "通常无负面栏，靠描述规避。",
     "tips": "强调时间连续与物理合理；一次只写一个镜头、一个主体动作。",
     "example": "A single continuous tracking shot follows a cyclist along a coastal road at dawn, camera gliding beside them, long shadows, gentle ocean mist, 8 seconds"},
    {"name": "Kling 可灵 / Runway Gen-3·4", "type": "video", "syntax": "wan",
     "structure": "主体动作, 镜头运动(pan/tilt/dolly/zoom), 环境, 光线, 风格, 运动强度",
     "negative": "建议写 motion blur, flicker, deformed hands, inconsistent character。",
     "tips": "运镜词单独写最有效；避免多个动作同时发生；可配合首尾帧。",
     "example": "A woman in a red coat walks through falling snow, slow dolly-in, soft overcast light, subtle motion, cinematic, 5s"},
    {"name": "Wan2.x / HunyuanVideo / CogVideoX", "type": "video", "syntax": "wan",
     "structure": "中文或英文长句 + 主体动作 + 镜头 + 光影 + 细节；可加 motion amplitude",
     "negative": "建议写 抖动、闪烁、肢体畸形、画面撕裂。",
     "tips": "中英均可；动态幅度别写太满，容易崩；固定 seed 便于对比。",
     "example": "镜头缓慢推进，一只白猫在窗台上伸懒腰，午后阳光穿过窗帘，毛发细节清晰，画面稳定"},
    {"name": "AnimateDiff / Pika / Luma / Vidu / 海螺", "type": "video", "syntax": "flux",
     "structure": "正向提示词 + LoRA/运动模块 + 帧数 fps + 镜头运动词",
     "negative": "沿用 SD 系负面词，并补 flicker / temporal inconsistency。",
     "tips": "AnimateDiff 需要配合运动 LoRA；帧数与 fps 影响连贯性；避免剧烈形变。",
     "example": "slow camera pan over a lavender field at sunrise, gentle breeze, bees drifting, 16 fps, 4s, cinematic"},
]


def load_guides() -> List[Dict[str, Any]]:
    path = os.path.join(CONFIG_DIR, "model_guides.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("guides", [])
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return DEFAULT_GUIDES


def guides_html() -> str:
    rows = []
    for g in load_guides():
        badge = "🎬" if g.get("type") == "video" else "🖼️"
        rows.append(
            "<tr><td><b>{} {}</b><br><span class='mini'>{}</span></td>"
            "<td><code>{}</code></td><td>{}</td><td>{}</td>"
            "<td><code>{}</code></td></tr>".format(
                badge, html.escape(str(g.get("name", ""))),
                html.escape(str(g.get("syntax", ""))),
                html.escape(str(g.get("structure", ""))),
                html.escape(str(g.get("negative", ""))),
                html.escape(str(g.get("tips", ""))),
                html.escape(str(g.get("example", "")))))
    return ("<table class='cheat'><thead><tr><th>模型 / 框架</th><th>推荐结构</th>"
            "<th>负面词策略</th><th>关键技巧</th><th>示例</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


CHEATSHEET_HTML = """
<details class="sd-details" open>
  <summary>① 提示词结构速览 · 权重语法小抄</summary>
  <div class="sd-details-body">
    <p><b>通用结构：</b><code>主体 + 动作/细节 + 环境 + 光线 + 镜头/运镜 + 风格 + 画质</code>。越靠前的词权重越高；逗号分段利于 SD 系解析，完整长句利于 FLUX / 视频模型。</p>
    <table class="cheat">
      <thead><tr><th>语法</th><th>写法</th><th>作用</th></tr></thead><tbody>
      <tr><td>加权 / 降权</td><td><code>(word:1.3)</code> / <code>(word:0.7)</code></td><td>&gt;1 加强，&lt;1 压低，1.2~1.4 最稳</td></tr>
      <tr><td>简写</td><td><code>(word)</code>≈1.1 · <code>((word))</code>≈1.21 · <code>[word]</code>≈0.9</td><td>括号叠乘、方括号递减</td></tr>
      <tr><td>分步混合</td><td><code>(A:B:0.6)</code></td><td>采样到 60% 时从 A 切到 B</td></tr>
      <tr><td>分步替换</td><td><code>[from:to:0.5]</code></td><td>前半段画 from，之后画 to</td></tr>
      <tr><td>交替词</td><td><code>[A|B]</code></td><td>按采样步轮流生效，得到混合质感</td></tr>
      <tr><td>合成 / 分段</td><td><code>A:1 AND B:1.2</code> · <code>… BREAK …</code></td><td>独立条件流 / 强制换段编码</td></tr>
      <tr><td>外部模型</td><td><code>&lt;lora:name:0.75&gt;</code> · <code>embedding:xxx</code></td><td>挂载 LoRA / Textual Inversion</td></tr>
      <tr><td>风格混搭</td><td><code>(styleA:1.1) + (styleB:0.6)</code></td><td>主次分明的双风格</td></tr>
      <tr><td>画质前缀</td><td><code>(masterpiece, best quality:1.2)</code></td><td>整组打包加权，可复用</td></tr>
      <tr><td>镜头 / 画幅</td><td><code>85mm, f/1.4</code> · <code>9:16</code> · <code>--ar 16:9</code></td><td>配合输出分辨率控制景深构图</td></tr>
      <tr><td>视频专用</td><td><code>slow dolly-in, pan left, handheld, 24fps, 5s, seamless loop</code></td><td>运镜 / 帧率 / 时长 / 循环 / 首尾帧</td></tr>
    </tbody></table>
    <p class="mini">模型差异：SD1.5 吃画质词与负面词；SDXL 对负面词依赖降低；FLUX / SD3 / Sora 偏好完整自然语言长句；视频模型要写「一个镜头、一个连续动作、一种运镜」。LoRA / Embedding 一般不能跨模型系列混用。</p>
  </div>
</details>
"""
