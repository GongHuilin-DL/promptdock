# -*- coding: utf-8 -*-
"""把提示语渲染成暗色卡片（沿用离线 HTML 版的视觉语言），并注入前端交互脚本。

前端只负责：权重滑块实时改写、一键复制、点击按钮把 (id, 动作, 文本) 送回 Gradio。
所有持久化、筛选、分页、翻译都交给 Python，避免前后端状态不一致。
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Tuple

from .syntax import Profile, fmt, get_profile, tokenize

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


# ------------------------------------------------------------------ 提示词高亮
def _token_text(t, value: float) -> str:
    if t.type == "lora":
        return f"<lora:{t.word}:{fmt(value)}>"
    return t.tpl.replace("{w}", t.word).replace("{v}", fmt(value))


def render_prompt(it: Dict[str, Any], profile: Profile, global_mul: float,
                  subw: float = 1.0) -> Tuple[str, List[Any]]:
    p = str(it.get("prompt", ""))
    toks = tokenize(p, profile)
    out, cur = [], 0
    for i, t in enumerate(toks):
        out.append(E(p[cur:t.start]))
        v = t.value * global_mul if t.type == "w" else t.value
        attrs = (f'class="sd-w" data-wi="{i}" data-type="{t.type}" '
                 f'data-tpl="{E(t.tpl)}" data-word="{E(t.word)}" '
                 f'data-base="{t.value}" data-mul="{global_mul}"')
        out.append(f"<span {attrs}>{E(_token_text(t, v))}</span>")
        cur = t.end
    out.append(E(p[cur:]))
    body = "".join(out)

    subject = str(it.get("subject") or "").strip()
    prefix = ""
    if profile.allow_prefix and subject:
        pv = fmt(subw)
        shown = f"({E(subject)}:{pv}), " if abs(subw - 1.0) > 1e-6 else ""
        prefix = (f'<span class="sd-prefix" data-subject="{E(subject)}" '
                  f'data-subw="{subw}">{shown}</span>')
    return prefix + body, toks


def render_sliders(it: Dict[str, Any], toks: List[Any], profile: Profile,
                   global_mul: float, subw: float) -> str:
    rows = []
    if profile.allow_prefix and str(it.get("subject") or "").strip():
        s = str(it["subject"])[:26]
        rows.append(
            '<div class="sd-sl sd-sl-sub"><span class="sd-sl-lab" title="主体前置权重">'
            f'主体 → {E(s)}</span>'
            f'<input type="range" class="sd-subw" min="0.5" max="1.8" step="0.05" value="{subw}">'
            f'<span class="sd-val" data-sub="1">{fmt(subw)}</span></div>')
    for i, t in enumerate(toks):
        if t.type == "step":
            lo, hi, step = 0, 1, 0.05
        elif t.type == "lora":
            lo, hi, step = 0, 1.5, 0.05
        else:
            lo, hi, step = 0.1, max(2.0, round(t.value * 1.6, 1)), 0.05
        label = {"lora": "lora:" + t.word, "step": "切换步 " + t.word + "→…",
                 "w": t.word}.get(t.type, t.word)[:34]
        shown = fmt(t.value) + (f" → {fmt(t.value * global_mul)}"
                               if t.type == "w" and abs(global_mul - 1) > 1e-6 else "")
        rows.append(
            '<div class="sd-sl"><span class="sd-sl-lab" title="' + E(t.raw) + '">' + E(label) + '</span>'
            f'<input type="range" class="sd-wr" data-wi="{i}" min="{lo}" max="{hi}" '
            f'step="{step}" value="{t.value}">'
            f'<span class="sd-val" data-vi="{i}">{shown}</span></div>')
    if not rows:
        rows.append('<div class="sd-sl"><span class="sd-sl-lab">该模型语法不使用数值权重；'
                    '可用上方「主体前置权重」或切换到其它权重语法</span><span></span><span></span></div>')
    return ('<div class="sd-sliders"><div class="sd-sl-title">权重可视化滑块 · 拖动即时改写提示词</div>'
            + "".join(rows) + "</div>")


def render_cards(items: List[Dict[str, Any]], *, settings: Dict[str, Any],
                 state: Dict[str, Any], tab: str, empty: str = "没有匹配的提示语") -> str:
    if not items:
        return f'<div class="sd-empty">{E(empty)}<br><span>换个筛选条件，或点「重新扫描并读取」。</span></div>'
    gm = float(settings.get("global_weight", 1.0))
    custom_tpl = str(settings.get("custom_tpl", "({w}:{v})"))
    default_key = str(settings.get("syntax_profile", "sd"))
    ui_state = state.get("weights", {})
    cards = []
    for it in items:
        key = str(it.get("syntax") or "").strip() or default_key
        prof = get_profile(key, custom_tpl)
        wst = ui_state.get(it["id"], {})
        subw = float(wst.get("subw", 1.0))
        prompt_html, toks = render_prompt(it, prof, gm, subw)
        # 应用该条已保存的单块权重覆盖
        overrides = wst.get("w", {})
        if overrides:
            prompt_html = _apply_overrides_html(prompt_html, toks, overrides, prof, gm)
        liked, fav = bool(it.get("like")), bool(it.get("favorite"))
        tags = (it.get("tags") or [])[:4]
        tag_html = "".join(f'<span class="sd-badge">{E(t)}</span>' for t in tags)
        video_meta = ""
        if it.get("kind") == "video":
            bits = [str(it.get(k, "")).strip() for k in ("camera", "duration", "motion", "fps")]
            bits = [b for b in bits if b]
            if bits:
                video_meta = '<div class="sd-meta">🎬 ' + E(" · ".join(bits)) + "</div>"
        neg = str(it.get("negative") or "").strip()
        neg_html = (f'<details class="sd-neg"><summary>负面 / 负向提示词</summary>'
                    f'<div class="sd-neg-body">{E(neg)}</div></details>') if neg else ""
        cards.append(f"""
