# -*- coding: utf-8 -*-
"""PromptDock · 文生图 / 文生视频提示语本地管理平台

启动：  python app.py  [--port 7860] [--data-dir ./data] [--no-browser]
依赖：  pip install gradio>=4.44

设计：左侧多选项卡（文生图 / 文生视频 / 喜欢与收藏 / 负面词 / 类别 / 数据文件 /
设置 / 速查），右侧常驻「选中详情 · 编辑 · 翻译 · 拼装台」侧栏。
所有数据就是 data/prompts/ 下的普通文件，用户可直接编辑、增删文件，点重新扫描即生效。
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import math
import os
import subprocess
import sys
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

# Gradio 6.0 起把 theme / css / head 从 Blocks 构造移到 launch()，
# 并把 show_copy_button 换成 buttons=["copy"]、show_api 换成 footer_links。
# 本项目同时兼容 4.44 ~ 6.x：下面按主版本号自动选择对应写法。
GRADIO_MAJOR = int(str(gr.__version__).split(".")[0].split("+")[0])

# 静默 5.x 关于 show_api 的弃用提示，避免控制台噪音（6.x 不再使用该参数）。
for _p in ("show_api", "theme", "css", "head"):
    warnings.filterwarnings("ignore", message=f"The '{_p}' parameter.*")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core.cards import (BRIDGE_JS, confirm_text, render_cards, render_categories,
                        render_sources, render_stats, render_tray)
from core.models import KIND_LABEL, normalize
from core.storage import DEFAULT_SETTINGS, FMT_OF, Library, safe_name
from core.syntax import (CHEATSHEET_HTML, PROFILES, guides_html, load_guides,
                         get_profile, tokenize, fmt as wfmt)
from core.translate import LANG_CHOICES, translate

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

EXTRA_JS = r"""
<script>
(function(){
  var COPY_MAP = {
    'btn_copy_neg0':'neg0', 'btn_copy_neg1':'neg1', 'btn_copy_neg2':'neg2',
    'btn_copy_tray':'tray_preview', 'btn_copy_trans':'trans_out',
    'btn_copy_editor':'ed_prompt', 'btn_copy_path':'file_path_box'
  };
  document.addEventListener('click', function(ev){
    var node = ev.target, id = '';
    for(var i=0; i<5 && node; i++, node = node.parentElement){
      if(node.id && COPY_MAP[node.id]){ id = node.id; break; }
    }
    if(!id) return;
    var box = document.getElementById(COPY_MAP[id]);
    if(!box) return;
    var el = box.querySelector('textarea,input') || box;
    var txt = (el.value !== undefined && el.value !== null) ? el.value : (el.textContent || '');
    if(window.__sdCopy) window.__sdCopy(txt);
  });
  document.addEventListener('keydown', function(ev){
    if(ev.key === 'Escape' && window.__sdSend) window.__sdSend('', 'cancel', '');
  });
})();
</script>
"""


# ==================================================================== 状态
TAB_KEYS = ("image", "video", "fav")


def default_tab(page_size: int) -> Dict[str, Any]:
    return {"page": 1, "size": page_size, "q": "", "cat": "ALL", "tech": "ALL",
            "model": "ALL", "tag": "ALL", "sort": "编号", "flag_mode": "全部"}


def default_state(lib: Library) -> Dict[str, Any]:
    ps = int(lib.settings.get("page_size", 24))
    return {
        "tabs": {k: default_tab(ps) for k in TAB_KEYS},
        "sel": "", "editor": {}, "tray": [], "tray_sep": "逗号 , ",
        "trans": "", "trans_note": "", "feedback": "",
        "pending": None, "cat_sel": "", "cat_rename": "",
        "file_sel": "", "file_raw": "", "weights": {},
    }


def set_feedback(st: Dict[str, Any], msg: str, ok: bool = True):
    icon = "✅" if ok else "⚠️"
    st["feedback"] = f"{icon} {msg}　<span class='mini'>· {time.strftime('%H:%M:%S')}</span>"


def clamp_page(st: Dict[str, Any], tab: str, total: int):
    cfg = st["tabs"][tab]
    pages = max(1, math.ceil(total / max(1, cfg["size"])))
    cfg["page"] = max(1, min(int(cfg["page"] or 1), pages))
    return pages


def query(lib: Library, tab: str, st: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, int]:
    cfg = st["tabs"][tab]
    items = lib.all_items()
    if tab == "image":
        items = [x for x in items if x["kind"] == "image"]
    elif tab == "video":
        items = [x for x in items if x["kind"] == "video"]
    else:
        mode = cfg.get("flag_mode", "全部")
        if mode == "仅喜欢 ♥":
            items = [x for x in items if x.get("like")]
        elif mode == "仅收藏 ★":
            items = [x for x in items if x.get("favorite")]
        else:
            items = [x for x in items if x.get("like") or x.get("favorite")]

    q = str(cfg.get("q", "")).strip().lower()
    if q:
        def hay(it):
            return " ".join([it.get("prompt", ""), it.get("tip", ""), it.get("category", ""),
                             it.get("tech", ""), it.get("model", ""), it.get("negative", ""),
                             " ".join(it.get("tags", []))]).lower()
        items = [x for x in items if q in hay(x)]
    for field, key in (("category", "cat"), ("tech", "tech"), ("model", "model")):
        v = cfg.get(key, "ALL")
        if v not in ("", "ALL"):
            items = [x for x in items if str(x.get(field, "")) == str(v)]
    tag = cfg.get("tag", "ALL")
    if tag not in ("", "ALL"):
        items = [x for x in items if tag in (x.get("tags") or [])]
    sort = cfg.get("sort", "编号")
    if sort == "类别":
        items.sort(key=lambda x: (x.get("category", ""), x.get("id", "")))
    elif sort == "提示语长度":
        items.sort(key=lambda x: -len(x.get("prompt", "")))
    elif sort == "随机":
        import random
        random.Random(42).shuffle(items)
    else:
        items.sort(key=lambda x: str(x.get("id", "")))
    total = len(items)
    pages = clamp_page(st, tab, total)
    page, size = cfg["page"], max(1, int(cfg["size"]))
    return items[(page - 1) * size: page * size], total, pages


SEP_MAP = {"逗号 , ": ", ", "AND 合成": " AND ", "BREAK 分段": " BREAK ", "换行": "\n"}


def tray_text(st: Dict[str, Any]) -> str:
    sep = SEP_MAP.get(st.get("tray_sep", "逗号 , "), ", ")
    return sep.join(str(t.get("text", "")) for t in st.get("tray", []))


def make_export(lib: Library, title: str, items: List[Dict[str, Any]]) -> str:
    d = os.path.join(lib.root, "exports")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"PromptDock_提示语_{title}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"PromptDock 导出 · {title} · {len(items)} 条\n")
        f.write("=" * 60 + "\n\n")
        for it in items:
            f.write(f"#{it['id']}  [{KIND_LABEL.get(it['kind'], it['kind'])} / {it['category']} / {it.get('tech','')}]\n")
            f.write(it.get("prompt", "") + "\n")
            if it.get("negative"):
                f.write("负面词: " + it["negative"] + "\n")
            if it.get("tip"):
                f.write("技巧: " + it["tip"] + "\n")
            f.write("\n")
        f.write("\n--- 通用负面提示词 ---\n")
        for k, v in lib.settings.get("negative_presets", {}).items():
            f.write(f"\n[{k}]\n{v}\n")
    return path


# ==================================================================== 主界面
def make_app(lib: Optional[Library] = None) -> gr.Blocks:
    lib = lib or Library()
    V: Dict[str, Any] = {}
    ORDER: List[str] = []

    def reg(name: str, comp):
        V[name] = comp
        ORDER.append(name)
        return comp

    css_path = os.path.join(HERE, "assets", "theme.css")
    css = open(css_path, "r", encoding="utf-8").read() if os.path.exists(css_path) else ""
    theme = gr.themes.Base()

    # Gradio 6.0 起 theme / css / head 必须从 Blocks 构造移到 launch()。
    # 这里按主版本组装，构造期只对 4.x/5.x 传这三个参数，6.x 一律不传。
    blocks_kwargs: Dict[str, Any] = {"title": "PromptDock · 文生图 / 文生视频提示语本地管理平台",
                                     "analytics_enabled": False}
    launch_kwargs: Dict[str, Any] = {}
    if GRADIO_MAJOR >= 6:
        launch_kwargs["theme"] = theme
        launch_kwargs["css"] = css
        launch_kwargs["head"] = BRIDGE_JS + EXTRA_JS
    else:
        blocks_kwargs["theme"] = theme
        blocks_kwargs["css"] = css
        blocks_kwargs["head"] = BRIDGE_JS + EXTRA_JS

    with gr.Blocks(**blocks_kwargs) as demo:

        # ---------------------------------------------------------- 顶部
        gr.HTML("""<div class="sd-hero">
  <h1>Prompt<span>Dock</span></h1>
  <div class="sd-sub">文生图 · 文生视频 提示语本地管理平台　|　多文件持久化 · 权重滑块 · 分页检索 · 手动翻译 · 喜欢与收藏</div>
  <div class="sd-tagline">所有内容都保存在本地普通文件里：直接编辑 data/prompts/ 下的 JSON / JSONL / CSV / TXT / DB，点「重新扫描并读取」即可生效。</div>
