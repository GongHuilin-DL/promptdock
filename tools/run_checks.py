# -*- coding: utf-8 -*-
"""综合自检：存储层 CRUD / 权重语法 / 卡片渲染 / 界面函数 / 翻译容错。"""
import copy
import json
import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.storage import Library
from core.syntax import PROFILES, get_profile, tokenize, rebuild
from core.cards import render_cards, render_sources, render_categories
from core.translate import split_chunks, translate
import app

errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)
    print(("  OK  " if cond else " FAIL ") + msg)


# ---------------------------------------------------------------- 1. 临时库 CRUD
tmp = tempfile.mkdtemp(prefix="sdpm_test_")
os.makedirs(os.path.join(tmp, "prompts"))
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "prompts")
for f in ("01_文生图_内置精选.json", "02_文生视频_内置精选.json"):
    shutil.copy(os.path.join(SRC, f), os.path.join(tmp, "prompts", f))
lib = Library(tmp)
s = lib.stats()
check(s["total"] == 760 and s["image"] == 600 and s["video"] == 160,
      f"加载 760 条 / 600 图 / 160 视频，实际 {s}")
check(s["files"] == 2, "扫描到 2 个数据文件")
check(len(lib.categories) >= 60, f"类别数 >= 60，实际 {len(lib.categories)}")
check(lib.get("img-0001") is not None, "按 id 取条目")

# 新增
it = lib.add_item({"kind": "image", "category": "人像与人物", "prompt": "test prompt (glow:1.2)",
                   "tech": "单元测试", "tags": ["test"]})
check(lib.stats()["total"] == 761 and os.path.exists(os.path.join(tmp, "prompts", "99_自定义提示语.json")),
      "新增提示语并自动写入默认文件")
# 编辑
lib.update_item(it["id"], {"prompt": "edited prompt (glow:1.5)", "category": "人像与人物"})
check(lib.get(it["id"])["prompt"].startswith("edited"), "编辑提示语写回文件")
# 标记喜欢 / 收藏
lib.toggle_flag(it["id"], "like")
lib.toggle_flag(it["id"], "favorite")
lib.reload()
check(lib.get(it["id"])["like"] is True and lib.get(it["id"])["favorite"] is True,
      "喜欢 / 收藏状态持久化，重载后仍在")
# 类别
try:
    lib.add_category("人像与人物", "both", "重名测试")
    check(False, "重名类别应被拒绝")
except ValueError as e:
    check("已存在" in str(e), f"重名类别被拒绝并给出提示：{e}")
lib.add_category("ZZ测试类别", "both", "备注")
check("ZZ测试类别" in lib.category_names(), "新增类别")
n = lib.rename_category("ZZ测试类别", "YY改名类别")
check(n == 0 and "YY改名类别" in lib.category_names(), "重命名类别")
try:
    lib.rename_category("YY改名类别", "人像与人物")
    check(False, "重名重命名应被拒绝")
except ValueError as e:
    check("已存在" in str(e), "重名重命名被拒绝")
lib.add_item({"kind": "image", "category": "YY改名类别", "prompt": "to be deleted"})
check(lib.delete_category("YY改名类别") == 1, "删除类别连带删除其下 1 条提示语")

# 多文件：新建 jsonl + 直接编辑原始内容 + 删除文件
rel = lib.create_file("03_test.jsonl", "jsonl", "video", "测试")
check(rel == "prompts/03_test.jsonl", "新建 JSONL 数据文件")
lib.save_raw(rel, '# comment\n{"prompt":"video test","category":"运镜与镜头运动","kind":"video"}\n')
found = [x for x in lib.all_items() if x["prompt"] == "video test"]
check(len(found) == 1 and found[0]["kind"] == "video", "直接编辑数据文件后重新读取生效")
check(any("# comment" in open(os.path.join(tmp, rel), encoding="utf-8").read() for _ in [0]),
      "JSONL 注释行写回时保留")
lib.delete_file(rel)
check(not os.path.exists(os.path.join(tmp, rel)), "删除数据文件")

# 删除条目
before = lib.stats()["total"]
lib.delete_item(it["id"])
check(lib.stats()["total"] == before - 1, "删除单条提示语")