<div class="sd-card" data-sdid="{E(it['id'])}" data-tab="{E(tab)}">
  <div class="sd-chead">
    <span class="sd-num">#{E(str(it['id'])[:14])}</span>
    <span class="sd-badge sd-badge-cat">{E(it['category'])}</span>
    <span class="sd-badge sd-badge-tech">{E(it.get('tech') or '自定义')}</span>
    <span class="sd-badge">{E(it.get('model') or '通用')}</span>
    <span class="sd-spacer"></span>
    <button type="button" class="sd-icon {'on' if liked else ''}" data-sdact="like" title="喜欢 / 取消喜欢">{'♥' if liked else '♡'}</button>
    <button type="button" class="sd-icon {'on' if fav else ''}" data-sdact="fav" title="收藏 / 取消收藏">{'★' if fav else '☆'}</button>
  </div>
  <div class="sd-prompt">{prompt_html}</div>
  {video_meta}
  {render_sliders(it, toks, prof, gm, subw)}
  {neg_html}
  <div class="sd-tip">💡 {E(it.get('tip') or '自定义提示语，可在右侧编辑面板补充技巧说明。')}</div>
  <div class="sd-cfoot">
    <button type="button" class="sd-btn sd-btn-p" data-sdact="copy">📋 复制</button>
    <button type="button" class="sd-btn" data-sdact="tray">＋ 拼装台</button>
    <button type="button" class="sd-btn" data-sdact="edit">✏️ 编辑</button>
    <button type="button" class="sd-btn" data-sdact="translate">🌐 翻译</button>
    <button type="button" class="sd-btn" data-sdact="saveweight" title="把滑块调整后的文本保存回本地数据文件">💾 存权重</button>
    <button type="button" class="sd-btn" data-sdact="resetweight" title="恢复该条的默认权重显示">♻️ 重置</button>
    <button type="button" class="sd-btn sd-btn-danger" data-sdact="delete">🗑 删除</button>
    {tag_html}
  </div>
