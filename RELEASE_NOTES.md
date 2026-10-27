# FakeTyper 3.1.1 发布说明

发布日期：2026-10-27  
平台：Windows 11 x64（已实测）；Windows 10 x64 22H2（同事实机全功能测试通过）；其他 Win10 版本未验证

## 下载

- Release：<https://github.com/yizuiningchang/FakeTyper/releases/tag/v3.1.1>
- 文件：`FakeTyper-3.1.1-win64.zip`
- 解压后直接运行 `FakeTyper.exe`，无需安装。

## 本版内容

- **验证与文档修订**：功能与 3.1.0 相同，无代码功能变更。
- **Win10 22H2 验证**：同事实机全功能测试通过（1K 外接 + 2K 笔记本双屏、100/125/150/200% 缩放、WebView2 与开发机同版本；使用 v3.1.0 官方包）。
- 内置使用说明、README 与发布说明更新 Win10 表述；其他 Win10 版本、真实 4K、其他混合 DPI 组合仍标注未验证。
- 延续 3.1.0：石墨/冷雾双皮肤、跟随 Windows 系统、设置页皮肤切换与持久化、托盘双皮肤、F1–F12 等。

## 文件校验

`FakeTyper.exe`：

```text
SHA-256 5be7b7167aca491110e634f728a5be9f5f427d4360d4cffad3d94eb44cf9161a
```

`FakeTyper-3.1.1-win64.zip` SHA-256：

```text
9c7bb17124de984a277fbc3df3907b4713a5c64c668d07c4a6bdcbf6b27fc1a6
```

发布包内 `SHA256SUMS.txt` 也包含 `FakeTyper.exe` 等文件校验值。

当前构建未做数字签名；Windows SmartScreen 可能提示，请核对来源与上述校验值。

## 升级与数据

- 本版没有数据迁移步骤；数据目录仍为 `%APPDATA%\FakeTyper`，升级前可自行备份。
- 外观默认“跟随系统”：Windows 为浅色的升级用户首次启动会看到冷雾浅色界面；可在设置页 → 皮肤固定深色或浅色。

## 系统要求

- Windows 11 x64（已实测）。
- Windows 10 x64 22H2（同事实机全功能测试通过）；其他 Win10 版本未验证。
- Microsoft Edge WebView2 Runtime（Win11 通常自带；缺失时应用会提示下载）。
- 普通权限可运行；向管理员权限窗口输出需以管理员身份启动。
- 已在 2560×1600 与 Win10 1K+2K 双屏验证 100/125/150/200% 缩放；真实 4K、其他混合 DPI 组合未实测。

## 已知限制

- 材质透明度与主题贴画不在 v3.1.0/v3.1.1：在 v3.2.0 评估/交付；本版不宣称透明材质。
- 其他 Win10 版本（非 22H2）、真实 4K、其他混合 DPI 组合、任务栏缩略图/跳转列表、Snap Layouts 飞出层、触摸/触控笔未验证。
- 浅色禁用态按钮仍以 50% 透明度表示，未单独配色（已知观感项；禁用态不参与 WCAG 对比度）。
- 目标编辑器需关闭自动缩进；笔记本需关闭或锁定 Fn 媒体层；运行态未启用的 F4–F12 会被占用。
- 未做代码签名。

## 许可

[PolyForm Noncommercial License 1.0.0](LICENSE)。仅供非商业用途；商业使用需另行获得许可。

## 作者

凝裳（[@yizuiningchang](https://github.com/yizuiningchang)）
