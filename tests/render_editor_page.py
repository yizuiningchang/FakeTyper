"""M2 编辑页验证脚本。

验证项：
1. 模块导入；
2. EditorPage 独立构造 + 渲染（液态玻璃子组件取背景正常）；
3. load_new / load_preset 切换标题与初始内容；
4. 实时字符统计（字符数 / 行数 / 预估时长）；
5. dirty 检测：未修改 False、修改后 True、保存后 False；
6. Ctrl+S 快捷键已绑定；
7. 保存信号 saveRequested 携带 Preset；
8. 导入 .txt 文件（mock 文件对话框）；
9. 剪贴板粘贴；
10. 未保存确认条：点返回显示确认条 → 放弃 → cancelRequested；
11. 集成 MainWindow 的 push/pop 转场 + 保存持久化；
12. 集成 MainWindow 编辑现有预设 + 保存刷新引擎内容。

运行：``python tests/render_editor_page.py``
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QShortcut, QTextCursor
from PySide6.QtWidgets import QApplication

from facktyper.core.controller import EngineController
from facktyper.core.hotkey_manager import HotkeyManager
from facktyper.core.typing_engine import TypingEngine
from facktyper.data import preset_store
from facktyper.data.config import AppConfig
from facktyper.data.preset import Preset
from facktyper.ui.views.editor_page import EditorPage, _format_duration
from facktyper.ui.views.main_window import MainWindow
from facktyper.ui.widgets.engine_bridge import EngineBridge
from facktyper.ui.widgets.liquid_glass import GlassWindow, make_synthetic_backdrop


def _pump(app: QApplication, ms: int) -> None:
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def _assert_rendered(pm: QPixmap, name: str) -> None:
    assert not pm.isNull(), f"{name} 截图为空"
    img = pm.toImage()
    w, h = img.width(), img.height()
    non_empty = 0
    total = 0
    for y in range(0, h, max(1, h // 40)):
        for x in range(0, w, max(1, w // 40)):
            total += 1
            px = img.pixel(x, y)
            a = (px >> 24) & 0xFF
            v = ((px >> 16) & 0xFF) + ((px >> 8) & 0xFF) + (px & 0xFF)
            if a > 30 and v > 40:
                non_empty += 1
    ratio = non_empty / max(1, total)
    print(f"  {name}: 有效像素占比 {ratio:.0%}")
    assert ratio > 0.35, f"{name} 渲染异常：有效像素占比过低 ({ratio:.0%})"


def main() -> int:
    print("=" * 60)
    print("FakeTyper Pro M2 编辑页验证")
    print("=" * 60)

    def step(name: str, fn):
        print(f"\n[{name}] {fn.__doc__ or ''}")
        try:
            fn()
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            traceback.print_exc()
            raise

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. 导入
    def _step_import():
        """模块导入"""
        from facktyper.ui.views import EditorPage as _EP
        from facktyper.ui.views.editor_page import _format_duration as _fd
        print("  OK: EditorPage / _format_duration 已导入")
    step("1 导入", _step_import)

    # 2. 时长格式化
    def _step_fmt():
        """时长格式化"""
        assert _format_duration(0) == "< 1 秒"
        assert _format_duration(800) == "< 1 秒"
        assert _format_duration(5000) == "约 5 秒"
        assert _format_duration(90000) == "约 1 分 30 秒"
        assert _format_duration(3725000) == "约 1 时 02 分"
        print("  OK: _format_duration 各档位正确")
    step("2 时长格式化", _step_fmt)

    # 3. 独立构造 EditorPage
    host_holder: dict = {}
    editor_holder: dict = {}

    def _step_construct():
        """构造 EditorPage（玻璃宿主 + 合成背景）"""
        win = GlassWindow()
        win.resize(400, 620)
        win.set_synthetic_backdrop(make_synthetic_backdrop(win.size()))
        win.show()
        _pump(app, 200)
        editor = EditorPage(win)
        editor.setGeometry(0, 0, 400, 620)
        editor.show()
        _pump(app, 200)
        host_holder["win"] = win
        editor_holder["editor"] = editor
        print("  OK: EditorPage 已构造并显示")
    step("3 构造", _step_construct)
    editor: EditorPage = editor_holder["editor"]
    host_win: GlassWindow = host_holder["win"]

    # 4. load_new
    def _step_load_new():
        """新建模式"""
        editor.load_new(auto_speed_ms=1000)
        _pump(app, 100)
        assert editor._title_label.text() == "新建预设", f"标题异常: {editor._title_label.text()}"
        assert editor._title_field.text() == "", "新建标题应空"
        assert editor._editor.toPlainText() == "", "新建内容应空"
        assert not editor.is_dirty(), "新建初始应非 dirty"
        print("  OK: 新建模式 标题/内容/dirty 正确")
    step("4 新建模式", _step_load_new)

    # 5. 实时统计
    def _step_stats():
        """字符统计 + 预估时长"""
        editor.load_new(auto_speed_ms=1000)
        editor._editor.setPlainText("ab\ncd")
        _pump(app, 80)
        assert editor._stat_chars.text() == "字符 4", f"字符数异常: {editor._stat_chars.text()}"
        assert editor._stat_lines.text() == "行 2", f"行数异常: {editor._stat_lines.text()}"
        # total_chars=5 (a,b,\n,c,d) → 5*1000=5000ms → 约 5 秒
        assert editor._stat_duration.text() == "约 5 秒", f"时长异常: {editor._stat_duration.text()}"
        print(f"  OK: 统计 {editor._stat_chars.text()} / {editor._stat_lines.text()} / {editor._stat_duration.text()}")
    step("5 实时统计", _step_stats)

    # 6. dirty 检测
    def _step_dirty():
        """dirty 状态变化"""
        editor.load_new(auto_speed_ms=1000)
        assert not editor.is_dirty()
        editor._title_field.setText("新预设标题")
        assert editor.is_dirty(), "改标题后应 dirty"
        editor._editor.setPlainText("内容")
        assert editor.is_dirty(), "改内容后应 dirty"
        # 保存后 dirty 重置
        editor._on_save()
        assert not editor.is_dirty(), "保存后应非 dirty"
        print("  OK: dirty 检测 改前/改后/保存后 正确")
    step("6 dirty 检测", _step_dirty)

    # 7. Ctrl+S 绑定
    def _step_ctrls():
        """Ctrl+S 快捷键绑定"""
        scs = editor.findChildren(QShortcut)
        has = any(s.key().toString() == "Ctrl+S" for s in scs)
        assert has, "未绑定 Ctrl+S 快捷键"
        print(f"  OK: Ctrl+S 已绑定（共 {len(scs)} 个 QShortcut）")
    step("7 Ctrl+S", _step_ctrls)

    # 8. 保存信号
    def _step_save_signal():
        """saveRequested 携带 Preset"""
        editor.load_new(auto_speed_ms=1000)
        editor._title_field.setText("信号测试预设")
        editor._editor.setPlainText("信号内容")
        captured = []
        editor.saveRequested.connect(lambda p: captured.append(p))
        editor._on_save()
        _pump(app, 80)
        assert captured, "saveRequested 未发射"
        p = captured[0]
        assert p.title == "信号测试预设"
        assert p.content == "信号内容"
        # 空标题兜底
        editor.load_new(auto_speed_ms=1000)
        editor._editor.setPlainText("x")
        captured.clear()
        editor._on_save()
        _pump(app, 80)
        assert captured and captured[0].title == "未命名预设", "空标题未兜底"
        print("  OK: saveRequested 携带 Preset（含空标题兜底）")
    step("8 保存信号", _step_save_signal)

    # 9. 导入 .txt（mock 文件对话框）
    def _step_import():
        """从 .txt 导入（mock 对话框）"""
        import facktyper.ui.views.editor_page as ep
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write("导入的第一行\n第二行中文")
        tmp.close()
        try:
            orig = ep.QFileDialog.getOpenFileName
            ep.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (tmp.name, ""))  # type: ignore[assignment]
            editor.load_new(auto_speed_ms=1000)
            editor.on_import_file()
            _pump(app, 80)
            assert editor._editor.toPlainText() == "导入的第一行\n第二行中文", "导入内容异常"
            ep.QFileDialog.getOpenFileName = orig  # type: ignore[assignment]
            print("  OK: .txt 导入内容已替换编辑器")
        finally:
            os.unlink(tmp.name)
    step("9 导入 .txt", _step_import)

    # 10. 剪贴板粘贴
    def _step_paste():
        """剪贴板粘贴到光标处"""
        QApplication.clipboard().setText("剪贴板片段")
        editor.load_new(auto_speed_ms=1000)
        editor._editor.setPlainText("前缀|")
        # 把光标移到末尾
        cursor = editor._editor._edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        editor._editor._edit.setTextCursor(cursor)
        editor.on_paste_clipboard()
        _pump(app, 80)
        assert editor._editor.toPlainText() == "前缀|剪贴板片段", f"粘贴结果异常: {editor._editor.toPlainText()!r}"
        # 空剪贴板提示
        QApplication.clipboard().setText("")
        editor.on_paste_clipboard()
        _pump(app, 80)
        print("  OK: 剪贴板粘贴到光标处 + 空剪贴板分支")
    step("10 剪贴板粘贴", _step_paste)

    # 11. 未保存确认条
    def _step_dirty_bar():
        """未保存确认条：返回 → 确认条 → 放弃 → cancel"""
        editor.load_new(auto_speed_ms=1000)
        editor._editor.setPlainText("未保存内容")
        assert editor.is_dirty()
        # 点返回 → 应显示确认条（不直接 cancel）
        cancelled = []
        editor.cancelRequested.connect(lambda: cancelled.append(True))
        editor._back_btn.clicked.emit()
        _pump(app, 200)
        assert editor._dirty_bar.height() > 0, "确认条未滑入"
        assert not cancelled, "dirty 时点返回不应直接 cancel"
        # 点放弃
        editor._dirty_bar._discard_btn.clicked.emit()
        _pump(app, 200)
        assert cancelled, "放弃后未发射 cancelRequested"
        print("  OK: 确认条 → 放弃 → cancelRequested 正确")
    step("11 未保存确认条", _step_dirty_bar)

    # 12. 渲染验证
    def _step_render():
        """渲染截图"""
        editor.load_preset(Preset.create("渲染预设", "print('hello')\n# 中文注释"), auto_speed_ms=1000)
        _pump(app, 100)
        shot = editor.grab()
        _assert_rendered(shot, "EditorPage")
        out = ROOT / "tests" / "_editor_page_shot.png"
        shot.save(str(out))
        print(f"  截图已保存：{out}")
    step("12 渲染", _step_render)

    # 关闭独立宿主
    host_win.close()
    _pump(app, 100)

    # ---------------- 集成 MainWindow ----------------
    preset_store.ensure_default_preset()
    config = AppConfig.load()
    hotkey = HotkeyManager()
    engine = TypingEngine(hotkey)
    controller = EngineController(engine, hotkey, config)
    bridge = EngineBridge(engine)
    win_holder: dict = {}

    def _step_mw_construct():
        """构造 MainWindow"""
        w = MainWindow(engine, controller, config, bridge)
        w.set_synthetic_backdrop(make_synthetic_backdrop(w.size()))
        w.show()
        _pump(app, 600)
        win_holder["w"] = w
        print("  OK: MainWindow 已构造显示")
    step("13 MainWindow 构造", _step_mw_construct)
    mw: MainWindow = win_holder["w"]

    def _step_push_new():
        """push 新建预设页 + 转场"""
        mw._on_new_preset()
        _pump(app, 400)  # 转场 260ms + 余量
        assert mw._editor_page.isVisible(), "编辑页未显示"
        assert mw._main_page.isHidden(), "主页未隐藏"
        assert mw._editor_page._title_label.text() == "新建预设"
        print("  OK: push 转场完成，编辑页已在前")
    step("14 push 新建", _step_push_new)

    def _step_save_persist():
        """编辑页保存 → 持久化 + pop"""
        mw._editor_page._title_field.setText("持久化集成预设")
        mw._editor_page._editor.setPlainText("集成保存内容\n第二行")
        captured = []
        mw._editor_page.saveRequested.connect(lambda p: captured.append(p))
        mw._editor_page._on_save()
        _pump(app, 400)
        assert captured, "保存信号未发射"
        pid = captured[0].id
        got = preset_store.get_preset(pid)
        assert got is not None and got.content == "集成保存内容\n第二行", "持久化失败"
        assert mw._main_page.isVisible(), "保存后主页未恢复"
        assert mw._editor_page.isHidden(), "保存后编辑页未隐藏"
        # 列表已刷新且选中刚保存的
        assert mw._library._list._active_id == pid, "保存后未选中新预设"
        print(f"  OK: 保存持久化 + pop 回主页（预设 id={pid[:6]}）")
        # 清理
        preset_store.delete_preset(pid)
    step("15 保存持久化", _step_save_persist)

    def _step_edit_existing():
        """编辑现有预设 → 修改 → 保存 → 引擎内容刷新（含恢复原内容）"""
        controller.reload_presets()  # 步骤15删除测试预设后刷新，避免取到过期 id
        target = controller.presets[0]
        orig_content = target.content  # 备份，测试后恢复
        mw._on_preset_edit(target.id)
        _pump(app, 400)
        assert mw._editor_page.isVisible()
        assert mw._editor_page._title_field.text() == target.title, "编辑页未载入原标题"
        # 设为激活预设
        controller.set_active_preset(target.id)
        new_content = target.content + "\n# 编辑后追加"
        mw._editor_page._editor.setPlainText(new_content)
        mw._editor_page._on_save()
        _pump(app, 400)
        got = preset_store.get_preset(target.id)
        assert got is not None and got.content == new_content, "编辑现有未持久化"
        assert engine._title == target.title, "引擎内容未随保存刷新"
        print(f"  OK: 编辑现有预设 → 保存刷新引擎内容（{target.title}）")
        # 恢复原内容，避免污染真实预设
        target.content = orig_content
        preset_store.save_preset(target)
    step("16 编辑现有", _step_edit_existing)

    def _step_cancel_pop():
        """取消（无 dirty）→ 直接 pop"""
        controller.reload_presets()
        if controller.presets:
            mw._on_preset_edit(controller.presets[0].id)
            _pump(app, 400)
            # 不修改，直接返回
            mw._editor_page._back_btn.clicked.emit()
            _pump(app, 400)
            assert mw._main_page.isVisible(), "无 dirty 取消未 pop 回主页"
            assert mw._editor_page.isHidden()
            print("  OK: 无 dirty 取消直接 pop")
        else:
            print("  跳过：无预设")
    step("17 取消 pop", _step_cancel_pop)

    # 清理
    def _step_cleanup():
        """清理 + 关闭"""
        bridge.detach()
        mw.close()
        _pump(app, 200)
        print("  OK: MainWindow 已关闭")
    step("18 清理", _step_cleanup)

    print("\n" + "=" * 60)
    print("✓ M2 编辑页验证全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
