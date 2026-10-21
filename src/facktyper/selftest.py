"""M1 数据/配置层自测（不依赖键盘钩子，可安全自动化运行）。

覆盖：
- 路径解析与目录创建；
- 原子化文件读写；
- Preset 模型序列化；
- 预设存储 CRUD / 搜索 / 排序 / 置顶 / 删除备份；
- 配置加载/保存/校验/热键映射冲突处理。
"""
from __future__ import annotations

import sys
import tempfile
import time

from .data import paths, preset_store
from .data.config import AppConfig
from .data.constants import Action, default_hotkey_map, validate_hotkey_map
from .data.preset import Preset
from .utils.atomic import atomic_write_json, safe_read_json


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def test_paths() -> bool:
    print("[test] 路径解析")
    root = paths.data_root()
    assert paths.presets_dir().exists(), "presets 目录未创建"
    assert paths.backups_dir().exists(), "backups 目录未创建"
    assert paths.logs_dir().exists(), "logs 目录未创建"
    _ok(f"data_root = {root}")
    return True


def test_atomic() -> bool:
    print("[test] 原子化读写")
    import os, uuid

    tmp = paths.data_root() / f"_selftest_{uuid.uuid4().hex[:8]}.json"
    payload = {"k": "中文值", "n": 42, "list": [1, 2, 3]}
    atomic_write_json(tmp, payload)
    got = safe_read_json(tmp, default=None)
    assert got == payload, f"读回不一致: {got}"
    _ok("写入并读回一致")
    # 损坏文件安全读取
    tmp.write_text("{ not json", encoding="utf-8")
    assert safe_read_json(tmp, default={"d": 1}) == {"d": 1}, "损坏文件未回退默认"
    _ok("损坏文件安全回退默认值")
    tmp.unlink(missing_ok=True)
    return True


def test_preset_model() -> bool:
    print("[test] Preset 模型")
    p = Preset.create("示例", "abc\n中")
    d = p.to_dict()
    p2 = Preset.from_dict(d)
    assert p2.title == "示例" and p2.content == "abc\n中"
    assert p.char_count == 4  # 去掉换行: a,b,c,中 = 4
    assert p.total_chars == 5  # 含换行: a,b,c,\n,中 = 5
    _ok("序列化/反序列化与字符统计正确")
    return True


def test_preset_store() -> bool:
    print("[test] 预设存储 CRUD/搜索/排序/置顶/删除备份")
    # 清理自测残留
    for fp in paths.presets_dir().glob("_selftest_*.json"):
        fp.unlink(missing_ok=True)

    # 备份现有预设，确保测试在隔离环境运行（reorder 断言要求目录干净）
    import shutil as _sh
    backup_dir = paths.data_root() / "_selftest_preset_backup"
    if backup_dir.exists():
        _sh.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    _preserved: list = []
    for fp in paths.presets_dir().glob("*.json"):
        _sh.move(str(fp), str(backup_dir / fp.name))
        _preserved.append(fp.name)

    try:
        a = Preset.create("Alpha", "alpha content aaa")
        b = Preset.create("Beta 中", "beta 内容 中文")
        c = Preset.create("Gamma", "gamma code")
        for p in (a, b, c):
            preset_store.save_preset(p)

        items = preset_store.list_presets()
        ids = [p.id for p in items]
        assert a.id in ids and b.id in ids and c.id in ids
        _ok(f"列出 {len(items)} 套预设")

        # 搜索
        res = preset_store.search("beta", items)
        assert any(p.id == b.id for p in res), "搜索 Beta 失败"
        res_cn = preset_store.search("中文", items)
        assert any(p.id == b.id for p in res_cn), "中文搜索失败"
        _ok("搜索（中英文）命中正确")

        # 置顶
        preset_store.set_pinned(c.id, True)
        items = preset_store.list_presets()
        assert items[0].id == c.id, f"置顶项应排首位，实际 {items[0].title}"
        _ok("置顶排在首位")

        # 重置置顶，测试排序权重
        preset_store.set_pinned(c.id, False)
        preset_store.reorder([b.id, a.id, c.id])
        items = preset_store.list_presets()
        order = [p.id for p in items if not p.pinned]
        assert order[:3] == [b.id, a.id, c.id], f"排序权重不符: {order}"
        _ok("拖拽排序生效")

        # 更新
        a.title = "Alpha 改"
        a.content = "new"
        preset_store.save_preset(a)
        got = preset_store.get_preset(a.id)
        assert got.title == "Alpha 改" and got.content == "new"
        _ok("更新持久化")

        # 删除 + 备份
        assert preset_store.delete_preset(a.id)
        assert preset_store.get_preset(a.id) is None
        baks = list(paths.backups_dir().glob(f"{a.id}_*.json"))
        assert baks, "删除未生成备份"
        _ok(f"删除已备份（{len(baks)} 份）")

        # 损坏隔离
        bad = paths.presets_dir() / "_selftest_corrupted.json"
        bad.write_text("{ broken", encoding="utf-8")
        items = preset_store.list_presets()  # 不应抛异常
        assert not any(p.id == "_selftest_corrupted" for p in items)
        assert not bad.exists(), "损坏文件未隔离"
        _ok("损坏文件已隔离，未阻断加载")

        # 清理本次测试创建的预设
        for p in preset_store.list_presets():
            if p.id in (b.id, c.id):
                preset_store.delete_preset(p.id)
    finally:
        # 恢复原有预设
        for name in _preserved:
            src = backup_dir / name
            dst = paths.presets_dir() / name
            if src.exists():
                _sh.move(str(src), str(dst))
        try:
            _sh.rmtree(backup_dir)
        except Exception:
            pass
    return True


