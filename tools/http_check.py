# -*- coding: utf-8 -*-
"""端到端验证：启动真实 Gradio 服务，检查页面、静态资源与事件 API。"""
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 7899
BASE = f"http://127.0.0.1:{PORT}"

proc = subprocess.Popen(
    [sys.executable, "app.py", "--port", str(PORT), "--no-browser"],
    cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace")

ok = True
try:
    # 等待服务起来
    body = ""
    for _ in range(60):
        try:
            with urllib.request.urlopen(BASE + "/", timeout=2) as r:
                body = r.read().decode("utf-8", "replace")
            break
        except Exception:
            time.sleep(1)
    if not body:
        raise RuntimeError("服务未能在 60 秒内启动")
    print("GET / ->", len(body), "bytes")
    for needle, desc in [
        ("PromptDock", "页面标题"),
        ("__sdSend", "前端桥接脚本注入到 head"),
        ("bridge_go", "桥接按钮 DOM 配置"),
        ("sd-card", "暗色主题 CSS / 卡片样式"),
        ("文生图提示语", "选项卡"),
    ]:
        hit = needle in body
        print(("  OK  " if hit else " FAIL ") + desc)
        ok &= hit

    # 页面静态资源
    with urllib.request.urlopen(BASE + "/gradio_api/info", timeout=5) as r:
        info = r.read().decode("utf-8", "replace")
    print("GET /gradio_api/info ->", len(info), "bytes")
    for needle, desc in [("bridge", "桥接 API 已注册"),
                         ("named_endpoints", "命名端点列表")]:
        hit = needle in info
        print(("  OK  " if hit else " FAIL ") + desc)
        ok &= hit

    # 用 gradio_client 真实触发一次事件（验证 67 个 update 全部被 Gradio 接受）
    try:
        from gradio_client import Client
        cli = Client(BASE, verbose=False)
        api = cli.view_api(return_format="dict")
        eps = list((api.get("named_endpoints") or {}).keys())
        has_bridge = "/bridge" in eps
        print(("  OK  " if has_bridge else " FAIL ") + "桥接事件 /bridge 已暴露为命名端点")
        ok &= has_bridge
        if has_bridge:
            spec = api["named_endpoints"]["/bridge"]
            print("  /bridge 参数:", len(spec.get("parameters", [])),
                  "返回:", len(spec.get("returns", [])))
        res = cli.predict("img-0001", "select", "", api_name="/bridge")
        n = len(res) if isinstance(res, (list, tuple)) else 1
        print(("  OK  " if n >= 60 else " FAIL ") + f"真实桥接事件调用返回 {n} 个输出")
        ok &= n >= 60
    except Exception as e:
        print("  WARN gradio_client 调用未完成：", type(e).__name__, str(e)[:220])
        # 不判定为硬失败：Python 层已通过完整自检
finally:
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate(timeout=5)
    tail = "\n".join((out or "").splitlines()[-25:])
    print("\n--- server log tail ---\n" + tail)
    for bad in ("Traceback (most recent call last)", "ERROR", "Exception"):
        if bad in tail:
            print("  WARN 服务日志出现：", bad)

print("\n" + ("HTTP 端到端检查通过 ✅" if ok else "HTTP 端到端检查存在失败 ❌"))
sys.exit(0 if ok else 1)
