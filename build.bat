@echo off
REM ============================================================
REM  FakeTyper Pro 单文件 exe 构建脚本
REM
REM  用法：
REM    build.bat            构建单文件 exe
REM    build.bat icon       仅重新生成应用图标
REM    build.bat clean      清理构建产物
REM
REM  产出：dist\FakeTyperPro.exe
REM ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

REM ---- 子命令分发 ----
if /i "%~1"=="clean"  goto :clean
if /i "%~1"=="icon"   goto :icon

REM ---- 1. 依赖检查 ----
echo [1/4] 检查构建依赖...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo     PyInstaller 未安装，正在安装...
    python -m pip install "pyinstaller>=6.0" || goto :fail
)
python -c "import PIL" 2>nul
if errorlevel 1 (
    echo     Pillow 未安装，正在安装...
    python -m pip install "pillow>=10.0" || goto :fail
)
python -c "import pyperclip" 2>nul
if errorlevel 1 (
    echo     pyperclip 未安装，正在安装...
    python -m pip install "pyperclip>=1.8" || goto :fail
)

REM ---- 2. 确保图标存在 ----
echo [2/4] 检查应用图标...
if not exist "src\facktyper\resources\app.ico" (
    echo     图标缺失，调用 make_icon.py 生成...
    python make_icon.py || goto :fail
)

REM ---- 3. 执行 PyInstaller ----
echo [3/4] 构建 FakeTyperPro.exe（单文件 / 无控制台）...
python -m PyInstaller FakeTyperPro.spec --noconfirm || goto :fail

REM ---- 4. 结果汇报 ----
echo [4/4] 构建完成
echo.
if exist "dist\FakeTyperPro.exe" (
    for %%I in ("dist\FakeTyperPro.exe") do set "SIZE=%%~zI"
    set /a "SIZEMB=!SIZE!/1048576"
    echo ============================================================
    echo  产物：dist\FakeTyperPro.exe  ^(!SIZEMB! MB^)
    echo  可拷贝到任意位置，发送快捷方式到桌面即可启动。
    echo ============================================================
) else (
    echo [警告] 未找到 dist\FakeTyperPro.exe，请检查上方日志。
    goto :fail
)
goto :eof

:icon
echo 重新生成应用图标...
python -c "import PIL" 2>nul || python -m pip install "pillow>=10.0"
python make_icon.py || goto :fail
goto :eof

:clean
echo 清理构建产物...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "src\facktyper\resources\app.ico" del /q "src\facktyper\resources\app.ico"
if exist "src\facktyper\resources\app_256.png" del /q "src\facktyper\resources\app_256.png"
echo 已清理 dist\ build\ 和图标资源。
goto :eof

:fail
echo.
echo ============================================================
echo  构建失败，请查看上方错误信息。
echo ============================================================
exit /b 1
