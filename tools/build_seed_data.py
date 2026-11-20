# -*- coding: utf-8 -*-
"""生成初始提示语数据文件。

1) 从 reference/ 里的离线 HTML 卡片库提取 600 条文生图提示语；
2) 生成 160 条文生视频提示语（覆盖运镜、动作、自然、城市、科幻、广告…）。

生成的是普通 JSON 文件，之后完全由用户掌控：可直接编辑、拆分、增删，
在程序里点「重新扫描并读取」即可生效。本脚本只在初次部署时需要运行。
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REF = os.path.join(ROOT, "reference", "SD提示词卡片库.html")
OUT = os.path.join(ROOT, "data", "prompts")
os.makedirs(OUT, exist_ok=True)


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("wrote", os.path.relpath(path, ROOT), len(obj) if isinstance(obj, list) else "")


# ------------------------------------------------------------------ 文生图 600 条
def build_image():
    raw = open(REF, "r", encoding="utf-8").read()
    m = re.search(r'<script id="DATA" type="application/json">(.*?)</script>', raw, re.S)
    if not m:
        raise RuntimeError("未在 reference HTML 中找到内置数据")
    data = json.loads(m.group(1))
    items = []
    for i, x in enumerate(data["items"], 1):
        cat = x["cat"]
        model, syntax = "通用 SD", "sd"
        if "模型适配" in cat or "模型适配" in x.get("tech", ""):
            syntax = "flux" if ("FLUX" in x["prompt"] or "SD3" in x["prompt"]) else "sd"
            model = "多模型适配"
        elif "FLUX" in x["prompt"]:
            syntax, model = "flux", "FLUX.1 / SD3"
        elif "Midjourney" in x["prompt"] or "--" in x["prompt"]:
            syntax, model = "mj", "Midjourney"
        elif "LoRA" in x.get("tech", "") or "<lora:" in x["prompt"]:
            model = "SD 1.5 / ComfyUI"
        elif "3d render" in x["prompt"] or "Octane" in x["prompt"]:
            model = "通用渲染 / 3D"
        items.append({
            "id": f"img-{i:04d}",
            "kind": "image",
            "category": cat,
            "prompt": x["prompt"],
            "negative": "",
            "tip": x["tip"],
            "tech": x.get("tech", "原100条精选"),
            "tags": x.get("tags", []),
            "model": model,
            "syntax": syntax,
            "subject": x.get("subject", ""),
            "like": False,
            "favorite": False,
        })
    dump(os.path.join(OUT, "01_文生图_内置精选.json"),
         {"description": "600 条文生图提示语 · 60 类 · 覆盖权重语法 / 镜头 / 光线 / 风格 / 构图",
          "default_kind": "image", "items": items})


# ------------------------------------------------------------------ 文生视频 160 条
VIDEO_CATS = [
    ("运镜与镜头运动", [
        "slow dolly-in toward a lone cabin in falling snow",
        "smooth 360-degree orbit around a vintage car on a cliff road",
        "crane-up reveal of a lavender field at sunrise",
        "handheld follow shot behind a cyclist on a coastal road",
        "fast push-in on a neon sign reflected in a rain puddle",
        "lateral tracking shot along a Kyoto alley with paper lanterns",
        "tilt-down from cathedral ceiling to a candlelit altar",
        "drone pull-back over a winding river through a red canyon",
        "slow zoom-out from a dewdrop to an entire meadow",
        "whip-pan transition between two sunlit rooms",
    ]),
    ("人物动作与表演", [
        "a young woman turns around slowly as cherry blossoms drift past",
        "an elderly fisherman casts a net into the morning sea",
        "a ballet dancer completes a single pirouette in a haze of stage light",
        "a chef plates a dish with one precise continuous motion",
        "a child blows dandelion seeds into backlit afternoon air",
        "a street musician draws a bow across a violin, coat moving in the wind",
        "a potter shapes clay on a spinning wheel, hands steady",
        "a runner pushes off the starting blocks, dust rising behind",
        "a calligrapher writes one long ink stroke on rice paper",
        "two friends laugh and clink cups at a candlelit cafe table",
    ]),
    ("自然动态与天气", [
        "thunderstorm clouds rolling over an empty prairie",
        "first snow drifting gently through a pine forest",
        "autumn leaves swirling up from a cobblestone path",
        "fog flowing across a valley at dawn",
        "rain droplets racing down a window with city bokeh behind",
        "heat lightning pulsing over desert dunes at night",
        "a rainbow forming after a monsoon shower over rice terraces",
        "waves folding onto black sand under an overcast sky",
        "sunbeams rotating slowly through a misty forest",
        "frost crystals spreading across a leaf in macro",
    ]),
    ("城市与街景", [
        "a tram glides through a rain-soaked European street at blue hour",
        "crowds crossing a Tokyo intersection under flickering signage",
        "an empty subway platform with a train arriving in the distance",
        "elevated highway traffic turning into light trails at dusk",
        "a quiet Venice canal with gondola wake rippling toward camera",
        "neon reflections trembling on wet asphalt after midnight rain",
        "a rooftop skyline waking up as apartment lights switch on",
        "market stalls opening as morning light hits the awnings",
        "a vintage bus passing a row of art deco facades",
        "snow falling on a small town square with a single warm lamp",
    ]),
    ("动物与野生", [
        "a lion shaking dew from its mane in tall savanna grass",
        "an eagle banking slowly above a mountain ridge",
        "a humpback whale turning beneath a shaft of surface light",
        "a kitten stretching on a sunlit windowsill",
        "a wolf stepping through fresh snow, breath visible",
        "a flock of starlings rippling across a sunset sky",
        "a sea turtle gliding over seagrass with caustics on its shell",
        "a peacock turning as its feathers catch the light",
        "dolphins breaking the surface in a single arc",
        "a butterfly opening its wings on a dew-covered fern",
    ]),
    ("水下与海洋", [
        "a manta ray drifting over a coral shelf, light caustics moving",
        "a school of sardines folding into a bait ball",
        "jellyfish pulsing upward through deep blue water",
        "a diver exhaling bubbles that rise toward the surface",
        "sunken shipwreck slowly revealed by drifting silt",
        "bioluminescent plankton washing around a dark reef",
        "an octopus changing texture as it crosses a rock",
        "underwater view looking up at a boat hull and rippled sky",
        "a sea anemone swaying in a gentle current",
        "slow descent past a hydrothermal vent with rising particles",
    ]),
    ("科幻与太空", [
        "a spaceship rising silently from an alien landing pad",
        "an astronaut drifting past a station window with earthrise behind",
        "a ringed planet rotating slowly in a star field",
        "a rover crossing martian dunes as dust trails behind",
        "a hologram booting up in a dim futuristic control room",
        "a maglev train sliding through a transparent tunnel",
        "a nebula slowly shifting from violet to teal in deep space",
        "a robot head turning as its optic lens focuses",
        "a solar eclipse shadow sweeping across a lunar plain",
        "floating drones assembling a lattice structure in zero gravity",
    ]),
    ("奇幻与魔法", [
        "a phoenix unfolding its wings above drifting embers",
        "magic particles spiraling up from a wizard's outstretched hand",
        "a floating island turning slowly with waterfalls spilling into cloud",
        "a dragon opening one eye inside a gold-lit cave",
        "glowing runes igniting one by one on a stone circle",
        "a mermaid's tail breaking a moonlit tidepool surface",
        "fairy lights blinking awake across a miniature gnome village",
        "a portal of soft white light widening in a dark forest",
        "a unicorn stepping through low ground mist",
        "paper lanterns lifting off into a violet night sky",
    ]),
    ("产品广告与静物", [
        "a perfume bottle rotating on marble with a soft travelling reflection",
        "a mechanical watch movement ticking under macro light",
        "silk fabric falling in slow motion over a chair",
        "a coffee cup with steam curling upward in a single ribbon",
        "a sneaker rotating on a seamless white cyclorama",
        "a diamond ring catching a moving caustic highlight",
        "a smartphone tilting as a gradient sweeps across its screen",
        "a glass bottle filling with amber liquid in one continuous pour",
        "a stack of books slowly settling as dust motes float",
        "a lipstick bullet twisting up with a soft specular roll",
    ]),
    ("美食与饮品", [
        "steam rising from a ramen bowl as noodles are lifted",
        "a single drop of honey falling onto toast in slow motion",
        "latte art forming as milk pours into espresso",
        "chocolate shaving curls falling onto a cake",
        "sizzling steak with rosemary smoke drifting sideways",
        "bubble tea pearls swirling as the cup is tilted",
        "a croissant breaking open to reveal layered crumb",
        "ice cream melting one slow drip at a time",
        "sushi being placed on slate with chopsticks",
        "sparkling water bubbles climbing a tall glass",
    ]),
    ("延时与时间流逝", [
        "a sunflower turning across a full day of light",
        "clouds racing over a mountain peak from dawn to dusk",
        "a city skyline transitioning from blue hour to full night",
        "cherry blossoms opening then falling across one branch",
        "tide advancing across a flat beach and retreating",
        "a candle burning down while shadows crawl across a wall",
        "construction of a timber frame in smooth time lapse",
        "stars wheeling above a lone pine tree",
        "snow melting from a stone step in morning sun",
        "a flower wilting and returning in a seamless loop",
    ]),
    ("转场与首尾帧", [
        "match cut: a spinning record dissolving into a vinyl sunrise",
        "start frame a closed door, end frame the same door opening to ocean",
        "whip-pan from a candle flame into a sunrise horizon",
        "a falling leaf crossing the lens and revealing an autumn street",
        "first frame empty stage, last frame the same stage with a dancer",
        "ink drop blooming in water and reforming as a logo",
        "a hand covering the lens, then uncovering a different season",
        "seamless loop: waves folding and unfolding on the same shoreline",
        "morph from a clay sphere into a polished chrome sphere",
        "camera passing through a window frame into a snowy interior",
    ]),
    ("风格化与动画", [
        "anime-style girl walking under falling petals, cel shading, gentle breeze",
        "stop-motion clay character waving with visible fingerprints",
        "pixel-art campfire flickering beside a 16-bit forest",
        "watercolor landscape where ink washes slowly spread",
        "low-poly island rotating with soft ambient occlusion",
        "papercut forest layers shifting as the camera drifts sideways",
        "3d render of a chrome balloon drifting past pastel geometry",
        "line-art city coming alive as ink strokes draw themselves",
        "storybook cottage with chimney smoke curling in loops",
        "vaporwave grid scrolling under a pink and cyan sun",
    ]),
    ("运动与竞技", [
        "a surfer dropping into a glassy barrel with spray trailing",
        "a skateboarder landing a kickflip in one unbroken shot",
        "a boxer throwing a single jab under ring lights",
        "a skier carving a clean arc through deep powder",
        "an archer releasing an arrow in slow motion",
        "a cyclist peloton sweeping around a hairpin bend",
        "a gymnast's ribbon drawing one continuous spiral",
        "a soccer ball spinning toward goal through drifting dust",
        "a rock climber reaching for a hold, chalk puffing",
        "a rowing shell cutting a still lake at dawn",
    ]),
    ("微距与科学", [
        "a droplet impacting a water surface and forming a crown",
        "pollen grains drifting off a stamen in macro",
        "a snowflake crystal growing branch by branch",
        "ink swirling into clear water in slow tendrils",
        "cells dividing under a microscope with soft glow",
        "a butterfly wing scale catching a shifting iridescent highlight",
        "smoke plume folding into vortices on a black background",
        "molten glass being turned on a rod, glowing orange",
        "magnetic field lines drawing themselves around a magnet",
        "a spider web vibrating as a single dewdrop slides down",
    ]),
    ("氛围与电影感", [
        "a lone figure standing in volumetric fog under one streetlamp",
        "dust motes floating in a single projector beam in an attic",
        "rain on a motel window with neon bleeding through the glass",
        "a long hallway with fluorescent lights flickering in sequence",
        "candlelight trembling across a cracked portrait in a dark room",
        "blue hour over wet rooftops with distant traffic glow",
        "silhouette of a person against a slowly brightening horizon",
        "a quiet library with one lamp switching on at closing time",
        "golden hour light sliding slowly across a plaster wall",
        "anamorphic lens flare sweeping across a night highway",
    ]),
]

MOVES = [
    "slow dolly-in", "smooth tracking shot", "gentle pan left", "crane-up reveal",
    "handheld follow", "static locked-off camera", "slow 360 orbit", "push-in with slight parallax",
    "pull-back wide reveal", "subtle handheld drift",
]
LIGHTS = [
    "soft golden hour backlight", "overcast diffuse light", "volumetric god rays",
    "moody blue hour with practical lights", "warm interior lamp glow", "high-key clean studio light",
    "teal and orange cinematic grade", "cold moonlight with rim light", "dusty projector beam",
    "soft pastel dawn light",
]
STYLES = [
    "cinematic, photorealistic, 24fps", "single continuous shot, natural motion",
    "film still, shallow depth of field, anamorphic", "documentary handheld realism",
    "dreamlike, gentle motion, smooth grading", "clean commercial look, stable framing",
    "atmospheric, low contrast, fine grain", "hyperdetailed, physically plausible motion",
    "storybook soft focus, subtle animation", "minimal composition, no camera shake",
]
MODELS = ["Kling 可灵", "Runway Gen-3·4", "Sora 2", "Wan2.x / HunyuanVideo",
          "AnimateDiff / Pika", "Luma / Vidu / 海螺", "CogVideoX", "通用视频模型"]
TECHS = ["单镜头单动作", "运镜词独立书写", "时间连续性", "光线连贯", "首尾帧约束",
         "无缝循环 loop", "负向视频词", "运动强度控制", "帧率与时长", "长句自然描述",
         "主体一致性", "物理合理性", "动态模糊控制", "分镜拆分", "中文长句适配",
         "避免多动作堆叠"]
TIPS = [
    "视频提示词一次只写「一个镜头 + 一个连续动作」，多个动作同时发生最容易崩坏。",
    "运镜词（dolly / pan / orbit / handheld）单独成段写，比混在主体描述里稳定得多。",
    "强调时间连续与物理合理：写清动作从哪到哪、光怎么变，别只堆静态画质词。",
    "保持光线方向与色温在整段里一致，否则会出现逐帧闪烁。",
    "首尾帧类需求在提示词里明确 start frame / end frame，方便与图生视频配合。",
    "无缝循环要写 seamless loop 并让首尾姿态接近，配合固定 seed 反复调。",
    "视频负向词重点压 flicker / jitter / warped background / inconsistent character。",
    "运动幅度别写太满：gentle / subtle / slow 比 dramatic / explosive 更不容易形变。",
    "时长和 fps 写进提示词（5s / 24fps），配合平台的实际输出参数一起调。",
    "Sora / FLUX 系视频模型吃完整长句，别套 SD 的 (word:1.2) 权重语法。",
    "多镜头请拆成多条提示语分别生成，再在剪辑里拼接，别让模型一次拍完。",
    "主体服装、发型、道具在一条里只描述一次，减少跨帧漂移。",
    "涉及液体、烟雾、布料时补一句 physically plausible，能减少撕裂与穿透。",
    "Wan / HunyuanVideo 中文长句表现好，可直接写「镜头缓慢推进，…」这类描述。",
    "避免 sudden zoom / camera shake，除非确实要手持感；多数平台会把它放大成抖动。",
    "需要风格化时把风格词放最后，前面先锁主体动作与镜头，优先级更清楚。",
]


def build_video():
    items = []
    n = 0
    for ci, (cat, scenes) in enumerate(VIDEO_CATS):
        for i in range(10):
            n += 1
            scene = scenes[i]
            move = MOVES[(ci + i * 3) % len(MOVES)]
            light = LIGHTS[(ci * 2 + i) % len(LIGHTS)]
            style = STYLES[(ci + i * 2) % len(STYLES)]
            model = MODELS[(ci + i) % len(MODELS)]
            tech = TECHS[(ci + i * 5) % len(TECHS)]
            tip = TIPS[(ci + i) % len(TIPS)]
            duration = f"{(ci % 4) + 4}s"
            fps = ["24fps", "24fps", "30fps", "16fps"][(ci + i) % 4]
            motion = ["gentle", "subtle", "moderate", "slow and steady"][(ci + i) % 4]
            prompt = (f"{scene}, {move}, {light}, {style}, {duration}, {fps}, "
                      f"{motion} motion, no sudden camera movement")
            items.append({
                "id": f"vid-{n:04d}", "kind": "video", "category": cat,
                "prompt": prompt,
                "negative": ("flicker, temporal inconsistency, jitter, warped background, "
                             "inconsistent character, deformed hands, frame tearing, "
                             "sudden zoom, camera shake, watermark, text, subtitle"),
                "tip": tip, "tech": tech,
                "tags": ["文生视频", tech, model, "运镜"],
                "model": model, "syntax": "wan" if model.startswith("Wan") else "flux",
                "subject": scene.split(",")[0][:56],
                "camera": move, "duration": duration, "motion": motion, "fps": fps,
                "like": False, "favorite": False,
            })
    dump(os.path.join(OUT, "02_文生视频_内置精选.json"),
         {"description": "160 条文生视频提示语 · 16 类 · 运镜 / 动作 / 首尾帧 / 循环 / 负向词",
          "default_kind": "video", "items": items})


def build_readme():
    txt = """data/prompts/ 提示语数据文件说明
