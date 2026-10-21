# FakeTyper Pro

伪装打字桌面软件 —— 录制教学视频时，把预设代码假装现场手敲。

基于 PySide6 液态玻璃 UI，重构自 AHK v2 脚本，提供多预设管理、可重绑热键、
设置中心、系统托盘、开机自启等完整桌面应用体验。单文件 exe，快捷方式放任意位置即可启动。

---

## 功能特性

- **两种输出模式**
  - 按键触发（F1）：每按一键输出 n 个字符（可配 1–5，或随机 1–3）
  - 自动匀速（F3）：按设定间隔逐字自动输出
- **拟人化输出**：随机抖动间隔、标点处差异化停顿（逗号短停 / 句号长停 / 换行段落停）、低概率思考停顿
- **多预设库**：新建 / 编辑 / 删除 / 副本 / 置顶，拖拽排序，实时搜索过滤
- **预设编辑器**：等宽多行编辑（JetBrains Mono），支持 .txt 导入、剪贴板粘贴，字符/行数/预估时长统计
- **可重绑热键**：F1–F6 录制式绑定，冲突自动交换
- **液态玻璃界面**：模糊 + 饱和 + 折射 + 顶光 + 动态高光，超椭圆 squircle 圆角层级化
- **主题切换**：深色 / 浅色 / 跟随系统，运行时实时刷新
- **系统集成**：系统托盘（动态图标）、单实例守卫、开机自启、关闭最小化到托盘
- **首启引导**：三张滑动卡片介绍功能与快捷键
- **数据安全**：剪贴板全程不碰（字符走 VK_PACKET），数据落 `%APPDATA%`，损坏文件自动隔离
- **便携模式**：exe 同目录放置 `portable.flag` 即用 `data\` 目录，免写注册表

## 默认快捷键

| 键  | 功能           | 说明                         |
|-----|----------------|------------------------------|
| F1  | 按键触发模式   | 开/关，开启后每按一键输出字符 |
| F2  | 急停           | 立即停止所有输出             |
| F3  | 自动匀速模式   | 开/关，开启后自动逐字输出     |
| F4  | 重置进度       | 游标回到预设开头             |
| F5  | 重新加载预设   | 重新载入当前预设内容         |
| F6  | 切换下一预设   | 循环切换到下一套预设         |

> 所有热键均可在「设置 → 快捷键」中重新绑定（仅限 F1–F6）。

## 快速开始

### 运行已打包的 exe

1. 双击 `dist\FakeTyperPro.exe`（或其快捷方式）即可启动
2. 首次启动会显示引导卡片，可跳过
3. 点击「＋ 新建预设」粘贴代码，开启顶部总开关
4. 聚焦到目标输入框，按 F1（按键触发）或 F3（自动匀速）开始输出

### 从源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 GUI（默认）
python -m facktyper

# 命令行交互模式
python -m facktyper cli

# 运行自测
python -m facktyper selftest

# 以最小化到托盘启动（开机自启用）
python -m facktyper --minimized
```

> `keyboard` 库安装全局键盘钩子需要管理员权限。若热键无响应，请以管理员身份运行。

## 打包

```bash
# 一键构建单文件 exe（自动检查依赖、生成图标、调用 PyInstaller）
build.bat

# 仅重新生成应用图标
build.bat icon

# 清理构建产物
build.bat clean
```

产出：`dist\FakeTyperPro.exe`（约 53 MB，单文件，无控制台窗口）

也可手动执行：

```bash
pip install pyinstaller pillow pyperclip
python make_icon.py
pyinstaller FakeTyperPro.spec --noconfirm
```

## 目录结构

