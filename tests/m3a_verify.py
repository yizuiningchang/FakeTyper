"""M3-a 系统集成后端验证：单实例 / 开机自启 / 托盘图标 / config 新字段。

注意：autostart 会真实读写注册表 HKCU\\...\\Run，测试前后会保存并还原原状态。
单实例在进程内创建两个守卫验证互斥体语义。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    print("=" * 60)
    print("M3-a 系统集成后端验证")
    print("=" * 60)

    # 1. 单实例命名互斥体
    print("\n[1] 单实例命名互斥体")
    from facktyper.core.single_instance import SingleInstance

    s1 = SingleInstance()
    a1 = s1.acquire()
    s2 = SingleInstance()
    a2 = s2.acquire()
    print(f"  首实例 acquire={a1} (期望 True)")
    print(f"  次实例 acquire={a2} (期望 False)")
    assert a1 is True, "首实例应获得互斥体"
    assert a2 is False, "次实例应检测到已存在实例"
    s1.release()
    s2.release()
    # release 后应可再次获得（句柄已关闭）
    s3 = SingleInstance()
    a3 = s3.acquire()
    print(f"  release 后再 acquire={a3} (期望 True)")
    assert a3 is True, "release 后应可重新获得"
    s3.release()
    print("  OK")

    # 2. 开机自启注册表读写（含原状态还原）
    print("\n[2] 开机自启注册表读写")
    from facktyper.core import autostart

    orig = autostart.is_autostart_enabled()
    print(f"  原状态: {orig}")
    try:
        assert autostart.enable_autostart() is True, "enable 应成功"
        cur = autostart.is_autostart_enabled()
        print(f"  enable 后: {cur} (期望 True)")
        assert cur is True, "enable 后应 True"
        assert autostart.disable_autostart() is True, "disable 应成功"
        cur2 = autostart.is_autostart_enabled()
        print(f"  disable 后: {cur2} (期望 False)")
        assert cur2 is False, "disable 后应 False"
        # sync_to_registry 双向
        assert autostart.sync_to_registry(True) is True
        assert autostart.is_autostart_enabled() is True
        assert autostart.sync_to_registry(False) is True
        assert autostart.is_autostart_enabled() is False
    finally:
        autostart.sync_to_registry(orig)
        print(f"  已还原原状态: {orig}")
    print("  OK")

    # 3. 托盘图标自绘
    print("\n[3] 托盘图标 TrayIconPainter")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    from facktyper.ui.widgets.tray_backend import TrayIconPainter, TrayIconState

    states = [
        ("激活+auto", TrayIconState(master_on=True, engine_mode="auto", preset_title="示例")),
        ("关闭+idle", TrayIconState(master_on=False, engine_mode="idle", preset_title="")),
        ("激活+key", TrayIconState(master_on=True, engine_mode="key", preset_title="测试")),
    ]
    for label, st in states:
        pm = TrayIconPainter.render(st, 32)
        print(f"  [{label}] -> {pm.width()}x{pm.height()} isNull={pm.isNull()}")
        assert not pm.isNull() and pm.width() == 32 and pm.height() == 32, f"{label} 渲染异常"
    # 多尺寸
    for sz in (16, 22, 32, 48):
        pm = TrayIconPainter.render(states[0][1], sz)
        assert pm.width() == sz and not pm.isNull(), f"尺寸 {sz} 异常"
    print(f"  多尺寸(16/22/32/48) 全部 OK")
    # 保存预览供人工核对
    out = os.path.join(os.path.dirname(__file__), "_m3a_tray_preview.png")
    TrayIconPainter.render(TrayIconState(True, "auto", ""), 64).save(out)
    print(f"  预览已保存: {out}")
    print("  OK")

    # 4. config 新字段 + 旧字段迁移
    print("\n[4] config 新字段与旧字段迁移")
    from facktyper.data.config import AppConfig

    # 默认值
    c = AppConfig()
    c._normalize()
    assert c.startup_window_state == "minimized", c.startup_window_state
    assert c.close_behavior == "tray", c.close_behavior
    assert c.startup_minimized is True and c.close_to_tray is True
    assert c.close_to_tray_first_prompted is False
    # 旧字段 → 新字段迁移
    c2 = AppConfig()
    c2.startup_minimized = False
    c2.close_to_tray = False
    c2._normalize()
    assert c2.startup_window_state == "normal", c2.startup_window_state
    assert c2.close_behavior == "quit", c2.close_behavior
    # 新字段 → 旧字段反向同步
    c3 = AppConfig()
    c3.startup_window_state = "maximized"
    c3.close_behavior = "quit"
    c3._normalize()
    assert c3.startup_minimized is False
    assert c3.close_to_tray is False
    # 非法值回退默认
    c4 = AppConfig()
    c4.startup_window_state = "weird"
    c4.close_behavior = "xxx"
    c4._normalize()
    assert c4.startup_window_state == "minimized"
    assert c4.close_behavior == "tray"
    print("  OK: 默认/迁移/反向同步/非法回退 全部正确")

    print("\n" + "=" * 60)
    print("✓ M3-a 系统集成后端验证全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