</div>""")
    return '<div class="sd-grid">' + "".join(cards) + "</div>"


def _apply_overrides_html(prompt_html: str, toks: List[Any], overrides: Dict[str, float],
                          prof: Profile, gm: float) -> str:
    """把用户保存过的滑块值回填到卡片 HTML（简单的 span 文本替换）。"""
    for i, t in enumerate(toks):
        if str(i) not in overrides:
            continue
        v = float(overrides[str(i)]) * gm if t.type == "w" else float(overrides[str(i)])
        txt = E(_token_text(t, v))
        prompt_html = re.sub(
            r'(<span class="sd-w" data-wi="' + str(i) + r'"[^>]*>).*?(</span>)',
            lambda m: m.group(1) + txt + m.group(2), prompt_html, count=1, flags=re.S)
    return prompt_html


# ------------------------------------------------------------------ 其它区域
def render_stats(lib, state: Dict[str, Any]) -> str:
    s = lib.stats()
    cells = [("提示语总数", s["total"], "条"), ("文生图", s["image"], "条"),
             ("文生视频", s["video"], "条"), ("喜欢 ♥", s["like"], "条"),
             ("收藏 ★", s["favorite"], "条"), ("类别", s["categories"], "个"),
             ("数据文件", s["files"], "个")]
    out = "".join(f'<div class="sd-stat"><b>{v}</b><small>{E(k)} · {unit}</small></div>'
                  for k, v, unit in cells)
    return f'<div class="sd-stats">{out}</div>'


def render_tray(state: Dict[str, Any]) -> str:
    tray = state.get("tray", [])
    if not tray:
        return '<div class="sd-tray-empty">拼装台是空的。点卡片上的「＋ 拼装台」，把当前权重版本的提示词加进来。</div>'
    rows = []
    for i, t in enumerate(tray):
        rows.append(f'<div class="sd-tray-item"><span class="sd-tray-n">{i+1}</span>'
                    f'<span class="sd-tray-t">{E(str(t.get("text",""))[:150])}</span>'
                    f'<button type="button" class="sd-x" data-sdact="tray_del" '
                    f'data-sdpayload="{i}" title="移除">✕</button></div>')
    return "".join(rows)


def render_sources(lib, selected: str = "") -> str:
    rows = lib.source_rows()
    if not rows:
        return '<div class="sd-empty">还没有数据文件。在下方「新建数据文件」创建一个，或把 .json / .jsonl / .csv / .txt / .db 放进 data/prompts/ 后重新扫描。</div>'
    out = []
    for r in rows:
        err = (f'<span class="sd-err">⚠️ {E(r["error"])}</span>') if r["error"] else '<span class="sd-ok">✓ 正常</span>'
        sel = " selected" if r["rel"] == selected else ""
        size = f"{r['size']/1024:.1f} KB" if r["size"] < 1024 * 1024 else f"{r['size']/1024/1024:.1f} MB"
        out.append(f"""
<tr class="sd-row{E(sel)}">
  <td><b>{E(r['rel'])}</b><div class="sd-mini">{E(r['path'])}</div></td>
  <td><span class="sd-badge">{E(r['fmt'].upper())}</span></td>
  <td>{r['count']}</td><td>{size}</td><td>{E(r['default_kind'])}</td><td>{err}</td>
  <td class="sd-row-btns">
    <button type="button" class="sd-btn" data-sdact="file_raw" data-sdpayload="{E(r['rel'])}">查看 / 编辑</button>
    <button type="button" class="sd-btn sd-btn-danger" data-sdact="file_delete" data-sdpayload="{E(r['rel'])}">删除</button>
  </td>
</tr>""")
    return ("<table class='cheat sd-files'><thead><tr><th>文件（相对 data/）</th><th>格式</th>"
            "<th>条数</th><th>大小</th><th>缺省类型</th><th>状态</th><th>操作</th></tr></thead><tbody>"
            + "".join(out) + "</tbody></table>")


def render_categories(lib, selected: str = "") -> str:
    counts = lib.category_counts()
    rows = []
    for c in sorted(lib.categories, key=lambda x: (-counts.get(x["name"], 0), x["name"])):
        n = counts.get(c["name"], 0)
        rows.append(f"""
<tr>
  <td><b>{E(c['name'])}</b></td><td>{E(c.get('kind','both'))}</td><td>{n}</td>
  <td class="sd-mini">{E(c.get('note',''))}</td>
  <td class="sd-row-btns">
    <button type="button" class="sd-btn" data-sdact="cat_pick" data-sdpayload="{E(c['name'])}">选中</button>
    <button type="button" class="sd-btn" data-sdact="cat_rename_req" data-sdpayload="{E(c['name'])}">改名</button>
    <button type="button" class="sd-btn sd-btn-danger" data-sdact="cat_delete" data-sdpayload="{E(c['name'])}">删除类别</button>
  </td>
