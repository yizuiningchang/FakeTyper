# FakeTyper 3.1.0 发布说明

发布日期：2026-10-27  
平台：Windows 11 x64（已实测）；Windows 10 未验证

## 下载

- Release：<https://github.com/yizuiningchang/FakeTyper/releases/tag/v3.1.0>
- 文件：`FakeTyper-3.1.0-win64.zip`
- 解压后直接运行 `FakeTyper.exe`，无需安装。

## 本版内容

- **冷雾浅色皮肤**：新增完整浅色外观；与石墨深色同为内置皮肤。
- **设置页 → 皮肤**：跟随系统 / 深色 / 浅色三态；石墨、冷雾两张皮肤卡；恢复默认外观只重置外观。
- **跟随 Windows**：默认跟随应用模式（`AppsUseLightTheme`），系统深浅切换约 1 秒内生效；也可固定深色或浅色。
- **持久化与启动顺序**：切换即时保存，重启恢复；启动先应用皮肤再显示窗口，避免错误皮肤闪烁。
- **托盘双皮肤**：托盘菜单同步深/浅颜色，菜单打开前重算。
- 延续：F1/F2/F3、F4–F12 直选槽、预设库、自定义标题栏、托盘三态、关闭到托盘、单实例、WebView2 缺失提示。
- 运行期不联网、不读写剪贴板、不记录按键内容。

## 文件校验

`FakeTyper.exe`：

```text
SHA-256 5feaa42ed0ee788205019d3dc23d57b511aaa53d93920707daea1197d4704709
```

`FakeTyper-3.1.0-win64.zip` SHA-256：

```text
5a68f094ba703cb9d41c8304f7d31a34b98cd66f071debcdd51e14e08c736109
```

发布包内 `SHA256SUMS.txt` 也包含 `FakeTyper.exe` 等文件校验值。

当前构建未做数字签名；Windows SmartScreen 可能提示，请核对来源与上述校验值。

## 升级与数据

- 本版没有数据迁移步骤；数据目录仍为 `%APPDATA%\FakeTyper`，升级前可自行备份。
- 外观默认“跟随系统”：Windows 为浅色的升级用户首次启动会看到冷雾浅色界面；可在设置页 → 皮肤固定深色或浅色。

## 系统要求

- Windows 11 x64（已实测）；Windows 10 未验证。
- Microsoft Edge WebView2 Runtime（Win11 通常自带；缺失时应用会提示下载）。
- 普通权限可运行；向管理员权限窗口输出需以管理员身份启动。
- 设计支持 1080P–4K / 100%–200% 缩放；已在 2560×1600 实机验证 100/125/150/200%，真实 4K 与多屏混合 DPI 未实测。

## 已知限制

- 目标编辑器需关闭自动缩进；否则换行缩进会逐层叠加。VS Code：`"editor.autoIndent": "none"`。
- 笔记本需关闭或锁定 Fn 媒体层；Fn 层无法被应用拦截。
- 运行态下未启用的 F4–F12 会被占用；需要浏览器 F5、讯飞 F7 等原生功能时先按 F2 暂停或 F1 停止。
- **材质透明度与主题贴画不在 v3.1.0**：在 v3.2.0 评估/交付；本版不宣称透明材质。
- 浅色禁用态按钮仍以 50% 透明度表示，未单独配色（已知观感项；禁用态不参与 WCAG 对比度）。
- Win10、真实 4K、多屏混合 DPI、任务栏缩略图/跳转列表、Snap Layouts 飞出层、触摸/触控笔未验证。
- 未做代码签名。

## 许可

[PolyForm Noncommercial License 1.0.0](LICENSE)。仅供非商业用途；商业使用需另行获得许可。

## 作者

凝裳（[@yizuiningchang](https://github.com/yizuiningchang)）