```
fackTyper项目/
├── src/facktyper/
│   ├── __main__.py          # 入口：gui(默认) / cli / selftest
│   ├── cli.py               # 命令行交互模式
│   ├── selftest.py          # 内置自测
│   ├── data/                # 数据层
│   │   ├── paths.py         #   路径解耦（%APPDATA% / 便携模式）
│   │   ├── preset.py        #   预设模型
│   │   ├── preset_store.py  #   预设 CRUD
│   │   ├── config.py        #   设置 + 热键映射
│   │   └── constants.py     #   Action 枚举 + F1–F6 白名单
│   ├── core/                # 核心引擎
│   │   ├── typing_engine.py #   状态机 + 字符输出 + 拟人化
│   │   ├── hotkey_manager.py#   键盘钩子 + 抑制
│   │   ├── clipboard_guard.py#  剪贴板保护
│   │   ├── controller.py    #   热键→动作 + 总开关 + 预设管理
│   │   ├── single_instance.py#  单实例守卫
│   │   ├── autostart.py     #   开机自启（注册表）
│   │   └── tray_controller.py#  系统托盘
│   ├── ui/                  # 界面层
│   │   ├── app.py           #   run_gui 入口
│   │   ├── theme.py         #   主题管理 + 色板
│   │   ├── widgets/         #   液态玻璃核心 + 控件
│   │   └── views/           #   主窗口 / 编辑页 / 设置页 / 引导页
│   ├── utils/               # 工具
│   │   ├── logger.py        #   滚动日志 + 全局异常钩子
│   │   └── atomic.py        #   原子化读写
│   └── resources/
│       └── app.ico          #   应用图标
├── tests/                   # 验证脚本
├── FakeTyperPro.spec        # PyInstaller 配置
├── make_icon.py             # 图标生成脚本
├── build.bat                # 一键打包
├── version_info.txt         # Windows 版本资源
├── requirements.txt         # 运行依赖
└── pyproject.toml           # 项目元数据
```

## 数据存储

| 模式   | 位置                              | 触发条件                          |
|--------|-----------------------------------|-----------------------------------|
| 常规   | `%APPDATA%\FakeTyperPro\`         | 默认                              |
| 便携   | exe 同目录 `\data\`               | exe 同目录存在 `portable.flag` 文件 |

目录内含 `presets\`（预设 JSON）、`config.json`（设置）、`logs\`（日志）、
`backups\`（损坏预设隔离区）。

## 验证测试

```bash
# 引擎状态机
python tests/test_engine_logic.py

# 真实键盘抑制链路
python tests/test_real_suppression.py

# 液态玻璃渲染
python tests/render_glass.py

# 控件层
python tests/render_widgets.py

# 主窗口
python tests/render_main_window.py

# 编辑页
python tests/render_editor_page.py

# 设置中心
python tests/render_settings_page.py

# 首启引导
python tests/render_onboarding.py

# 主题切换
python tests/m3d_verify.py

# 托盘 + 单实例
python tests/m3e_verify.py
```

> 涉及持久化数据的测试（如 selftest）须串行运行，不可与写预设的测试并行。

## 技术要点

- **字符输出**：统一走 `keyboard._os_keyboard.type_unicode`（VK_PACKET），绕过 LL 钩子——
  既不触发回调也不被抑制，且完全不碰剪贴板，天然满足剪贴板保护目标。
- **特殊键**：Enter 在抑制期间临时摘单键钩子再发送；Tab/Backspace 不在抑制白名单直接发送。
- **引擎与 UI 分离**：纯 Python 引擎通过 `EngineListener` 回调通信，
  `EngineBridge` 适配为 Qt 信号（跨线程 AutoConnection 自动队列化）。
- **双页面转场**：自定义容器 + `QVariantAnimation` 驱动位移 + `QGraphicsOpacityEffect` 淡入淡出，
  实现 iOS push/pop 风格（QStackedWidget 无法两页并存）。
- **主题动态化**：`ThemeManager` 单例 + `themeChanged` 信号遍历所有控件 `update()`；
  `style_text` 注册的 QLabel/QLineEdit 通过动态属性重应用 stylesheet。

## 许可

© 2026 FakeTyper Pro
