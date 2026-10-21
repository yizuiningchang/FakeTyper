"""M3-d 主题运行时切换验证脚本。

验证项：
1. ThemeManager 单例：set_theme / current_palette / themeChanged 信号；
2. dark ↔ light ↔ system 三种模式切换 + resolved 解析正确；
3. 系统明暗状态变化（system 模式下跟随）；
4. paintEvent 控件在主题切换后刷新（GlassContainer/GlassButton 染色变化）；
5. AppearancePane 分段切换 → 实时 set_theme + config 写回；
6. 截图对比：dark vs light 主题下同一控件的像素差异（验证确实刷新）。

运行：``python tests/m3d_verify.py``
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import faulthandler  # noqa: E402
_fault_log = open(str(Path(__file__).parent / "_m3d_fault.log"), "w")
faulthandler.enable(file=_fault_log, all_threads=True)

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from facktyper.data.config import AppConfig  # noqa: E402
from facktyper.ui import theme  # noqa: E402
from facktyper.ui.widgets.liquid_glass import (  # noqa: E402
    GlassContainer,
    GlassWindow,
    make_synthetic_backdrop,
)
from facktyper.ui.widgets.glass_button import GlassButton  # noqa: E402


def _pump(app: QApplication, ms: int) -> None:
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def _avg_color(pm: QPixmap) -> tuple[int, int, int]:
    """取截图的平均 RGB（忽略透明像素）。"""
    img = pm.toImage()
    r = g = b = n = 0
    for y in range(0, img.height(), max(1, img.height() // 30)):
        for x in range(0, img.width(), max(1, img.width() // 30)):
            px = img.pixel(x, y)
            a = (px >> 24) & 0xFF
            if a < 30:
                continue
            r += (px >> 16) & 0xFF
            g += (px >> 8) & 0xFF
            b += px & 0xFF
            n += 1
    if n == 0:
        return (0, 0, 0)
    return (r // n, g // n, b // n)


def main() -> int:
    print("=" * 60)
    print("FakeTyper Pro M3-d 主题运行时切换验证")
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

    # 1. ThemeManager 基本功能
    def _step_manager():
        """ThemeManager 单例 + 基本 API"""
        m = theme.manager()
        assert m is theme.manager(), "manager() 应返回同一单例"
        assert hasattr(m, "themeChanged"), "缺少 themeChanged 信号"
        assert hasattr(m, "set_theme"), "缺少 set_theme 方法"
        assert hasattr(m, "current_palette"), "缺少 current_palette 方法"
        # 初始默认 dark
        theme.set_theme("dark")
        assert theme.current_theme_resolved() == "dark"
        assert theme.current_palette().name == "dark"
        print(f"  OK: 单例/信号/方法 齐全，初始 resolved={theme.current_theme_resolved()}")
    step("1 ThemeManager", _step_manager)

    # 2. dark ↔ light ↔ system 切换
    def _step_switch():
        """dark ↔ light ↔ system 切换 + resolved 解析"""
        theme.set_theme("light")
        assert theme.current_theme_resolved() == "light"
        assert theme.current_palette().name == "light"
        assert theme.current_palette().bg_top == "#EAECF6"
        print(f"  OK: → light, bg_top={theme.current_palette().bg_top}")

        theme.set_theme("dark")
        assert theme.current_theme_resolved() == "dark"
        assert theme.current_palette().bg_top == "#1B1B33"
        print(f"  OK: → dark, bg_top={theme.current_palette().bg_top}")

        theme.set_theme("system")
        assert theme.current_theme_raw() == "system"
        # 默认 system_dark=True → resolved=dark
        theme.set_system_dark(True)
        assert theme.current_theme_resolved() == "dark"
        print(f"  OK: system + 深色系统 → resolved={theme.current_theme_resolved()}")

        theme.set_system_dark(False)
        assert theme.current_theme_resolved() == "light"
        print(f"  OK: system + 浅色系统 → resolved={theme.current_theme_resolved()}")

        # 恢复
        theme.set_system_dark(True)
        theme.set_theme("dark")
    step("2 三模式切换", _step_switch)

    # 3. themeChanged 信号
    def _step_signal():
        """themeChanged 信号触发"""
        captured: list[str] = []
        theme.manager().themeChanged.connect(lambda n: captured.append(n))
        theme.set_theme("light")
        assert captured == ["light"], f"期望 ['light']，实际 {captured}"
        theme.set_theme("dark")
        assert captured == ["light", "dark"], f"期望 ['light','dark']，实际 {captured}"
        # 同名不触发
        n_before = len(captured)
        theme.set_theme("dark")
        assert len(captured) == n_before, "同名切换不应触发信号"
        print(f"  OK: themeChanged 触发 {captured}（同名不重复触发）")
    step("3 themeChanged信号", _step_signal)

    # 4. paintEvent 控件刷新验证：dark vs light 截图差异
    def _step_widget_refresh():
        """GlassContainer/GlassButton 在主题切换后刷新（截图像素差异）"""
        win = GlassWindow()
        win.set_synthetic_backdrop(make_synthetic_backdrop(QSize(400, 300)))
        win.resize(400, 300)

        container = GlassContainer(win, radius=theme.RADIUS_CARD)
        container.setGeometry(20, 20, 360, 120)
        btn = GlassButton(container, text="测试按钮", radius=theme.RADIUS_BUTTON, accent=True)
        btn.setGeometry(20, 20, 160, 50)

        # dark 主题截图
        theme.set_theme("dark")
        win.show()
        _pump(app, 200)
        pm_dark = win.grab()
        dark_avg = _avg_color(pm_dark)
        print(f"  dark 平均色: RGB{dark_avg}")

        # 切换到 light
        theme.set_theme("light")
        _pump(app, 200)
        pm_light = win.grab()
        light_avg = _avg_color(pm_light)
        print(f"  light 平均色: RGB{light_avg}")

        # 验证两者有明显差异（亮色主题应更亮）
        assert light_avg[0] > dark_avg[0] + 10, \
            f"light 主题应比 dark 更亮（R: {light_avg[0]} vs {dark_avg[0]}）"
        print(f"  OK: dark → light 像素差异显著（R 差 {light_avg[0] - dark_avg[0]}）")

        # 切换回 dark 验证可逆
        theme.set_theme("dark")
        _pump(app, 200)
        pm_dark2 = win.grab()
        dark2_avg = _avg_color(pm_dark2)
        assert abs(dark2_avg[0] - dark_avg[0]) < 20, \
            f"切回 dark 应恢复接近原色（R: {dark2_avg[0]} vs {dark_avg[0]}）"
        print(f"  OK: light → dark 可逆恢复")

        win.close()
    step("4 控件刷新", _step_widget_refresh)

    # 5. AppearancePane 实时切换
    def _step_appearance_pane():
        """AppearancePane 分段切换 → 实时 set_theme + config 写回"""
        from facktyper.ui.views.settings_panes import AppearancePane
        from facktyper.ui.widgets.liquid_glass import GlassContainer

        config = AppConfig.load()
        config.theme = "dark"
        theme.set_theme("dark")

        host = GlassWindow()
        host.resize(400, 300)
        host.set_synthetic_backdrop(make_synthetic_backdrop(QSize(400, 300)))
        pane = AppearancePane(config, host)
        pane.load()
        host.show()
        _pump(app, 150)

        # 切换到浅色
        pane._theme_seg.setCurrentIndex(1)  # 浅色
        _pump(app, 150)
        assert config.theme == "light", f"config.theme 应为 light，实际 {config.theme}"
        assert theme.current_theme_resolved() == "light", \
            f"resolved 应为 light，实际 {theme.current_theme_resolved()}"
        print(f"  OK: 分段→浅色 → config={config.theme}, resolved={theme.current_theme_resolved()}")

        # 切换到跟随系统
        theme.set_system_dark(True)
        pane._theme_seg.setCurrentIndex(2)  # 跟随系统
        _pump(app, 150)
        assert config.theme == "system"
        assert theme.current_theme_resolved() == "dark"  # system_dark=True
        print(f"  OK: 分段→系统 → config={config.theme}, resolved={theme.current_theme_resolved()}")

        # 恢复
        pane._theme_seg.setCurrentIndex(0)  # 深色
        _pump(app, 100)
        host.close()
    step("5 AppearancePane", _step_appearance_pane)

    # 6. palette_for 回退兼容
    def _step_compat():
        """palette_for / DARK / LIGHT 常量仍可用（兼容性）"""
        assert theme.palette_for("dark") is theme.DARK
        assert theme.palette_for("light") is theme.LIGHT
        assert theme.DARK.name == "dark"
        assert theme.LIGHT.name == "light"
        # current_palette 与 palette_for 一致
        theme.set_theme("dark")
        assert theme.current_palette() is theme.palette_for("dark")
        theme.set_theme("light")
        assert theme.current_palette() is theme.palette_for("light")
        theme.set_theme("dark")
        print("  OK: DARK/LIGHT/palette_for 兼容性保持")
    step("6 兼容性", _step_compat)

    print("\n" + "=" * 60)
    print("✓ M3-d 主题运行时切换验证全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