</div>""")
        reg("stats", gr.HTML())
        reg("feedback", gr.HTML('<div class="sd-feedback">就绪。</div>'))

        with gr.Row():
            gm = gr.Slider(0.5, 1.8, value=float(lib.settings.get("global_weight", 1.0)),
                           step=0.05, label="⚖️ 全局权重倍率（实时作用于所有 (word:数值) 提示词）",
                           scale=3, elem_id="global_mul")
            gr.HTML('<div style="font-size:11px;color:var(--dim2);padding-top:26px">'
                    '拖动后所有卡片的权重滑块与复制文本会同步改写；在「设置」里可持久化该值。</div>')

        with gr.Group(visible=False, elem_classes=["sd-confirm"]) as confirm_group:
            reg("confirm_group", confirm_group)
            reg("confirm_md", gr.Markdown("确认操作"))
            with gr.Row():
                btn_yes = gr.Button("✅ 确认执行", variant="primary", elem_id="btn_yes")
                btn_no = gr.Button("↩️ 取消", elem_id="btn_no")

        # ---------------------------------------------------------- 主区
        with gr.Row(equal_height=False):
            # ============================ 左侧 Tabs
            with gr.Column(scale=4):
                with gr.Tabs() as tabs:
                    list_ui: Dict[str, Dict[str, Any]] = {}

                    def build_list_tab(tab: str, label: str, icon: str):
                        with gr.TabItem(f"{icon} {label}"):
                            with gr.Row():
                                q_box = gr.Textbox(label="🔍 搜索（主体 / 技巧 / 类别 / 标签 / 负面词）",
                                                   placeholder="输入关键词…", scale=3,
                                                   elem_id=f"q_{tab}")
                                size_dd = gr.Dropdown(choices=["8", "12", "24", "48", "96"],
                                                      value=str(default_state(lib)["tabs"][tab]["size"]),
                                                      label="每页条数", scale=1, elem_id=f"size_{tab}")
                                sort_dd = gr.Dropdown(choices=["编号", "类别", "提示语长度", "随机"],
                                                      value="编号", label="排序", scale=1)
                            reg(f"q_{tab}", q_box)
                            reg(f"size_{tab}", size_dd)
                            reg(f"sort_{tab}", sort_dd)
                            with gr.Row():
                                cat_dd = gr.Dropdown(choices=["ALL"], value="ALL", label="类别", scale=2)
                                tech_dd = gr.Dropdown(choices=["ALL"], value="ALL", label="技巧", scale=2)
                                model_dd = gr.Dropdown(choices=["ALL"], value="ALL", label="模型 / 框架", scale=2)
                                tag_dd = gr.Dropdown(choices=["ALL"], value="ALL", label="语法特性 / 标签", scale=2)
                            if tab == "fav":
                                with gr.Row():
                                    flag_dd = gr.Dropdown(choices=["全部", "仅喜欢 ♥", "仅收藏 ★"],
                                                          value="全部", label="标记筛选", scale=2)
                                    reg(f"flag_{tab}", flag_dd)
                                    btn_fav_refresh = gr.Button("🔄 手动刷新", scale=1)
                                    gr.HTML('<div class="sd-hint" style="padding-top:22px">'
                                            '点卡片上的 ♥ / ★ 即可取消喜欢或收藏；编辑与分页与其它页面一致。</div>')
                            else:
                                flag_dd = None
                                btn_fav_refresh = None
                            with gr.Row():
                                b_first = gr.Button("⏮ 首页", scale=1)
                                b_prev = gr.Button("← 上一页", scale=1)
                                page_num = gr.Number(value=1, label="跳转页码", precision=0,
                                                     minimum=1, scale=1, elem_id=f"pnum_{tab}")
                                b_next = gr.Button("下一页 →", scale=1)
                                b_last = gr.Button("末页 ⏭", scale=1)
                            reg(f"cards_{tab}", gr.HTML())
                            reg(f"page_{tab}", gr.HTML('<div class="sd-page"></div>'))
                            with gr.Row():
                                b_refresh = gr.Button("📥 重新读取本地数据", scale=1)
                                b_reset = gr.Button("↩️ 重置筛选", scale=1)
                                b_copy_page = gr.Button("📄 导出当前页 .txt", scale=1)
                                b_copy_all = gr.Button("📦 导出全部筛选结果 .txt", scale=1)
                                b_page_tray = gr.Button("📋 当前页→拼装台", scale=1)
                                b_clear = gr.Button("✨ 清空该页筛选", scale=1)
                            list_ui[tab] = dict(
                                q=q_box, size=size_dd, sort=sort_dd, cat=cat_dd, tech=tech_dd,
                                model=model_dd, tag=tag_dd, flag=flag_dd,
                                fav_refresh=btn_fav_refresh, first=b_first, prev=b_prev,
                                next=b_next, last=b_last, pnum=page_num,
                                refresh=b_refresh, reset=b_reset, export_page=b_copy_page,
                                export_all=b_copy_all, page_tray=b_page_tray, clear=b_clear)
                            for nm, comp in (("cat", cat_dd), ("tech", tech_dd),
                                             ("model", model_dd), ("tag", tag_dd)):
                                reg(f"{nm}_{tab}", comp)

                    build_list_tab("image", "文生图提示语", "🖼️")
                    build_list_tab("video", "文生视频提示语", "🎬")
                    build_list_tab("fav", "个人喜欢与收藏", "♥★")

                    # ------------------------------ 负面提示词
                    with gr.TabItem("🚫 负面提示词"):
                        gr.HTML('<div class="sd-hint">三套可编辑负面词保存在 data/config/settings.json。'
                                'SD1.5 建议用完整版；SDXL / FLUX 可只保留 worst quality / blurry / watermark / text；'
                                '视频模型用第四套思路（见下方文生视频负向词）。</div>')
                        presets = lib.settings.get("negative_presets", {})
                        neg_keys = (list(presets.keys()) + ["负面词 A", "负面词 B", "负面词 C"])[:3]
                        neg_boxes, neg_to_editor_btns = [], []
                        for i, k in enumerate(neg_keys):
                            with gr.Group():
                                gr.Markdown(f"**{k}**")
                                tb = reg(f"neg{i}", gr.Textbox(value=presets.get(k, ""),
                                         lines=6, label="", elem_id=f"neg{i}",
                                         **({"buttons": ["copy"]} if GRADIO_MAJOR >= 6
                                            else {"show_copy_button": True})))
                                neg_boxes.append(tb)
                                with gr.Row():
                                    gr.Button("📋 复制这套", elem_id=f"btn_copy_neg{i}")
                                    b = gr.Button("↘ 填入当前编辑条目", elem_id=f"btn_neg_to_editor_{i}")
                                    neg_to_editor_btns.append(b)
                        with gr.Row():
                            btn_neg_save = gr.Button("💾 保存三套负面词到 settings.json", variant="primary")
                            btn_neg_reset = gr.Button("↩️ 恢复默认负面词")
                        gr.HTML(CHEATSHEET_HTML)

                    # ------------------------------ 类别管理
                    with gr.TabItem("🗂️ 类别管理"):
                        gr.HTML('<div class="sd-hint">类别名全局唯一；新增或改名时若已存在会明确提示并拒绝。'
                                '删除类别会连带删除该类别下所有提示语，需要二次确认。</div>')
                        with gr.Row():
                            cat_new_name = gr.Textbox(label="新增类别名", scale=2)
                            cat_new_kind = gr.Dropdown(choices=["both", "image", "video"], value="both",
                                                       label="适用", scale=1)
                            cat_new_note = gr.Textbox(label="备注（可选）", scale=2)
                            btn_cat_add = gr.Button("＋ 新增类别", variant="primary", scale=1)
                        with gr.Row():
                            reg("cat_pick_box", gr.Textbox(label="当前选中的类别", interactive=False, scale=2))
                            reg("cat_rename_new", gr.Textbox(label="修改为（新类别名）", scale=2))
                            btn_cat_rename = gr.Button("✏️ 重命名类别", scale=1)
                            btn_cat_delete = gr.Button("🗑 删除选中类别", scale=1)
                        reg("cat_html", gr.HTML())

                    # ------------------------------ 数据文件
                    with gr.TabItem("📁 数据文件"):
                        gr.HTML('<div class="sd-hint">支持 .json / .jsonl / .csv / .txt / .db(sqlite)。'
                                '在外部编辑器改完文件后点「重新读取」；新建文件后点「重新扫描」即可被发现。</div>')
                        with gr.Row():
                            btn_scan = gr.Button("🔄 重新扫描文件列表", scale=1)
                            btn_reload = gr.Button("📥 重新扫描并读取全部数据", variant="primary", scale=1)
                            btn_opendir = gr.Button("📂 在文件管理器中打开目录", scale=1)
                        reg("files_html", gr.HTML())
                        with gr.Group():
                            gr.Markdown("**编辑数据文件原始内容**（保存后自动重新读取；请保持格式合法）")
                            with gr.Row():
                                reg("file_rel_box", gr.Textbox(label="当前文件（相对 data/）",
                                                              interactive=False, scale=2))
                                reg("file_path_box", gr.Textbox(label="绝对路径", interactive=False, scale=3))
                                gr.Button("📋 复制路径", elem_id="btn_copy_path", scale=1)
                            reg("file_raw_box", gr.Textbox(label="文件原始内容", lines=12,
                                                          elem_id="file_raw_box"))
                            with gr.Row():
                                btn_raw_save = gr.Button("💾 保存并重新读取", variant="primary")
                                btn_file_delete = gr.Button("🗑 删除当前数据文件")
                        with gr.Group():
                            gr.Markdown("**新建数据文件**（新建后可直接在界面或外部编辑器里填内容）")
                            with gr.Row():
                                f_name = gr.Textbox(label="文件名", value="03_我的提示语.json", scale=2)
                                f_fmt = gr.Dropdown(choices=["json", "jsonl", "csv", "txt", "db"],
                                                    value="json", label="格式", scale=1)
                                f_kind = gr.Dropdown(choices=["image", "video"], value="image",
                                                     label="缺省类型", scale=1)
                                f_desc = gr.Textbox(label="文件说明", scale=2)
                                btn_file_new = gr.Button("＋ 新建文件", variant="primary", scale=1)

                    # ------------------------------ 设置 / 模型指南
                    with gr.TabItem("⚙️ 设置与模型指南"):
                        with gr.Row():
                            set_page = gr.Dropdown(choices=["8", "12", "24", "48", "96"],
                                                   value=str(int(lib.settings.get("page_size", 24))),
                                                   label="默认每页条数（程序启动时生效）")
                            set_profile = gr.Dropdown(
                                choices=[p.key for p in PROFILES.values()],
                                value=str(lib.settings.get("syntax_profile", "sd")),
                                label="默认权重语法画像")
                            set_tpl = gr.Textbox(value=str(lib.settings.get("custom_tpl", "({w}:{v})")),
                                                 label="自定义权重模板（含 {w} 与 {v}）")
                        with gr.Row():
                            set_target = gr.Textbox(
                                value=str(lib.settings.get("default_target_file", "99_自定义提示语.json")),
                                label="新增提示语默认写入的文件")
                            set_provider = gr.Dropdown(
                                choices=["gtx", "mymemory", "libre", "off"],
                                value=str(lib.settings.get("translate", {}).get("provider", "gtx")),
                                label="翻译服务（免费、仅手动触发）")
                            set_tgt_lang = gr.Dropdown(choices=list(LANG_CHOICES.keys()), value="中文",
                                                       label="翻译目标语言")
                            set_timeout = gr.Slider(3, 20, value=int(lib.settings.get("translate", {}).get("timeout", 8)),
                                                    step=1, label="超时（秒）")
                        with gr.Row():
                            set_endpoint = gr.Textbox(
                                value=str(lib.settings.get("translate", {}).get("custom_endpoint", "")),
                                label="自建 / 公共 LibreTranslate 端点（选 libre 时必填）")
                            set_enabled = gr.Checkbox(value=bool(lib.settings.get("translate", {}).get("enabled", True)),
                                                      label="启用翻译按钮")
                            btn_set_save = gr.Button("💾 保存设置", variant="primary")
                            btn_set_reset = gr.Button("↩️ 重新载入设置文件")
                        gr.Markdown("### 📚 主流模型 / 推理框架撰写规范")
                        gr.HTML(guides_html())
                        with gr.Row():
                            guide_dd = gr.Dropdown(
                                choices=[g["name"] for g in load_guides()],
                                value=load_guides()[0]["name"], label="选一个模型，把示例套用到编辑面板", scale=3)
                            btn_guide_apply = gr.Button("↘ 套用示例到编辑面板", scale=1)

                    # ------------------------------ 速查 / 关于
                    with gr.TabItem("📖 语法小抄与关于"):
                        gr.HTML(CHEATSHEET_HTML)
                        gr.HTML("""<div class="sd-details"><summary>关于本程序</summary>
