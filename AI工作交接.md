# FakeTyper v2 — AI 工作交接文档

> ⚠️ **本文档已过时（2026-10-20 晚）**：第 7 节"git init + 封存"任务已完成（commit `2946ffc`）。
> **请改读 [工作交接_总索引.md](工作交接_总索引.md)**；本文档仅第 3 节"资产盘点"仍有参考价值。

> 用途：交给任一 AI 编程助手，读罢本文件即可开始执行任务。
> 生成日期：2026-10-20 · 项目目录：`d:\1Desktop\fackTyper` · 平台：Windows + PowerShell

---

## 1. 项目是什么

**FakeTyper Pro**：Windows 桌面"伪装打字"工具。录制教学视频/直播时，把预设文本逐字模拟成真人键盘输入，输出到任意窗口。原型是一个 196 行 AutoHotkey v2 脚本（见 `初始脚本/fake_typing.ahk`）。

核心价值链：`预设文本 → 打字引擎（拦截/模拟键盘）→ 逐字输出`。**打字引擎是产品的全部价值，其余都是外围。**

## 2. v1 为什么报废（教训，禁止重犯）

1. **自绘液态玻璃特效压垮工程**：4300 行自绘 UI（截屏模糊 + 动态高光 + 超椭圆 + 手搓页面栈），导致文字看不清、元素重叠、自绘按钮大批损坏。`src/facktyper/ui/` 整体废弃。
2. **需求优先级倒挂**：提示词里视觉规格篇幅压过核心引擎，且写明"不允许降级"，把可读性让位于特效。
3. **无过程控制**：无 git、无断言式测试（只有截图目检脚本）、一次性交付 7300 行无中途验证。

## 3. 资产盘点

### 可复用（不要重写，直接摘用）

| 路径 | 说明 |
|---|---|
| `src/facktyper/core/typing_engine.py` | 打字引擎状态机（342 行纯 Python，不依赖 Qt；VK_PACKET 输出，不碰剪贴板、绕过钩子抑制） |
| `src/facktyper/core/` 其余 | hotkey_manager（键盘钩子）、controller（热键→动作）、single_instance、autostart（注册表自启）、clipboard_guard、tray_controller |
| `src/facktyper/data/` 全部 | preset_store / config / paths（%APPDATA% 与便携模式解耦）/ constants（F1–F6 白名单）/ preset |
| `src/facktyper/utils/` 全部 | logger（滚动日志）、atomic（原子写） |
| `build.bat` `FakeTyperPro.spec` `make_icon.py` `version_info.txt` | PyInstaller 打包链路，已验证可产出单文件 exe |
| `tests/test_engine_logic.py` | 引擎测试，可改造为 pytest 复用 |

### 已废弃（不修复、不参考其实现）

- `src/facktyper/ui/` **全部**（17 个自绘控件 + 8 个视图——地基错误，修补成本高于重写）
- `FakeTyper软件开发提示词_液态玻璃版.md`（事故标本，禁止再喂给 AI）
- `tests/render_*.py`（截图目检式"测试"，由 pytest 断言测试替代）

### 仅作需求知识参考

- `FakeTyper软件开发提示词.md`（v1 任务书，含快捷键表、数据存储约定；**不是 v2 规格**）
- `初始脚本/FakeTyper_使用手册.txt`、`初始脚本/preset.txt`

## 4. v2 需求重定性（MoSCoW）

- **Must**：按键触发/自动匀速两种模式 + 按键拦截与急停 + CJK 输出 + 剪贴板无感 + 多预设 CRUD + 总开关 + F1–F6 可重绑 + 数据与 exe 路径解耦 + 单文件 exe
- **Should**：系统托盘 + 单实例 + 设置中心（启动行为/自启/速度/拟人化参数）+ 深色主题
- **Could**：浅色/跟随系统、预设导入导出、搜索、置顶、拖拽排序
- **Won't（明确不做）**：自绘液态玻璃、动态高光、波纹动效、首启引导动画、浮动状态胶囊、任何自绘按钮/控件——一律 Qt 原生控件

**视觉铁律**：可读性一票否决；文字与背景对比度 ≥ 4.5:1；若要毛玻璃，只允许 Qt 原生 DWM（Mica/Acrylic）API，一行自绘都不写。

## 5. 开发纪律（执行 AI 必须遵守）

1. **一次一个任务**，不跨里程碑、不顺手"优化"未要求的代码、不新建无关文件；
2. 交付的每段代码必须附带**运行/验证方式**，"读过"不算数，"跑起来"才算；
3. 引擎层**先写 pytest 测试再写实现**；
4. 每个验证通过的节点**一次 git commit**；
5. 同一问题连续两次修不好 → 停下向人报告，禁止暴力重试；
6. 有需求歧义时：先给出自己的理解与假设，写进回复，再继续推进。

## 6. 路线图与验证门

| 里程碑 | 内容 | 验证门（不通过不进下一步） |
|---|---|---|
| M1 引擎复活（无 UI） | 摘出 core/ + data/ + utils/，命令行可驱动 | pytest 引擎测试全绿 |
| M2 最小原生 UI | Qt 原生控件：总开关 + 预设库 + 热键面板 | 验收清单逐项人工过 |
| M3 系统集成 | 托盘 / 单实例 / 开机自启 / 关闭到托盘 | 真实录课场景试用 |
| M4 打包交付 | PyInstaller 单文件 exe + 快捷方式 | 多位置双击启动通过 |

## 7. 当前任务：git init + 封存 v1 事故标本

目标：把 v1 现状**原样**封进 git 历史，作为后续一切工作的回退基线。

执行步骤：

1. 在项目根目录创建 `.gitignore`，内容：

   ```gitignore
   __pycache__/
   *.pyc
   .pytest_cache/
   build/
   dist/
   ```

   说明：`dist/` 内有 53MB 的 exe、`build/` 是 PyInstaller 中间产物，均不入库；`FakeTyperPro.spec` 是构建配置，**要**入库。

2. `git init`
3. `git add -A`，然后 `git status` 检查：不得有 `build/`、`dist/`、`__pycache__` 被跟踪
4. 首次提交：

   ```powershell
   git commit -m "chore: 封存 v1 事故标本（液态玻璃 UI 已废弃，引擎与数据层保留复用）"
   ```

5.（可选）打标记：`git tag v1-fossil`

验收：`git log --oneline` 有且有一条提交；`git status` 干净；仓库不含 exe（体积应在几 MB 量级）。

## 8. 封存完成后的下一步

进入 **M1**：把 `core/`、`data/`、`utils/` 摘出为可独立运行的包，配 pytest 把引擎状态机测试跑绿（`tests/test_engine_logic.py` 可改造复用）。M1 期间**禁止碰任何 UI 代码**。