</tr>""")
    return ("<table class='cheat'><thead><tr><th>类别名（全局唯一）</th><th>适用</th>"
            "<th>提示语条数</th><th>备注</th><th>操作</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def confirm_text(state: Dict[str, Any]) -> str:
    p = state.get("pending") or {}
    return p.get("message", "确认要执行这个操作吗？此操作不可撤销。")


# ------------------------------------------------------------------ 前端脚本
BRIDGE_JS = r"""
<script>
(function(){
  'use strict';
  function setVal(id, val){
    var box = document.getElementById(id);
    if(!box) return;
    var el = box.tagName === 'TEXTAREA' || box.tagName === 'INPUT' ? box : box.querySelector('textarea,input');
    if(!el) return;
    var proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    try { Object.getOwnPropertyDescriptor(proto,'value').set.call(el, String(val)); } catch(e){ el.value = String(val); }
    el.dispatchEvent(new Event('input',  {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  window.__sdSend = function(id, act, payload){
    setVal('bridge_id', id || '');
    setVal('bridge_action', act || '');
    setVal('bridge_payload', payload == null ? '' : payload);
    var g = document.getElementById('bridge_go');
    if(!g) { console.warn('[SD] bridge button missing'); return; }
    var btn = g.tagName === 'BUTTON' ? g : g.querySelector('button');
    if(btn) btn.click();
  };
  function toast(msg){
    var t = document.getElementById('sd-toast');
    if(!t){ t = document.createElement('div'); t.id='sd-toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._t); t._t = setTimeout(function(){ t.classList.remove('show'); }, 1600);
  }
  window.__sdToast = toast;
  function copyText(txt){
    if(navigator.clipboard && window.isSecureContext){
      navigator.clipboard.writeText(txt).then(function(){toast('已复制到剪贴板');}, fallback);
    } else fallback();
    function fallback(){
      var ta=document.createElement('textarea'); ta.value=txt;
      ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta);
      ta.select(); try{ document.execCommand('copy'); toast('已复制到剪贴板'); }
      catch(e){ toast('复制失败，请手动选择文本'); } document.body.removeChild(ta);
    }
  }
  function currentPrompt(card){
    return (card.querySelector('.sd-prompt') || {}).textContent || '';
  }
  function fmt(v){ return String(Math.round(parseFloat(v)*100)/100); }

  document.addEventListener('click', function(ev){
    var b = ev.target.closest('[data-sdact]'); if(!b) return;
    ev.preventDefault(); ev.stopPropagation();
    var act = b.getAttribute('data-sdact');
    var card = b.closest('[data-sdid]');
    var id = card ? card.getAttribute('data-sdid') : '';
    var payload = b.getAttribute('data-sdpayload');
    if(payload == null){
      if(act === 'copy' || act === 'tray' || act === 'translate' || act === 'edit' || act === 'saveweight'){
        payload = currentPrompt(card);
      } else payload = '';
    }
    if(act === 'copy'){ copyText(payload); return; }
    // 纯前端即时反馈
    if(act === 'like' || act === 'fav'){
      var on = !b.classList.contains('on');
      b.classList.toggle('on', on);
      b.textContent = act === 'like' ? (on ? '♥' : '♡') : (on ? '★' : '☆');
    }
    window.__sdSend(id, act, payload);
  });

  document.addEventListener('input', function(ev){
    var el = ev.target;
    if(!el || el.type !== 'range') return;
    var card = el.closest('.sd-card'); if(!card) return;
    if(el.classList.contains('sd-subw')){
      var sp = card.querySelector('.sd-prefix');
      var v = parseFloat(el.value);
      if(sp){
        var s = sp.getAttribute('data-subject');
        sp.textContent = Math.abs(v-1) < 0.0001 ? '' : '('+s+':'+fmt(v)+'), ';
      }
      var lab = card.querySelector('[data-sub]'); if(lab) lab.textContent = fmt(v);
      return;
    }
    var i = el.getAttribute('data-wi');
    var span = card.querySelector('.sd-w[data-wi="'+i+'"]');
    var lab  = card.querySelector('[data-vi="'+i+'"]');
    if(!span) return;
    var v = parseFloat(el.value), base = parseFloat(span.getAttribute('data-base')) || 1;
    var mul = parseFloat(span.getAttribute('data-mul')) || 1;
    var type = span.getAttribute('data-type');
    var word = span.getAttribute('data-word');
    var tpl = span.getAttribute('data-tpl');
    var shown = type === 'w' ? v*mul : v;
    var txt;
    if(type === 'lora') txt = '<lora:'+word+':'+fmt(v)+'>';
    else txt = tpl.replace('{w}', word).replace('{v}', fmt(shown));
    span.textContent = txt;
    if(lab) lab.textContent = fmt(v) + (type === 'w' && Math.abs(mul-1)>0.0001 ? ' → '+fmt(shown) : '');
  });
  window.__sdCopy = copyText;
})();
</script>
"""