<div class="sd-details-body">
<p><b>数据在哪：</b><code>data/prompts/</code> 下的多个普通文件；设置、类别、模型指南在 <code>data/config/</code>。
直接编辑这些文件 → 回到「数据文件」页点「重新扫描并读取」即可生效。删除条目 / 类别 / 文件都需要二次确认。</p>
<p><b>权重滑块：</b>卡片里每个 <code>(word:1.2)</code> / <code>word::1.2</code> / <code>&lt;lora:x:0.8&gt;</code>
都有独立滑块，拖动即时改写提示词；「复制」「＋拼装台」「💾 保存权重版本」用的都是改写后的文本。
全局倍率在页面顶部，换模型可在「设置」里切换权重语法画像，条目也可以单独指定 syntax 字段。</p>
<p><b>翻译：</b>默认 Google 免费公开接口，失败自动回退 MyMemory，也支持自建 LibreTranslate；
只在点「🌐 翻译」时发起请求，绝不后台自动上传。按 Esc 可取消任何待确认操作。</p>
<p><b>离线参考：</b><code>reference/SD提示词卡片库.html</code> 是上一版单文件离线卡片库，功能与视觉风格与本程序一致。</p>
</div></div>""")

            # ============================ 右侧常驻侧栏
            with gr.Column(scale=1, min_width=330, elem_classes=["sd-side"]):
                reg("sel_html", gr.HTML())
                with gr.Accordion("✏️ 编辑 / 新增提示语", open=True):
                    reg("ed_id", gr.Textbox(label="条目 ID（空 = 新增）", interactive=False,
                                            elem_id="ed_id"))
                    with gr.Row():
                        reg("ed_kind", gr.Dropdown(choices=["image", "video"], value="image",
                                                   label="类型", scale=1))
                        reg("ed_cat", gr.Dropdown(choices=["ALL"], value="ALL", label="类别", scale=2))
                    reg("ed_newcat", gr.Textbox(label="或新建类别（填了就优先使用，重名会被拒绝）"))
                    reg("ed_prompt", gr.Textbox(label="提示语正文 *", lines=6, elem_id="ed_prompt"))
                    reg("ed_neg", gr.Textbox(label="专属负面 / 负向提示词", lines=2))
                    reg("ed_tip", gr.Textbox(label="技巧说明 / 学习注解", lines=2))
                    with gr.Row():
                        reg("ed_tags", gr.Textbox(label="标签（逗号分隔）", scale=1))
                        reg("ed_model", gr.Textbox(label="适用模型", scale=1))
                    with gr.Row():
                        reg("ed_syntax", gr.Dropdown(
                            choices=["（跟随全局）"] + [p.key for p in PROFILES.values()],
                            value="（跟随全局）", label="权重语法", scale=1))
                        reg("ed_subject", gr.Textbox(label="主体短语", scale=1))
                    with gr.Accordion("🎬 文生视频专用字段", open=False):
                        reg("ed_camera", gr.Textbox(label="运镜 / 镜头运动"))
                        with gr.Row():
                            reg("ed_duration", gr.Textbox(label="时长", scale=1))
                            reg("ed_fps", gr.Textbox(label="帧率", scale=1))
                        reg("ed_motion", gr.Textbox(label="运动强度"))
                    reg("ed_target", gr.Dropdown(choices=["自动（默认文件）"], value="自动（默认文件）",
                                                 label="写入的数据文件"))
                    with gr.Row():
                        btn_ed_new = gr.Button("✨ 新建")
                        btn_ed_save = gr.Button("💾 保存", variant="primary")
                        btn_ed_del = gr.Button("🗑 删除")
                    with gr.Row():
                        gr.Button("📋 复制正文", elem_id="btn_copy_editor")
                        btn_ed_copy_weight = gr.Button("♻️ 重置该条权重滑块")
                    reg("ed_status", gr.Markdown(""))

                with gr.Accordion("🌐 翻译（手动触发）", open=True):
                    with gr.Row():
                        trans_dir = gr.Dropdown(choices=["自动互译", "译成中文", "译成英文"],
                                                value="自动互译", label="方向", scale=2)
                        btn_trans = gr.Button("🌐 翻译", variant="primary", scale=1)
                    reg("trans_out", gr.Textbox(label="译文（可编辑）", lines=5,
                                                elem_id="trans_out"))
                    reg("trans_note", gr.Markdown(""))
                    with gr.Row():
                        gr.Button("📋 复制译文", elem_id="btn_copy_trans")
                        btn_trans_use = gr.Button("↘ 用译文替换正文")

                with gr.Accordion("🧩 拼装台", open=True):
                    reg("tray_count_md", gr.Markdown(""))
                    reg("tray_html", gr.HTML())
                    with gr.Row():
                        tray_sep = gr.Dropdown(choices=list(SEP_MAP.keys()), value="逗号 , ",
                                               label="拼接方式", scale=2)
                        btn_tray_export = gr.Button("📦 导出", scale=1)
                    reg("tray_preview", gr.Textbox(label="拼装结果（可直接复制 / 再编辑）", lines=5,
                                                   elem_id="tray_preview"))
                    with gr.Row():
                        gr.Button("📋 复制拼装结果", elem_id="btn_copy_tray")
                        btn_tray_clear = gr.Button("🗑 清空拼装台")

                reg("export_file", gr.File(label="⬇️ 最近导出的文件", interactive=False))
                gr.HTML('<div class="sd-hint">提示：卡片里的「复制」是纯前端操作；'
                        '拖动权重滑块后再复制 / 加入拼装台，得到的就是改权重后的版本。</div>')

        # ---------------------------------------------------------- 前端桥接（隐藏）
        with gr.Group(elem_id="bridge_wrap"):
            bridge_id = gr.Textbox(label="id", elem_id="bridge_id")
            bridge_action = gr.Textbox(label="action", elem_id="bridge_action")
            bridge_payload = gr.Textbox(label="payload", elem_id="bridge_payload")
            bridge_go = gr.Button("bridge", elem_id="bridge_go", visible=True)

        state_comp = gr.State(default_state(lib))
        OUT = [V[k] for k in ORDER] + [state_comp]

        # ============================================================ 统一视图
        def sync(st: Dict[str, Any], **ov):
            """所有事件共用同一组输出，避免逐个对齐组件。"""
            views: Dict[str, Any] = {}
            views["stats"] = gr.update(value=render_stats(lib, st))
            views["feedback"] = gr.update(
                value='<div class="sd-feedback">' + (st.get("feedback") or "就绪 · 所有改动实时写入本地数据文件。") + "</div>")
            p = st.get("pending")
            views["confirm_group"] = gr.update(visible=bool(p))
            views["confirm_md"] = gr.update(value="### ⚠️ " + confirm_text(st) if p else "")

            for tab in TAB_KEYS:
                cfg = st["tabs"][tab]
                kind = "image" if tab == "image" else ("video" if tab == "video" else "both")
                ch = lib.choices(kind)
                # 类别/技巧若已失效（例如类别被删或改名）自动回到 ALL
                for nm, key in (("cat", "category"), ("tech", "tech"),
                                ("model", "model"), ("tag", "tag")):
                    if cfg.get(nm) not in ch[key]:
                        cfg[nm] = "ALL"
                page_items, total, pages = query(lib, tab, st)
                views[f"cards_{tab}"] = gr.update(value=render_cards(
                    page_items, settings=lib.settings, state=st, tab=tab,
                    empty=("还没有喜欢或收藏的提示语，去列表页点 ♥ / ★ 试试。"
                           if tab == "fav" else "没有匹配的提示语")))
                views[f"page_{tab}"] = gr.update(value=(
                    f'<div class="sd-page">第 <b>{cfg["page"]}</b> / {pages} 页 · '
                    f'共 <b>{total}</b> 条 · 每页 {cfg["size"]} 条'
                    + (f' · 标记：{E(cfg.get("flag_mode",""))}' if tab == "fav" else "") + "</div>"))
                for nm, key in (("cat", "category"), ("tech", "tech"),
                                ("model", "model"), ("tag", "tag")):
                    views[f"{nm}_{tab}"] = gr.update(choices=ch[key])

            views["cat_html"] = gr.update(value=render_categories(lib, st.get("cat_sel", "")))
            views["cat_pick_box"] = gr.update(value=st.get("cat_sel", ""))
            views["files_html"] = gr.update(value=render_sources(lib, st.get("file_sel", "")))
            views["file_rel_box"] = gr.update(value=st.get("file_sel", ""))
            fpath = ""
            if st.get("file_sel"):
                for r in lib.source_rows():
                    if r["rel"] == st["file_sel"]:
                        fpath = r["path"]
                        break
            views["file_path_box"] = gr.update(value=fpath)

            sel = lib.get(st.get("sel", "")) if st.get("sel") else None
            if sel:
                views["sel_html"] = gr.update(value=(
                    '<div class="sd-card" style="padding:11px">'
                    f'<div class="sd-chead"><span class="sd-num">当前选中 #{E(sel["id"])}</span>'
                    f'<span class="sd-badge sd-badge-cat">{E(sel["category"])}</span>'
                    f'<span class="sd-badge">{E(KIND_LABEL.get(sel["kind"], sel["kind"]))}</span></div>'
                    f'<div class="sd-mini" style="margin-top:6px">{E(sel["prompt"][:160])}</div></div>'))
            else:
                views["sel_html"] = gr.update(value=(
                    '<div class="sd-tray-empty">点任意卡片的「✏️ 编辑」把内容载入右侧面板，'
                    '或直接点「✨ 新建」写一条新的。</div>'))

            views["ed_status"] = gr.update(value=st.get("ed_status", "新增：填好正文后点「💾 保存」。编辑：先点卡片「✏️ 编辑」。"))
            views["trans_note"] = gr.update(value=st.get("trans_note", "翻译不会自动触发，也不会覆盖原文。"))
            views["tray_html"] = gr.update(value=render_tray(st))
            views["tray_count_md"] = gr.update(value=f"**拼装台 · {len(st.get('tray', []))} 条**")
            views["tray_preview"] = gr.update(value=tray_text(st))
            views["export_file"] = gr.update()

            for k, v in ov.items():
                views[k] = v
            return tuple(views.get(k, gr.update()) for k in ORDER) + (st,)

        # ============================================================ 事件 helpers
        def mutate(state, fn):
            st = copy.deepcopy(state)
            try:
                fn(st)
            except Exception as e:
                set_feedback(st, f"操作失败：{type(e).__name__}: {e}", False)
            return sync(st)

        def page_go(tab: str, delta: int, absolute: Optional[int] = None):
            def _f(st):
                cfg = st["tabs"][tab]
                if absolute is not None:
                    cfg["page"] = max(1, int(absolute or 1))
                else:
                    cfg["page"] = max(1, cfg["page"] + delta)
            return _f

        # ------------------------------------------------------------ 列表页事件
        def reset_tab(tab: str, s):
            st = copy.deepcopy(s)
            size = int(st["tabs"][tab]["size"])
            st["tabs"][tab] = default_tab(size)
            kind = "image" if tab == "image" else ("video" if tab == "video" else "both")
            ch = lib.choices(kind)
            ov = {
                f"q_{tab}": gr.update(value=""),
                f"size_{tab}": gr.update(value=str(size)),
                f"sort_{tab}": gr.update(value="编号"),
                f"cat_{tab}": gr.update(value="ALL", choices=ch["category"]),
                f"tech_{tab}": gr.update(value="ALL", choices=ch["tech"]),
                f"model_{tab}": gr.update(value="ALL", choices=ch["model"]),
                f"tag_{tab}": gr.update(value="ALL", choices=ch["tag"]),
            }
            if list_ui[tab]["flag"]:
                ov[f"flag_{tab}"] = gr.update(value="全部")
            set_feedback(st, "该页筛选条件与页码已重置。")
            return sync(st, **ov)

        def clear_q(tab: str, s):
            st = copy.deepcopy(s)
            st["tabs"][tab]["q"] = ""
            st["tabs"][tab]["page"] = 1
            return sync(st, **{f"q_{tab}": gr.update(value="")})

        for tab, u in list_ui.items():
            u["q"].change(lambda text, s, t=tab: mutate(s, lambda x: (
                x["tabs"][t].__setitem__("q", text), x["tabs"][t].__setitem__("page", 1))),
                inputs=[u["q"], state_comp], outputs=OUT)
            u["size"].change(lambda v, s, t=tab: mutate(s, lambda x: (
                x["tabs"][t].__setitem__("size", int(v)), x["tabs"][t].__setitem__("page", 1))),
                inputs=[u["size"], state_comp], outputs=OUT)
            u["sort"].change(lambda v, s, t=tab: mutate(s, lambda x: (
                x["tabs"][t].__setitem__("sort", v), x["tabs"][t].__setitem__("page", 1))),
                inputs=[u["sort"], state_comp], outputs=OUT)
            for nm, key in (("cat", "cat"), ("tech", "tech"), ("model", "model"), ("tag", "tag")):
                u[nm].change(lambda v, s, t=tab, k=key: mutate(s, lambda x: (
                    x["tabs"][t].__setitem__(k, v), x["tabs"][t].__setitem__("page", 1))),
                    inputs=[u[nm], state_comp], outputs=OUT)
            if u["flag"]:
                u["flag"].change(lambda v, s, t=tab: mutate(s, lambda x: (
                    x["tabs"][t].__setitem__("flag_mode", v), x["tabs"][t].__setitem__("page", 1))),
                    inputs=[u["flag"], state_comp], outputs=OUT)
                u["fav_refresh"].click(lambda s, t=tab: mutate(s, lambda x: (
                    lib.reload(), x["tabs"][t].__setitem__("page", 1),
                    set_feedback(x, "已重新读取本地数据，喜欢与收藏列表已刷新。"))),
                    inputs=[state_comp], outputs=OUT)
            u["prev"].click(lambda s, t=tab: mutate(s, page_go(t, -1)),
                            inputs=[state_comp], outputs=OUT)
            u["next"].click(lambda s, t=tab: mutate(s, page_go(t, +1)),
                            inputs=[state_comp], outputs=OUT)
            u["first"].click(lambda s, t=tab: mutate(s, page_go(t, 0, 1)),
                             inputs=[state_comp], outputs=OUT)
            u["last"].click(lambda s, t=tab: mutate(s, page_go(t, 0, 10 ** 6)),
                            inputs=[state_comp], outputs=OUT)
            u["pnum"].change(lambda v, s, t=tab: mutate(s, page_go(t, 0, int(v or 1))),
                             inputs=[u["pnum"], state_comp], outputs=OUT)
            u["refresh"].click(lambda s, t=tab: mutate(s, lambda x: (
                lib.reload(), x["tabs"][t].__setitem__("page", 1),
                set_feedback(x, "已重新扫描并读取全部数据文件。" +
                             (" ".join(lib.notices) if lib.notices else "")))),
                inputs=[state_comp], outputs=OUT)
            u["reset"].click(lambda s, t=tab: reset_tab(t, s),
                             inputs=[state_comp], outputs=OUT)
            u["clear"].click(lambda s, t=tab: clear_q(t, s),
                             inputs=[state_comp], outputs=OUT)

            def do_page_tray(s, t=tab):
                st = copy.deepcopy(s)
                its, total, _ = query(lib, t, st)
                for x in its:
                    st.setdefault("tray", []).append({"id": x["id"], "text": x["prompt"]})
                set_feedback(st, f"已把第 {st['tabs'][t]['page']} 页的 {len(its)} 条提示语"
                                 "（原文）加入拼装台，可在右侧一键复制或改分隔符。")
                return sync(st)
            u["page_tray"].click(do_page_tray, inputs=[state_comp], outputs=OUT)

            def do_export_page(s, t=tab):
                st = copy.deepcopy(s)
                its, total, _ = query(lib, t, st)
                path = make_export(lib, f"{t}_第{st['tabs'][t]['page']}页", its)
                set_feedback(st, f"已导出当前页 {len(its)} 条到 {os.path.basename(path)}")
                return sync(st, export_file=gr.update(value=path, label="⬇️ 已导出当前页 .txt"))
            u["export_page"].click(do_export_page, inputs=[state_comp], outputs=OUT)

            def do_export_all(s, t=tab):
                st = copy.deepcopy(s)
                st["tabs"][t]["page"] = 1
                st["tabs"][t]["size"] = 10 ** 6
                its, total, _ = query(lib, t, st)
                st["tabs"][t]["size"] = s["tabs"][t]["size"]
                st["tabs"][t]["page"] = s["tabs"][t]["page"]
                path = make_export(lib, f"{t}_全部筛选结果", its)
                set_feedback(st, f"已导出全部筛选结果 {total} 条到 {os.path.basename(path)}")
                return sync(st, export_file=gr.update(value=path, label="⬇️ 已导出全部结果 .txt"))
            u["export_all"].click(do_export_all, inputs=[state_comp], outputs=OUT)

        # ------------------------------------------------------------ 桥接 dispatch
        def dispatch(item_id: str, action: str, payload: str, state):
            st = copy.deepcopy(state)
            ov: Dict[str, Any] = {}
            try:
                item_id = (item_id or "").strip()
                payload = payload or ""
                if action == "cancel":
                    st["pending"] = None
                    set_feedback(st, "已取消待确认操作。")
                elif action in ("like", "fav"):
                    field = "like" if action == "like" else "favorite"
                    newv = lib.toggle_flag(item_id, field)
                    it = lib.get(item_id) or {}
                    set_feedback(st, f"#{item_id} {'喜欢 ♥' if field == 'like' else '收藏 ★'}"
                                    f"已{'开启' if newv else '取消'}，状态已写入本地文件：{it.get('source','')}")
                elif action == "tray":
                    st.setdefault("tray", []).append({"id": item_id, "text": payload})
                    set_feedback(st, f"已把 #{item_id} 的当前权重版本加入拼装台（共 {len(st['tray'])} 条）。")
                elif action == "tray_del":
                    idx = int(payload or 0)
                    if 0 <= idx < len(st.get("tray", [])):
                        st["tray"].pop(idx)
                        set_feedback(st, "已从拼装台移除一条。")
                elif action == "edit":
                    it = lib.get(item_id)
                    if not it:
                        raise KeyError("条目不存在，请重新扫描读取本地数据")
                    st["sel"] = item_id
                    st["ed_status"] = f"正在编辑 #{item_id}（文件：{it['source']}）。改完点「💾 保存」。"
                    ov.update(editor_values(it, lib))
                    set_feedback(st, f"已把 #{item_id} 载入右侧编辑面板。")
                elif action == "select":
                    st["sel"] = item_id
                elif action == "saveweight":
                    lib.update_item(item_id, {"prompt": payload})
                    set_feedback(st, f"已把调整后的权重版本保存回 #{item_id} 的数据文件。")
                elif action == "resetweight":
                    st.setdefault("weights", {}).pop(item_id, None)
                    set_feedback(st, f"已重置 #{item_id} 的滑块覆盖值。")
                elif action == "delete":
                    it = lib.get(item_id)
                    st["pending"] = {"type": "item", "id": item_id,
                                     "message": f"确定删除提示语 #{item_id}（{E((it or {}).get('category',''))}）吗？"
                                                "这会从它所属的数据文件里永久移除，不可撤销。"}
                    set_feedback(st, "删除请求已发起，请在页面上方确认。", True)
                elif action == "translate":
                    do_translate(st, ov, payload or (lib.get(item_id) or {}).get("prompt", ""), "自动互译", item_id)
                elif action == "file_raw":
                    st["file_sel"] = payload
                    st["file_raw"] = lib.read_raw(payload)
                    ov["file_raw_box"] = gr.update(value=st["file_raw"])
                    set_feedback(st, f"已载入 {payload} 的原始内容，可直接编辑后保存。")
                elif action == "file_delete":
                    st["file_sel"] = payload
                    n = sum(1 for x in lib.all_items() if x["source"] == payload)
                    st["pending"] = {"type": "file", "id": payload,
                                     "message": f"确定删除数据文件 {E(payload)} 吗？"
                                                f"该文件里的 {n} 条提示语会一并移除，且文件会被物理删除。"}
                    set_feedback(st, "删除数据文件需要二次确认。")
                elif action == "cat_pick":
                    st["cat_sel"] = payload
                    ov["cat_pick_box"] = gr.update(value=payload)
                    ov["cat_rename_new"] = gr.update(value=payload)
                    set_feedback(st, f"已选中类别「{payload}」。")
                elif action == "cat_rename_req":
                    st["cat_sel"] = payload
                    ov["cat_pick_box"] = gr.update(value=payload)
                    ov["cat_rename_new"] = gr.update(value=payload)
                    set_feedback(st, f"已在右侧填入「{payload}」，改成新名字后点「✏️ 重命名类别」。")
                elif action == "cat_delete":
                    st["cat_sel"] = payload
                    n = lib.category_counts().get(payload, 0)
                    st["pending"] = {"type": "category", "id": payload,
                                     "message": f"确定删除类别「{E(payload)}」吗？"
                                                f"该类别下的 {n} 条提示语会全部被删除，并写回各自的数据文件，不可撤销。"}
                    set_feedback(st, "删除类别需要二次确认。")
                else:
                    set_feedback(st, f"未知操作：{action}", False)
            except Exception as e:
                set_feedback(st, f"操作失败：{type(e).__name__}: {e}", False)
            return sync(st, **ov)

        bridge_go.click(dispatch, inputs=[bridge_id, bridge_action, bridge_payload, state_comp],
                        outputs=OUT, api_name="bridge")

        # ------------------------------------------------------------ 编辑面板
        def editor_values(it: Dict[str, Any], l: Library):
            files = ["自动（默认文件）"] + [r["rel"] for r in l.source_rows()]
            return {
                "ed_id": gr.update(value=it["id"]),
                "ed_kind": gr.update(value=it["kind"]),
                "ed_cat": gr.update(value=it["category"],
                                    choices=["ALL"] + l.category_names("both")),
                "ed_newcat": gr.update(value=""),
                "ed_prompt": gr.update(value=it.get("prompt", "")),
                "ed_neg": gr.update(value=it.get("negative", "")),
                "ed_tip": gr.update(value=it.get("tip", "")),
                "ed_tags": gr.update(value=", ".join(it.get("tags", []))),
                "ed_model": gr.update(value=it.get("model", "")),
                "ed_syntax": gr.update(value=it.get("syntax") or "（跟随全局）"),
                "ed_subject": gr.update(value=it.get("subject", "")),
                "ed_camera": gr.update(value=it.get("camera", "")),
                "ed_duration": gr.update(value=it.get("duration", "")),
                "ed_fps": gr.update(value=it.get("fps", "")),
                "ed_motion": gr.update(value=it.get("motion", "")),
                "ed_target": gr.update(value=it.get("source", "自动（默认文件）")
                                       if it.get("source") in files else "自动（默认文件）",
                                       choices=files),
            }

        def clear_editor(s):
            st = copy.deepcopy(s)
            ov = {k: gr.update(value=v) for k, v in {
                "ed_id": "", "ed_kind": "image", "ed_newcat": "", "ed_prompt": "",
                "ed_neg": "", "ed_tip": "", "ed_tags": "", "ed_model": "通用",
                "ed_syntax": "（跟随全局）", "ed_subject": "", "ed_camera": "",
                "ed_duration": "", "ed_fps": "", "ed_motion": "",
                "ed_target": "自动（默认文件）"}.items()}
            ov["ed_cat"] = gr.update(value="ALL", choices=["ALL"] + lib.category_names("both"))
            st["sel"] = ""
            st["ed_status"] = "新增模式：填好提示语正文，选择类别（或填写新类别），点「💾 保存」。"
            set_feedback(st, "已清空编辑面板，进入新增模式。")
            return sync(st, **ov)
        btn_ed_new.click(clear_editor, inputs=[state_comp], outputs=OUT)

        def save_editor(eid, kind, cat, newcat, prompt, neg, tip, tags, model, syntax,
                        subject, camera, duration, fps, motion, target, s):
            st = copy.deepcopy(s)
            ov: Dict[str, Any] = {}
            try:
                if not str(prompt or "").strip():
                    raise ValueError("提示语正文不能为空")
                use_cat = str(newcat or "").strip() or ("" if cat in ("", "ALL") else str(cat))
                if str(newcat or "").strip():
                    lib.add_category(str(newcat).strip(), kind if kind != "both" else "both", "在编辑面板新建")
                    use_cat = str(newcat).strip()
                data = {
                    "kind": kind, "category": use_cat or "未分类", "prompt": prompt.strip(),
                    "negative": neg or "", "tip": tip or "",
                    "tags": [x.strip() for x in str(tags or "").split(",") if x.strip()],
                    "model": model or "通用",
                    "syntax": "" if syntax == "（跟随全局）" else syntax,
                    "subject": subject or "", "camera": camera or "",
                    "duration": duration or "", "fps": fps or "", "motion": motion or "",
                }
                if str(eid or "").strip():
                    it = lib.update_item(str(eid).strip(), data)
                    set_feedback(st, f"已保存修改：#{it['id']} → {it['source']}")
                else:
                    tgt = "" if target in ("", "自动（默认文件）", None) else target
                    it = lib.add_item(data, tgt)
                    set_feedback(st, f"已新增 #{it['id']}，写入 {it['source']}")
                st["sel"] = it["id"]
                st["ed_status"] = f"已保存 #{it['id']}（{it['source']}）。"
                ov.update(editor_values(it, lib))
            except Exception as e:
                set_feedback(st, f"保存失败：{type(e).__name__}: {e}", False)
                st["ed_status"] = "⚠️ " + str(e)
            return sync(st, **ov)
        btn_ed_save.click(save_editor,
                          inputs=[V["ed_id"], V["ed_kind"], V["ed_cat"], V["ed_newcat"],
                                  V["ed_prompt"], V["ed_neg"], V["ed_tip"], V["ed_tags"],
                                  V["ed_model"], V["ed_syntax"], V["ed_subject"], V["ed_camera"],
                                  V["ed_duration"], V["ed_fps"], V["ed_motion"], V["ed_target"],
                                  state_comp], outputs=OUT)

        def del_editor(eid, s):
            st = copy.deepcopy(s)
            if not str(eid or "").strip():
                set_feedback(st, "当前是新增模式，没有可删除的条目。", False)
            else:
                st["pending"] = {"type": "item", "id": str(eid).strip(),
                                 "message": f"确定删除正在编辑的提示语 #{E(str(eid))} 吗？此操作不可撤销。"}
                set_feedback(st, "删除请求已发起，请在页面上方确认。")
            return sync(st)
        btn_ed_del.click(del_editor, inputs=[V["ed_id"], state_comp], outputs=OUT)

        btn_ed_copy_weight.click(lambda eid, s: dispatch(eid or "", "resetweight", "", s),
                                 inputs=[V["ed_id"], state_comp], outputs=OUT)

        def do_translate(st, ov, text, direction, item_id=""):
            cfg = lib.settings.get("translate", {})
            if not cfg.get("enabled", True) or cfg.get("provider") == "off":
                ok, out, note = False, "", "翻译已在设置中关闭。"
            else:
                tgt = LANG_CHOICES.get("中文", "zh-CN")
                if direction == "译成英文":
                    tgt = "en"
                elif direction == "译成中文":
                    tgt = "zh-CN"
                ok, out, note = translate(
                    text, target=tgt, provider=cfg.get("provider", "gtx"),
                    custom_endpoint=cfg.get("custom_endpoint", ""),
                    timeout=int(cfg.get("timeout", 8)),
                    auto_reverse=(direction == "自动互译"))
            st["trans"] = out
            st["trans_note"] = note
            ov["trans_out"] = gr.update(value=out)
            set_feedback(st, f"{'🌐 ' + note if ok else '🌐 ' + note}"
                             + (f"（#{item_id}）" if item_id else ""), ok)

        def trans_click(prompt, direction, s):
            st = copy.deepcopy(s)
            ov: Dict[str, Any] = {}
            text = prompt or (lib.get(st.get("sel", "")) or {}).get("prompt", "")
            do_translate(st, ov, text, direction)
            return sync(st, **ov)
        btn_trans.click(trans_click, inputs=[V["ed_prompt"], trans_dir, state_comp], outputs=OUT)

        def trans_use(txt, s):
            st = copy.deepcopy(s)
            if not str(txt or "").strip():
                set_feedback(st, "译文是空的，先点「🌐 翻译」。", False)
                return sync(st)
            set_feedback(st, "已用译文替换编辑面板中的正文（还没保存，确认后点「💾 保存」）。")
            return sync(st, ed_prompt=gr.update(value=txt))
        btn_trans_use.click(trans_use, inputs=[V["trans_out"], state_comp], outputs=OUT)

        def guide_apply(name, s):
            st = copy.deepcopy(s)
            g = next((x for x in load_guides() if x["name"] == name), None)
            if not g:
                return sync(st)
            set_feedback(st, f"已把「{name}」的示例与推荐结构套用到编辑面板，可直接改后保存。")
            return sync(st,
                        ed_prompt=gr.update(value=g.get("example", "")),
                        ed_model=gr.update(value=g.get("name", "")),
                        ed_syntax=gr.update(value=g.get("syntax", "（跟随全局）")),
                        ed_tip=gr.update(value="推荐结构：" + str(g.get("structure", ""))
                                         + " | " + str(g.get("tips", ""))))
        btn_guide_apply.click(guide_apply, inputs=[guide_dd, state_comp], outputs=OUT)

        # ------------------------------------------------------------ 拼装台
        tray_sep.change(lambda v, s: mutate(s, lambda x: x.__setitem__("tray_sep", v)),
                        inputs=[tray_sep, state_comp], outputs=OUT)

        def tray_clear(s):
            st = copy.deepcopy(s)
            if not st.get("tray"):
                set_feedback(st, "拼装台已经是空的。")
            else:
                st["pending"] = {"type": "tray", "id": "",
                                 "message": f"确定清空拼装台里的 {len(st['tray'])} 条提示语吗？"}
                set_feedback(st, "清空拼装台需要二次确认。")
            return sync(st)
        btn_tray_clear.click(tray_clear, inputs=[state_comp], outputs=OUT)

        def tray_export(s):
            st = copy.deepcopy(s)
            if not st.get("tray"):
                set_feedback(st, "拼装台是空的，没有可导出的内容。", False)
                return sync(st)
            d = os.path.join(lib.root, "exports")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, f"SD拼装台_{time.strftime('%Y%m%d_%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(tray_text(st))
            set_feedback(st, f"已导出拼装结果（{len(st['tray'])} 条）。")
            return sync(st, export_file=gr.update(value=path, label="⬇️ 已导出拼装台 .txt"))
        btn_tray_export.click(tray_export, inputs=[state_comp], outputs=OUT)

        # ------------------------------------------------------------ 二次确认
        def confirm_yes(s):
            st = copy.deepcopy(s)
            p = st.get("pending") or {}
            ov: Dict[str, Any] = {}
            try:
                typ = p.get("type")
                if typ == "item":
                    lib.delete_item(p["id"])
                    set_feedback(st, f"已删除提示语 #{p['id']}，改动已写回本地数据文件。")
                    if st.get("sel") == p["id"]:
                        st["sel"] = ""
                        ov.update({k: gr.update(value="") for k in
                                   ("ed_id", "ed_prompt", "ed_tip", "ed_neg")})
                elif typ == "category":
                    n = lib.delete_category(p["id"])
                    set_feedback(st, f"已删除类别「{p['id']}」及其 {n} 条提示语。")
                    st["cat_sel"] = ""
                    ov["cat_pick_box"] = gr.update(value="")
                    ov["cat_rename_new"] = gr.update(value="")
                elif typ == "file":
                    n = lib.delete_file(p["id"])
                    set_feedback(st, f"已删除数据文件 {p['id']}（原含 {n} 条）。")
                    st["file_sel"] = ""
                    st["file_raw"] = ""
                    ov["file_raw_box"] = gr.update(value="")
                elif typ == "tray":
                    n = len(st.get("tray", []))
                    st["tray"] = []
                    set_feedback(st, f"已清空拼装台（{n} 条）。")
                else:
                    set_feedback(st, "没有待确认的操作。", False)
            except Exception as e:
                set_feedback(st, f"执行失败：{type(e).__name__}: {e}", False)
            st["pending"] = None
            return sync(st, **ov)
        btn_yes.click(confirm_yes, inputs=[state_comp], outputs=OUT)

        def confirm_no(s):
            st = copy.deepcopy(s)
            st["pending"] = None
            set_feedback(st, "已取消，未做任何改动。")
            return sync(st)
        btn_no.click(confirm_no, inputs=[state_comp], outputs=OUT)

        # ------------------------------------------------------------ 类别管理
        def cat_add(name, kind, note, s):
            st = copy.deepcopy(s)
            try:
                lib.add_category(name, kind, note)
                st["cat_sel"] = str(name).strip()
                set_feedback(st, f"已新增类别「{st['cat_sel']}」（名称唯一性已校验）。")
            except Exception as e:
                set_feedback(st, f"新增类别被拒绝：{e}", False)
            return sync(st, cat_pick_box=gr.update(value=st.get("cat_sel", "")))
        btn_cat_add.click(cat_add, inputs=[cat_new_name, cat_new_kind, cat_new_note, state_comp],
                          outputs=OUT)

        def cat_rename(newname, s):
            st = copy.deepcopy(s)
            old = st.get("cat_sel", "")
            if not old:
                set_feedback(st, "请先在类别表格里点「选中」，或点「改名」。", False)
                return sync(st)
            try:
                n = lib.rename_category(old, str(newname).strip())
                st["cat_sel"] = str(newname).strip()
                set_feedback(st, f"类别「{old}」已改名为「{st['cat_sel']}」，同步更新了 {n} 条提示语。")
            except Exception as e:
                set_feedback(st, f"重命名被拒绝：{e}", False)
            return sync(st, cat_pick_box=gr.update(value=st.get("cat_sel", "")))
        btn_cat_rename.click(cat_rename, inputs=[V["cat_rename_new"], state_comp], outputs=OUT)

        def cat_delete_btn(s):
            st = copy.deepcopy(s)
            name = st.get("cat_sel", "")
            if not name:
                set_feedback(st, "请先选中一个类别。", False)
                return sync(st)
            n = lib.category_counts().get(name, 0)
            st["pending"] = {"type": "category", "id": name,
                             "message": f"确定删除类别「{E(name)}」吗？该类别下 {n} 条提示语会全部删除，不可撤销。"}
            set_feedback(st, "删除类别需要二次确认。")
            return sync(st)
        btn_cat_delete.click(cat_delete_btn, inputs=[state_comp], outputs=OUT)

        # ------------------------------------------------------------ 数据文件
        def rescan(s, read: bool = True):
            st = copy.deepcopy(s)
            try:
                if read:
                    lib.reload()
                    msg = f"已重新扫描 {len(lib.sources)} 个文件、读取 {len(lib.items)} 条提示语。"
                else:
                    lib.scan()
                    msg = f"已重新扫描文件列表，发现 {len(lib.sources)} 个数据文件（尚未重新读取内容）。"
                if lib.notices:
                    msg += " " + " ".join(lib.notices)
                    set_feedback(st, msg, False)
                else:
                    set_feedback(st, msg)
                for t in TAB_KEYS:
                    st["tabs"][t]["page"] = 1
            except Exception as e:
                set_feedback(st, f"扫描失败：{type(e).__name__}: {e}", False)
            return sync(st)
        def scan_only(s):
            return rescan(s, False)

        def reload_all(s):
            return rescan(s, True)

        btn_scan.click(scan_only, inputs=[state_comp], outputs=OUT)
        btn_reload.click(reload_all, inputs=[state_comp], outputs=OUT)

        def opendir(s):
            st = copy.deepcopy(s)
            try:
                path = lib.prompts_dir
                if sys.platform.startswith("win"):
                    os.startfile(path)  # type: ignore
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
                set_feedback(st, f"已尝试在文件管理器中打开：{path}")
            except Exception as e:
                set_feedback(st, f"无法打开目录（无图形环境时请手动复制路径）：{path} · {e}", False)
            return sync(st)
        btn_opendir.click(opendir, inputs=[state_comp], outputs=OUT)

        def file_new(name, fmt, kind, desc, s):
            st = copy.deepcopy(s)
            try:
                rel = lib.create_file(name, fmt, kind, desc)
                st["file_sel"] = rel
                set_feedback(st, f"已新建数据文件 {rel}，重新扫描后即可写入提示语。")
                lib.reload()
            except Exception as e:
                set_feedback(st, f"新建文件失败：{e}", False)
            return sync(st)
        btn_file_new.click(file_new, inputs=[f_name, f_fmt, f_kind, f_desc, state_comp], outputs=OUT)

        def raw_save(rel, text, s):
            st = copy.deepcopy(s)
            try:
                lib.save_raw(rel, text)
                st["file_raw"] = text
                set_feedback(st, f"已保存 {rel} 并重新读取全部数据。" +
                             (" ".join(lib.notices) if lib.notices else ""))
            except Exception as e:
                set_feedback(st, f"保存失败（请检查格式是否合法）：{type(e).__name__}: {e}", False)
            return sync(st)
        btn_raw_save.click(raw_save, inputs=[V["file_rel_box"], V["file_raw_box"], state_comp],
                           outputs=OUT)

        def file_delete_btn(s, rel):
            st = copy.deepcopy(s)
            rel = rel or st.get("file_sel", "")
            if not rel:
                set_feedback(st, "请先在文件列表里点「查看 / 编辑」选中一个文件。", False)
                return sync(st)
            n = sum(1 for x in lib.all_items() if x["source"] == rel)
            st["pending"] = {"type": "file", "id": rel,
                             "message": f"确定删除数据文件 {E(rel)} 及其中的 {n} 条提示语吗？文件会被物理删除，不可撤销。"}
            set_feedback(st, "删除数据文件需要二次确认。")
            return sync(st)
        btn_file_delete.click(file_delete_btn, inputs=[state_comp, V["file_rel_box"]], outputs=OUT)

        # ------------------------------------------------------------ 负面词
        def neg_save(n0, n1, n2, s):
            st = copy.deepcopy(s)
            presets = dict(lib.settings.get("negative_presets", {}))
            keys = list(presets.keys())
            for i, val in enumerate((n0, n1, n2)):
                if i < len(keys):
                    presets[keys[i]] = val
            lib.save_settings({"negative_presets": presets})
            set_feedback(st, "三套负面提示词已保存到 data/config/settings.json。")
            return sync(st)
        btn_neg_save.click(neg_save, inputs=neg_boxes + [state_comp], outputs=OUT)

        def neg_reset(s):
            st = copy.deepcopy(s)
            lib.save_settings({"negative_presets": copy.deepcopy(DEFAULT_SETTINGS["negative_presets"])})
            ov = {f"neg{i}": gr.update(value=v) for i, v in
                  enumerate(list(lib.settings["negative_presets"].values())[:3])}
            set_feedback(st, "已恢复默认负面提示词。")
            return sync(st, **ov)
        btn_neg_reset.click(neg_reset, inputs=[state_comp], outputs=OUT)

        def make_neg_to_editor(idx: int):
            def _f(s):
                st = copy.deepcopy(s)
                vals = list(lib.settings.get("negative_presets", {}).values())
                txt = vals[idx] if idx < len(vals) else ""
                set_feedback(st, f"已把第 {idx + 1} 套负面词填入右侧编辑面板（记得点「💾 保存」才会写入条目）。")
                return sync(st, ed_neg=gr.update(value=txt))
            return _f

        for i, b in enumerate(neg_to_editor_btns):
            b.click(make_neg_to_editor(i), inputs=[state_comp], outputs=OUT)

        # ------------------------------------------------------------ 设置
        def set_save(page, profile, tpl, target, provider, lang, timeout, endpoint, enabled, s):
            st = copy.deepcopy(s)
            try:
                lib.save_settings({
                    "page_size": int(page), "syntax_profile": profile, "custom_tpl": tpl,
                    "default_target_file": target,
                    "translate": {"provider": provider, "target": LANG_CHOICES.get(lang, "zh-CN"),
                                  "timeout": int(timeout), "custom_endpoint": endpoint,
                                  "enabled": bool(enabled)},
                })
                set_feedback(st, "设置已保存到 data/config/settings.json。权重语法与翻译配置立即生效。")
            except Exception as e:
                set_feedback(st, f"保存设置失败：{e}", False)
            return sync(st)
        btn_set_save.click(set_save,
                           inputs=[set_page, set_profile, set_tpl, set_target, set_provider,
                                   set_tgt_lang, set_timeout, set_endpoint, set_enabled, state_comp],
                           outputs=OUT)

        def set_reset(s):
            st = copy.deepcopy(s)
            lib.load_settings()
            set_feedback(st, "已从 settings.json 重新载入设置。")
            return sync(st)
        btn_set_reset.click(set_reset, inputs=[state_comp], outputs=OUT)

        def gm_change(v, s):
            st = copy.deepcopy(s)
            lib.settings["global_weight"] = float(v)
            set_feedback(st, f"全局权重倍率设为 ×{float(v):.2f}（在设置里可持久化）。")
            return sync(st)
        gm.change(gm_change, inputs=[gm, state_comp], outputs=OUT)

        def profile_change(v, s):
            st = copy.deepcopy(s)
            lib.settings["syntax_profile"] = v
            set_feedback(st, f"默认权重语法切换为：{PROFILES[v].name}（在设置里可持久化）。")
            return sync(st)
        set_profile.change(profile_change, inputs=[set_profile, state_comp], outputs=OUT)

        # ------------------------------------------------------------ 初始渲染
        demo.load(lambda s: sync(s), inputs=[state_comp], outputs=OUT)

        demo._pd_launch_kwargs = launch_kwargs
    return demo


# ==================================================================== 启动
def main():
    ap = argparse.ArgumentParser(description="PromptDock")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--data-dir", default=None, help="数据目录（默认 ./data）")
    ap.add_argument("--share", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    lib = Library(args.data_dir)
    print(f"[PromptDock] 数据目录：{lib.root}")
    print(f"[PromptDock] 已加载 {len(lib.items)} 条提示语 / "
          f"{len(lib.sources)} 个数据文件 / {len(lib.categories)} 个类别")
    if lib.notices:
        for n in lib.notices:
            print("  ", n)
    demo = make_app(lib)
    launch_kwargs = getattr(demo, "_pd_launch_kwargs", {})
    if GRADIO_MAJOR >= 6:
        # 6.x：去掉 show_api，改用 footer_links；theme/css/head 已在 launch 传入
        launch_kwargs.setdefault("footer_links", [])
    else:
        launch_kwargs["show_api"] = False
    demo.launch(server_name=args.host, server_port=args.port,
                inbrowser=not args.no_browser, share=args.share,
                allowed_paths=[lib.root, os.path.join(HERE, "assets"),
                               os.path.join(HERE, "reference")],
                **launch_kwargs)


if __name__ == "__main__":
    main()