def test_config() -> bool:
    print("[test] 配置加载/校验/热键映射")
    cfg = AppConfig()
    cfg.auto_speed_ms = 5  # 越界
    cfg.chars_per_keypress = 99
    cfg.jitter_amount = 2.5
    cfg.theme = "pink"
    cfg._normalize()
    assert cfg.auto_speed_ms == 10, f"auto_speed 未夹断: {cfg.auto_speed_ms}"
    assert cfg.chars_per_keypress == 5
    assert 0.0 <= cfg.jitter_amount <= 1.0
    assert cfg.theme == "dark"
    _ok("设置项越界自动夹断")

    # 默认热键映射
    hm = default_hotkey_map()
    assert hm[Action.KEY_TRIGGER.value] == "F1"
    assert hm[Action.STOP.value] == "F2"
    assert len(set(hm.values())) == 6, "默认映射应 6 键无重复"
    _ok("默认热键映射正确")

    # 冲突交换
    cfg.set_hotkey(Action.AUTO.value, "F1")  # F1 原属 KEY_TRIGGER
    assert cfg.hotkey_map[Action.AUTO.value] == "F1"
    assert cfg.hotkey_map[Action.KEY_TRIGGER.value] == "F3", "冲突应交换"
    _ok("热键冲突自动交换")

    # 非法键被拒绝
    cfg2 = AppConfig()
    cfg2.hotkey_map = {Action.STOP.value: "F9", Action.KEY_TRIGGER.value: "F1"}
    cfg2._normalize()
    assert cfg2.hotkey_map[Action.STOP.value] != "F9", "F9 不在白名单应被替换"
    _ok("白名单外按键被拒绝并补齐")

    # 持久化往返
    cfg.save()
    cfg3 = AppConfig.load()
    assert cfg3.auto_speed_ms == cfg.auto_speed_ms
    assert cfg3.hotkey_map == cfg.hotkey_map
    _ok("配置持久化往返一致")

    # 还原默认映射，避免污染
    cfg_default = AppConfig()
    cfg_default.hotkey_map = default_hotkey_map()
    cfg_default.save()
    return True


def run_selftest() -> int:
    print("=" * 56)
    print("FakeTyper Pro —— M1 数据/配置层自测")
    print("=" * 56)
    tests = [test_paths, test_atomic, test_preset_model, test_preset_store, test_config]
    passed = 0
    for t in tests:
        try:
            if t():
                passed += 1
        except Exception as e:  # noqa: BLE001
            import traceback

            _fail(f"{t.__name__} 异常: {e}")
            traceback.print_exc()
    print("-" * 56)
    print(f"结果：{passed}/{len(tests)} 通过")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(run_selftest())
