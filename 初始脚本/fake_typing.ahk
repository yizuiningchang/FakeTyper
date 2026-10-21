#Requires AutoHotkey v2.0
#SingleInstance Force

; ============================================================
;  伪装打字工具  FakeTyper
;  用途：录制教学视频时，把提前写好的代码"假装手敲"出来
;  原理：拦截你的真实按键并屏蔽，每按一次输出预设文本下一字
; ------------------------------------------------------------
;  快捷键：
;    F1  启动 / 暂停「按键触发」模式（随便敲键盘，逐字出预设内容）
;    F2  退出脚本
;    F3  启动 / 暂停「自动匀速」模式（自动按固定间隔逐字输出）
;    F4  重置：把光标位置回到预设文本开头，方便重录
;    F5  重新读取 preset.txt（改完文本后不用重启脚本）
;  预设文本：编辑同目录下的 preset.txt
; ============================================================

; ---------- 可调参数 ----------
global autoSpeed := 80   ; 自动模式每字间隔(ms)，越小越快
; ------------------------------

global presetText := ""
global idx := 1
global keyMode := false    ; 按键触发模式
global autoMode := false   ; 自动匀速模式
global hkList := []

LoadPreset()
RegisterKeys()
Tip("伪装打字已就绪`nF1=按键触发  F3=自动匀速`nF2=退出  F4=重置  F5=重载文本")

; ==================== 快捷键 ====================

F1:: {  ; 启动/暂停 按键触发模式
    global keyMode, idx
    StopAuto()
    keyMode := !keyMode
    ToggleKeys(keyMode)
    if keyMode {
        idx := 1
        Tip("▶ 按键触发模式 ON`n随意敲键盘即可，再按 F1 暂停")
    } else {
        Tip("⏸ 已暂停（恢复正常打字）")
    }
}

F2::ExitApp  ; 退出

F3:: {  ; 启动/暂停 自动匀速模式
    global autoMode, idx
    StopKey()
    autoMode := !autoMode
    if autoMode {
        idx := 1
        SetTimer(AutoType, autoSpeed)
        Tip("▶ 自动匀速模式 ON`n每 " autoSpeed "ms 一字，再按 F3 停止")
    } else {
        SetTimer(AutoType, 0)
        Tip("⏸ 自动模式已停止")
    }
}

F4:: {  ; 重置到开头
    global idx, keyMode, autoMode
    idx := 1
    Tip("↺ 已重置到开头 (idx=1)`n当前模式保持不变")
}

F5:: {  ; 重新读取预设文本
    LoadPreset()
    global idx := 1
    Tip("🔄 已重新读取 preset.txt`n共 " StrLen(presetText) " 字")
}

; ==================== 自动输出 ====================

AutoType() {
    global idx, presetText, autoMode
    if !autoMode
        return
    if idx > StrLen(presetText) {
        StopAuto()
        Tip("✅ 预设文本输出完毕")
        return
    }
    ch := SubStr(presetText, idx, 1)
    idx += 1
    SendChar(ch)
}

; ==================== 按键回调 ====================

OnKey(*) {
    global keyMode, idx, presetText
    if !keyMode
        return
    if idx > StrLen(presetText) {
        StopKey()
        Tip("✅ 预设文本输出完毕")
        return
    }
    ch := SubStr(presetText, idx, 1)
    idx += 1
    SendChar(ch)
}

; ==================== 热键注册/开关 ====================

; 注册要拦截的按键（默认处于关闭状态，不影响正常打字）
RegisterKeys() {
    global hkList
    keys := []
    Loop 26                       ; a-z
        keys.Push(Chr(96 + A_Index))
    Loop 10                       ; 0-9
        keys.Push(Chr(47 + A_Index))
    keys.Push("Space")
    keys.Push("Enter")
    for p in ["-", "=", "[", "]", "\", ";", "'", ",", ".", "/"]
        keys.Push(p)
    for k in keys {
        try {
            Hotkey("$*" k, OnKey, "Off")   ; 创建热键并绑定回调，但默认关闭
            hkList.Push("$*" k)
        }
    }
}

; 批量启用/禁用所有拦截热键
ToggleKeys(on) {
    global hkList
    for h in hkList {
        try Hotkey(h, , on ? "On" : "Off")   ; 仅切换状态，不改回调
    }
}

StopKey() {
    global keyMode
    if keyMode {
        keyMode := false
        ToggleKeys(false)
    }
}

StopAuto() {
    global autoMode
    if autoMode {
        autoMode := false
        SetTimer(AutoType, 0)
    }
}

; ==================== 发送单个字符 ====================

SendChar(ch) {
    code := Ord(ch)
    if (code = 10 || code = 13) {        ; 换行/回车
        Send("{Enter}")
    } else if (code = 9) {               ; Tab
        Send("{Tab}")
    } else if (code = 32) {              ; 空格
        Send("{Space}")
    } else if (code < 128) {             ; 普通 ASCII：直接发文本
        SendText(ch)
    } else {                             ; 中文等非 ASCII：走剪贴板
        A_Clipboard := ch
        Sleep(30)
        Send("^v")
    }
}

; ==================== 读取预设文本 ====================

LoadPreset() {
    global presetText
    path := A_ScriptDir "\preset.txt"
    if FileExist(path) {
        presetText := FileRead(path, "UTF-8")
        presetText := StrReplace(presetText, "`r`n", "`n")  ; 统一换行
        presetText := StrReplace(presetText, "`r", "`n")
        presetText := RTrim(presetText, "`n")               ; 去掉末尾多余换行
    } else {
        presetText := "while running:`n    frame = frame_queue.get()`n    overlay(frame)"
    }
    if presetText = "" {
        presetText := "（preset.txt 为空，请填写内容）"
    }
}

; ==================== 提示 ====================

Tip(msg) {
    ; 提示已关闭。如需恢复，把下面两行取消注释即可：
    ; ToolTip(msg)
    ; SetTimer(() => ToolTip(), -2500)
}