# 设置 / 负面词
lib.save_settings({"page_size": 12, "translate": {"provider": "off"}})
check(lib.load_settings()["page_size"] == 12, "设置持久化")
check(len(lib.settings["negative_presets"]) >= 3, "负面词预设 >= 3 套")

# ---------------------------------------------------------------- 2. 权重语法
p = get_profile("sd")
tks = tokenize("a girl, (freckles:1.2), <lora:detail:0.8>, [cat:dog:0.5], (style:0.7)", p)
check(len(tks) == 4, f"解析出权重/LoRA/分步 token 共 4 个，实际 {len(tks)}")
check(any(t.type == "lora" for t in tks) and any(t.type == "step" for t in tks),
      "LoRA 与分步替换语法被识别")
check(not any(":" in t.word for t in tks if t.type == "w"), "分步混合 (A:B:0.6) 不会被误当权重")
r = rebuild("a girl, (freckles:1.2)", tokenize("a girl, (freckles:1.2)", p), {0: 1.5}, 1.0, p)
check("(freckles:1.5)" in r, "按滑块值重建提示词")
r2 = rebuild("a girl, (freckles:1.2)", tokenize("a girl, (freckles:1.2)", p), {0: 1.5}, 1.2, p)
check("(freckles:1.8)" in r2, "全局倍率乘到权重值")
mj = get_profile("mj")
check(len(tokenize("diver::2 water::0.5", mj)) == 2, "Midjourney :: 权重语法")
check(len(tokenize("a long natural language sentence", get_profile("flux"))) == 0,
      "FLUX 自然语言画像不解析数值权重")
custom = get_profile("custom", "(({w}:{v}))")
check(custom.render("cat", 1.3) == "((cat:1.3))", "自定义权重模板生效")

# ---------------------------------------------------------------- 3. 卡片渲染
st = app.default_state(lib)
page, total, pages = app.query(lib, "image", st)
check(total >= 600 and pages > 1, f"文生图默认分页：共 {total} 条 / {pages} 页")
html_cards = render_cards(page, settings=lib.settings, state=st, tab="image")
check(html_cards.count('class="sd-card"') == len(page), "卡片数量等于每页条数")
check("sd-wr" in html_cards and "data-sdact" in html_cards, "卡片包含权重滑块与操作按钮")
check("sd-files" in render_sources(lib, ""), "数据文件表格渲染")
check("类别" in render_categories(lib, ""), "类别表格渲染")

# ---------------------------------------------------------------- 4. 翻译容错
check(len(split_chunks("x" * 5000)) >= 2, "长文本分块")
ok, out, note = translate("hello world", provider="off")
check(not ok and "关闭" in note, "翻译关闭时不发网络请求")
check(isinstance(note, str), "翻译失败返回可读说明而非异常")

# ---------------------------------------------------------------- 5. 界面函数
demo = app.make_app(lib)
by_name = {}
for f in demo.fns.values():
    fn = getattr(f, "fn", None)
    if fn is not None:
        by_name.setdefault(getattr(fn, "__name__", "?"), []).append(f)
print("界面事件数:", len(demo.fns), "具名函数:", sorted(k for k in by_name if k != "<lambda>"))

state = app.default_state(lib)


def call(name, *args, idx=0):
    fs = by_name.get(name)
    if not fs:
        errors.append(f"缺少函数 {name}")
        print(" FAIL 缺少函数", name)
        return None
    f = fs[idx]
    try:
        ret = f.fn(*args)
        n = len(ret) if isinstance(ret, tuple) else 1
        check(n == len(f.outputs), f"{name} 返回 {n} 个输出 = 输出组件数 {len(f.outputs)}")
        return ret
    except Exception as e:
        errors.append(f"{name} 抛异常: {e}")
        traceback.print_exc()
        return None


r = call("dispatch", "img-0001", "like", "", state)
state = r[-1] if r else state
r = call("dispatch", "img-0001", "fav", "", state)
state = r[-1] if r else state
r = call("dispatch", "img-0002", "tray", "hello (glow:1.4)", state)
state = r[-1] if r else state
check(len(state.get("tray", [])) == 1, "拼装台加入一条")
r = call("dispatch", "img-0001", "edit", "", state)
state = r[-1] if r else state
r = call("dispatch", "img-0003", "delete", "", state)
state = r[-1] if r else state
check(state.get("pending", {}).get("type") == "item", "删除条目进入二次确认")
r = call("confirm_no", state)
state = r[-1] if r else state
check(state.get("pending") is None and lib.get("img-0003") is not None, "取消确认后条目仍在")
r = call("dispatch", "", "cancel", "", state)
state = r[-1] if r else state