========================================

本目录下的每一个文件都是一个独立的提示语库。程序启动时会递归扫描本目录
（以及 data/ 下其它非 config/ 目录），支持以下格式：

  .json    顶层为数组，或 {"items": [...], "default_kind": "image|video", ...}
  .jsonl   每行一个 JSON 对象；以 # 开头的行是注释，会被保留
  .csv     至少包含 prompt 列，其余列名与条目字段同名（tags 可用逗号分隔）
  .txt     每行一条纯提示语；支持 "提示语 ||| 类别 ||| 技巧说明"；# 开头为注释
  .db      SQLite：表 prompts(id TEXT, payload TEXT)，payload 为条目 JSON

一条提示语可用的字段（除 prompt 外全部可省略，缺失会自动补默认值）：

  id          稳定标识；不写则按内容自动生成（建议自定义条目手动写上）
  kind        image | video
  category    类别名（全局唯一，可在「类别管理」里维护）
  prompt      提示语正文（必填）
  negative    该条专属负面 / 负向提示词
  tip         学习注解 / 技巧说明
  tech        技巧标签
  tags        标签数组，或逗号分隔字符串
  model       适用模型 / 框架
  syntax      权重语法画像：sd | flux | mj | comfy | wan | custom；留空跟随全局设置
  subject     主体短语（用于「主体前置权重」滑块）
  camera / duration / motion / fps   文生视频专用字段
  like        喜欢（true / 1 / 是）
  favorite    收藏（true / 1 / 是）

任何你自己新增的字段都会被原样保留，写回文件时不会丢失。

典型工作流：
  1. 用文本编辑器直接改这里的文件，或新增一个文件（例如 03_我的私藏.jsonl）；
  2. 回到程序「数据文件」选项卡，点「🔄 重新扫描并读取」；
  3. 新内容立即出现在文生图 / 文生视频 / 收藏页里。

大数据量建议：按类别或项目拆成多个文件，扫描时并行无关、只读一次；
界面默认每页显示 24 条，可在每个列表页调整每页条数与翻页。
"""
    # 用 .md 后缀，避免被扫描器当成纯提示语数据文件
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    build_image()
    build_video()
    build_readme()
    print("done.")
