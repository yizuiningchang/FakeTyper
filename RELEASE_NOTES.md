# FakeTyper 3.0.0 发布说明

发布日期：2026-10-26  
平台：Windows 11 x64（已实测）；Windows 10 未验证

## 下载

- Release：<https://github.com/yizuiningchang/FakeTyper/releases/tag/v3.0.0>
- 文件：`FakeTyper-3.0.0-win64.zip`
- 解压后直接运行 `FakeTyper.exe`，无需安装。

## 本版内容

FakeTyper V3 是一次完整重写，重点是把“录课/演示时看起来像手敲”的流程做得更直接：

- 单文件 exe，无需安装；首次运行创建“使用说明”预设。
- F1 开始/停止，F2 暂停/继续，F3 切换预设；F4–F12 为直选槽。
- 编辑器式主界面：预设库、标题与内容编辑、底部直选槽。
- 自定义标题栏、托盘三态、关闭到托盘、单实例保护。
- 设置页四板块：常规、皮肤占位、使用说明、关于与作者名片。
- WebView2 缺失时显示原生提示和官方下载地址，不出现空白窗口。
- 运行期不联网、不读写剪贴板、不记录按键内容。

## 文件校验

`FakeTyper.exe`：

```text
SHA-256 c47cc69a96c3abd5a07c7be1ac48329088dba0d5203ae2676a3c8c8ecd40ccfd
```

`FakeTyper-3.0.0-win64.zip` SHA-256：

```text
9f117bade852a052b68fd1af5125831ca88c28b77bb52a0489a5728e4d923fd0
```

发布包内 `SHA256SUMS.txt` 也包含 `FakeTyper.exe` 的校验值。

当前构建未做数字签名；Windows SmartScreen 可能提示，请核对来源与上述校验值。

## 系统要求

- Windows 11 x64（已实测）；Windows 10 未验证。
- Microsoft Edge WebView2 Runtime（Win11 通常自带；缺失时应用会提示下载）。
- 普通权限可运行；向管理员权限窗口输出需以管理员身份启动。
- 设计支持 1080P–4K / 100%–200% 缩放；已在 2560×1600 实机验证 100/125/150/200%，真实 4K 与多屏混合 DPI 未实测。

## 已知限制

- 目标编辑器需关闭自动缩进；否则换行缩进会逐层叠加。VS Code：`"editor.autoIndent": "none"`。
- 笔记本需关闭或锁定 Fn 媒体层；Fn 层无法被应用拦截。
- 运行态下未启用的 F4–F12 会被占用；需要浏览器 F5、讯飞 F7 等原生功能时先按 F2 暂停或 F1 停止。
- Win10、真实 4K、多屏混合 DPI、任务栏缩略图/跳转列表、Snap Layouts 飞出层、触摸/触控笔未验证。
- 皮肤当前只提供静态占位；主题、透明度和模糊未实现。
- 未做代码签名。

## 许可

[PolyForm Noncommercial License 1.0.0](LICENSE)。仅供非商业用途；商业使用需另行获得许可。

## 作者

凝裳（[@yizuiningchang](https://github.com/yizuiningchang)）