# 编辑面板：新增一条
ed_args = ("", "image", "人像与人物", "", "new prompt (light:1.2)", "",
           "单元测试技巧", "test,unit", "SD 1.5", "（跟随全局）", "portrait",
           "", "", "", "", "自动（默认文件）", state)
r = call("save_editor", *ed_args)
state = r[-1] if r else state
check(any(x["prompt"] == "new prompt (light:1.2)" for x in lib.all_items()),
      "通过编辑面板新增提示语")
# 重名类别拒绝
r = call("cat_add", "人像与人物", "both", "", state)
state = r[-1] if r else state
check("拒绝" in state.get("feedback", ""), "界面新增重名类别被拒绝")
r = call("cat_add", "QQ界面新类别", "both", "备注", state)
state = r[-1] if r else state
check("QQ界面新类别" in lib.category_names(), "界面新增类别成功")
r = call("cat_delete_btn", state)
state = r[-1] if r else state
check(state.get("pending", {}).get("type") == "category", "删除类别进入二次确认")
r = call("confirm_yes", state)
state = r[-1] if r else state
check("QQ界面新类别" not in lib.category_names(), "确认后类别已删除")

# 数据文件：扫描 / 新建 / 保存原始内容
r = call("reload_all", state)
state = r[-1] if r else state
r = call("scan_only", state)
state = r[-1] if r else state
r = call("file_new", "04_ui.json", "json", "image", "界面新建", state)
state = r[-1] if r else state
check(os.path.exists(os.path.join(tmp, "prompts", "04_ui.json")), "界面新建数据文件")
r = call("raw_save", "prompts/04_ui.json",
         json.dumps({"items": [{"prompt": "raw edited prompt", "category": "未分类"}]}, ensure_ascii=False),
         state)
state = r[-1] if r else state
check(any(x["prompt"] == "raw edited prompt" for x in lib.all_items()), "界面编辑原始数据文件后生效")
r = call("file_delete_btn", state, "prompts/04_ui.json")
state = r[-1] if r else state
check(state.get("pending", {}).get("type") == "file", "删除文件进入二次确认")
r = call("confirm_yes", state)
state = r[-1] if r else state
check(not os.path.exists(os.path.join(tmp, "prompts", "04_ui.json")), "确认后数据文件被删除")

# 设置 / 负面词 / 拼装台 / 翻译按钮（关闭状态，不发网络）
r = call("set_save", "12", "sd", "({w}:{v})", "99_自定义提示语.json",
         "off", "中文", 8, "", True, state)
state = r[-1] if r else state
check(lib.settings["syntax_profile"] == "sd", "界面保存设置")
r = call("neg_reset", state)
state = r[-1] if r else state
r = call("tray_clear", state)
state = r[-1] if r else state
check(state.get("pending", {}).get("type") == "tray", "清空拼装台需要二次确认")
r = call("confirm_yes", state)
state = r[-1] if r else state
check(len(state.get("tray", [])) == 0, "确认后拼装台清空")
r = call("trans_click", "a test prompt", "自动互译", state)
state = r[-1] if r else state
check("关闭" in state.get("trans_note", ""), "翻译关闭时按钮给出提示且不联网")
r = call("guide_apply", "SD 1.5", state)
state = r[-1] if r else state
r = call("gm_change", 1.25, state)
state = r[-1] if r else state
check(abs(lib.settings["global_weight"] - 1.25) < 1e-6, "全局权重倍率即时生效")
r = call("do_export_page", state)
state = r[-1] if r else state
r = call("do_export_all", state)
state = r[-1] if r else state
r = call("tray_export", state)
state = r[-1] if r else state

# ---------------------------------------------------------------- 汇总
shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "=" * 60)
if errors:
    print("存在", len(errors), "个问题：")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("全部检查通过 ✅")
