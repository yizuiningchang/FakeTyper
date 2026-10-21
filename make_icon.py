"""生成 FakeTyper Pro 应用图标（.ico，多尺寸）。

图标设计：紫色渐变超椭圆背景 + 顶光带 + 白色键盘方块矩阵，
与主窗口顶栏 logo（_paint_app_logo）视觉一致。

运行：``python make_icon.py``
产出：``src/facktyper/resources/app.ico``（含 256/128/64/48/32/16 多尺寸）
"""
from __future__ import annotations

from pathlib import Path
from math import sqrt

from PIL import Image, ImageDraw, ImageFilter


def _superellipse_mask(size: int, radius: float) -> Image.Image:
    """生成超椭圆（squircle）形状的 L 通道遮罩。"""
    img = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(img)
    # 用圆角矩形近似超椭圆（Qt 端用真正的超椭圆曲线，图标用圆角矩形足够）
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(radius), fill=255)
    return img


def _make_icon(size: int) -> Image.Image:
    """渲染指定尺寸的图标（RGBA）。"""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    radius = s * 0.28

    # 1) 紫色渐变超椭圆底（左上浅紫 → 右下深紫）
    base = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gp = grad.load()
    c1 = (0x9D, 0x8E, 0xFF)  # accent_soft
    c2 = (0x7C, 0x6F, 0xF0)  # accent
    for y in range(s):
        for x in range(s):
            t = (x + y) / max(1, 2 * s - 2)
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            gp[x, y] = (r, g, b, 255)
    mask = _superellipse_mask(s, radius)
    base.paste(grad, (0, 0), mask)

    # 2) 顶光带（上半部白→透明渐变）
    hl = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hp = hl.load()
    for y in range(s // 2):
        a = int(110 * (1 - y / max(1, s // 2)))
        for x in range(s):
            hp[x, y] = (255, 255, 255, a)
    hl.putalpha(Image.composite(
        hl.split()[3], Image.new("L", (s, s), 0), mask
    ))
    base = Image.alpha_composite(base, hl)

    # 3) 键盘方块矩阵（2 行 3 列，白色）
    d = ImageDraw.Draw(base)
    cell = s * 0.13
    gap = s * 0.04
    grid_w = 3 * cell + 2 * gap
    grid_x = (s - grid_w) / 2
    grid_y = s * 0.42
    for r in range(2):
        for c in range(3):
            cx = grid_x + c * (cell + gap)
            cy = grid_y + r * (cell + gap)
            d.rounded_rectangle(
                (cx, cy, cx + cell, cy + cell),
                radius=max(1, cell * 0.18),
                fill=(255, 255, 255, 240),
            )

    return base


def main() -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    images = [_make_icon(s) for s in sizes]
    out_dir = Path("src/facktyper/resources")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "app.ico"
    # 主图为 256，其余作为附加尺寸
    images[0].save(out_path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"图标已生成: {out_path}（尺寸 {sizes}）")

    # 同时输出一张 256 PNG 便于预览
    png_path = out_dir / "app_256.png"
    images[0].save(png_path, format="PNG")
    print(f"预览图: {png_path}")


if __name__ == "__main__":
    main()
