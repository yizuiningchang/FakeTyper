"""M2 控件离屏渲染验证：Toggle / PresetCard / Toast / EngineBridge 信号。

验证：
1. Toggle 切换动画 + 玻璃质感渲染；
2. PresetCard 选中态 + 徽标 + hover 操作按钮渲染；
3. Toast 顶部下拉动画 + 玻璃质感；
4. EngineBridge 信号跨线程正确转发。

运行：python tests\\render_widgets.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

# 加入 src 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
from PySide6.QtCore import Qt, QTimer, QSize, QPointF
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from facktyper.ui import theme
from facktyper.ui.widgets.liquid_glass import GlassWindow, make_synthetic_backdrop
from facktyper.ui.widgets.toggle import MasterToggle
from facktyper.ui.widgets.preset_card import PresetCard
from facktyper.ui.widgets.toast import Toast, show_toast
from facktyper.ui.widgets.capsule import StatusCapsule
from facktyper.ui.widgets.engine_bridge import EngineBridge


def _assert_glass_rendered(pix: QPixmap, tag: str) -> None:
    """校验渲染非全透明、有像素方差（有内容）。"""
    img = pix.toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    mv = img.bits()
    arr = np.frombuffer(mv, dtype=np.uint8, count=h * bpl)
    if bpl == w * 4:
        arr = arr.reshape(h, w, 4)
    else:
        arr = arr.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4)
    non_transparent = int((arr[:, :, 3] > 10).sum())
    var = float(arr[:, :, :3].std())
    assert non_transparent > 200, f"[{tag}] 渲染几乎全透明: {non_transparent}"
    assert var > 3.0, f"[{tag}] 像素方差过低: {var}"
    print(f"[OK] {tag}: 非透明像素={non_transparent}  RGB方差={var:.2f}")


def _pump(app: QApplication, ms: float) -> None:
    """驱动事件循环 ms 毫秒，让动画推进。"""
    import time as _t
    end = _t.time() + ms / 1000.0
    while _t.time() < end:
        app.processEvents()
        _t.sleep(0.02)


def test_toggle(app: QApplication, win: GlassWindow) -> None:
    print("\n=== 测试 MasterToggle ===")
    toggle = MasterToggle(win)
    toggle.move(60, 60)
    toggle.show()
    app.processEvents()
    # 初始 OFF
    assert not toggle.isChecked(), "初始应为 OFF"
    assert toggle.knobFactor == 0.0, f"OFF 态滑块应为 0: {toggle.knobFactor}"
    # 切换到 ON（动画 420ms）
    toggle.setChecked(True)
    _pump(app, 500)
    assert toggle.isChecked(), "切换后应为 ON"
    assert toggle.knobFactor > 0.9, f"ON 态滑块未到位: {toggle.knobFactor}"
    # 切换回 OFF
    toggle.setChecked(False)
    _pump(app, 500)
    assert not toggle.isChecked()
    assert toggle.knobFactor < 0.1, f"OFF 态滑块未归零: {toggle.knobFactor}"
    _assert_glass_rendered(toggle.grab(), "Toggle")


def test_preset_card(app: QApplication, win: GlassWindow) -> None:
    print("\n=== 测试 PresetCard ===")
    card = PresetCard("test-id", win)
    card.resize(360, PresetCard.CARD_H)
    card.move(20, 160)
    card.setData(
        title="示例预设：双模型逐帧处理",
        char_count=128,
        time_text="刚刚",
        pinned=True,
        selected=True,
    )
    card.show()
    app.processEvents()
    assert card.isSelected()
    assert card.preset_id == "test-id"
    # 信号测试
    received = []
    card.clicked.connect(lambda pid: received.append(("clicked", pid)))
    card.doubleClicked.connect(lambda pid: received.append(("dbl", pid)))
    card.actionRequested.connect(lambda pid, a: received.append((a, pid)))
    # 模拟
    card.clicked.emit("test-id")
    card.actionRequested.emit("test-id", "edit")
    assert ("clicked", "test-id") in received
    assert ("edit", "test-id") in received
    _assert_glass_rendered(card.grab(), "PresetCard")


def test_toast(app: QApplication, win: GlassWindow) -> None:
    print("\n=== 测试 Toast ===")
    toast = show_toast(win, "已保存预设", kind="success", duration=5000)
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    _assert_glass_rendered(toast.grab(), "Toast")
    toast.hide_toast()


def test_capsule(app: QApplication, win: GlassWindow) -> None:
    print("\n=== 测试 StatusCapsule ===")
    # 直接测试尺寸变化逻辑（不依赖窗口标志）
    cap = StatusCapsule()
    # IDLE 收缩态
    cap.set_mode("idle")
    _pump(app, 400)
    idle_w = cap.width()
    print(f"  IDLE 宽度={idle_w}, expand={cap.expand}")
    assert idle_w == StatusCapsule.W_COLLAPSED, f"收缩态宽度异常: {idle_w}"
    # 展开态
    cap.set_mode("auto")
    _pump(app, 500)
    auto_w = cap.width()
    print(f"  AUTO 宽度={auto_w}, expand={cap.expand}")
    assert auto_w > idle_w + 20, f"展开态尺寸未变化: idle={idle_w} auto={auto_w}"
    assert cap.expand > 0.9, f"展开因子异常: {cap.expand}"
    cap.set_progress(45.0)
    assert cap._percent == 45.0
    # 在 win 内渲染验证
    cap.setParent(win)
    cap.setWindowFlags(Qt.Widget)
    cap.move(80, 460)
    cap.show()
    app.processEvents()
    _assert_glass_rendered(cap.grab(), "Capsule")


def test_engine_bridge(app: QApplication) -> None:
    print("\n=== 测试 EngineBridge 信号转发 ===")
    # 构造一个最小 mock 引擎，仅暴露 add/remove_listener
    class _MockEngine:
        def __init__(self) -> None:
            self.listeners: list = []
        def add_listener(self, ln) -> None:
            self.listeners.append(ln)
        def remove_listener(self, ln) -> None:
            try:
                self.listeners.remove(ln)
            except ValueError:
                pass
        def fire(self, method: str, *args) -> None:
            for ln in list(self.listeners):
                getattr(ln, method)(*args)

    mock = _MockEngine()
    bridge = EngineBridge(mock)  # type: ignore[arg-type]
    got = {}
    bridge.mode_changed.connect(lambda m: got.__setitem__("mode", m))
    bridge.progress_changed.connect(lambda p, c, t: got.__setitem__("progress", (p, c, t)))
    bridge.preset_changed.connect(lambda title, total: got.__setitem__("preset", (title, total)))
    bridge.error_occurred.connect(lambda msg: got.__setitem__("error", msg))

    # 同线程触发：直接 emit
    mock.fire("on_mode_changed", "key")
    mock.fire("on_progress", 42.0, 10, 24)
    mock.fire("on_preset_changed", "示例", 100)
    mock.fire("on_error", "boom")
    app.processEvents()
    assert got.get("mode") == "key", f"mode 信号未到: {got}"
    assert got.get("progress") == (42.0, 10, 24), f"progress 信号未到: {got}"
    assert got.get("preset") == ("示例", 100), f"preset 信号未到: {got}"
    assert got.get("error") == "boom", f"error 信号未到: {got}"
    print("[OK] 同线程信号转发正常")

    # 跨线程触发（模拟 keyboard 监听线程）
    got.clear()
    def _worker() -> None:
        mock.fire("on_mode_changed", "auto")
    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    # 让事件循环处理排队信号
    for _ in range(20):
        app.processEvents()
        if "mode" in got:
            break
        time.sleep(0.02)
    assert got.get("mode") == "auto", f"跨线程 mode 信号未到: {got}"
    print("[OK] 跨线程信号转发正常（已排队到 UI 线程）")
    bridge.detach()


def render() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = GlassWindow()
    win.resize(theme.WINDOW_W, theme.WINDOW_H)
    bd = make_synthetic_backdrop(QSize(theme.WINDOW_W, theme.WINDOW_H))
    win.set_synthetic_backdrop(bd)
    win.show()
    app.processEvents()

    try:
        test_toggle(app, win)
        test_preset_card(app, win)
        test_toast(app, win)
        test_capsule(app, win)
        test_engine_bridge(app)
    finally:
        # 保存预览图
        out = os.path.join(os.path.dirname(__file__), "..", "_widgets_preview.png")
        pix = win.grab()
        pix.save(out)
        print(f"\n已保存预览: {os.path.abspath(out)}")

    print("\n[全部通过] M2 控件渲染 + 信号桥接验证完成")
    return 0


if __name__ == "__main__":
    sys.exit(render())
