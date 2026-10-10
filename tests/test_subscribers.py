import json

import pytest

from rssrob.subscribers import Subscribers, normalize_hours


# 本文件的用例原先用裸邮箱做订阅目标。1ccbdbd（改用 Apprise 多服务通知）把
# Subscribers 的模型换成了 Apprise URL（scheme://...），旧邮箱只在读取历史数据时
# 才被迁移成 mailto://。当时测试没跟着改，又因为 is_valid_email 已删除而在收集阶段
# 直接 ImportError，整个文件（连带其余 10 个用例）长期没被执行过。
#
# 下面统一用 Apprise URL 作为订阅目标；旧格式的兼容行为由两个 legacy 用例覆盖。


def test_add_and_list(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    assert s.list("feed1") == []
    assert s.add("feed1", "mailto://me@example.com") == "added"
    assert s.list("feed1") == ["mailto://me@example.com"]
    assert (tmp_path / "subs.json").exists()


def test_add_duplicate(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    s.add("f", "mailto://a@b.com")
    assert s.add("f", "  mailto://a@b.com  ") == "exists"   # whitespace-insensitive dup
    assert s.list("f") == ["mailto://a@b.com"]


def test_add_invalid(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    assert s.add("f", "not-a-target") == "invalid"          # 无 scheme://
    assert s.add("f", "") == "invalid"
    assert s.list("f") == []


def test_feeds_are_independent(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    s.add("a", "mailto://x@y.com")
    s.add("b", "mailto://z@y.com")
    assert s.list("a") == ["mailto://x@y.com"]
    assert s.list("b") == ["mailto://z@y.com"]


def test_remove(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    s.add("f", "mailto://a@b.com")
    assert s.remove("f", "mailto://a@b.com") is True
    assert s.list("f") == []
    assert s.remove("f", "mailto://a@b.com") is False


def test_by_target_reverse_view(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    s.add("feedA", "mailto://x@y.com", 6)
    s.add("feedB", "mailto://x@y.com")      # 同一目标 -> 保留它的 6h
    s.add("feedA", "json://z@y.com", 12)
    assert s.by_email() == {
        "mailto://x@y.com": {"feeds": ["feedA", "feedB"], "hours": 6},
        "json://z@y.com": {"feeds": ["feedA"], "hours": 12},
    }


@pytest.mark.parametrize("value,expected", [
    (6, 6), ("12", 12), (None, 24), ("", 24), ("abc", 24), (0, 24), (-3, 24), (1.5, 1.5),
])
def test_normalize_hours(value, expected):
    assert normalize_hours(value) == expected


def test_frequency_is_target_level_set_once(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    s.add("feedA", "mailto://a@b.com", 6)
    s.add("feedB", "mailto://a@b.com", 100)  # 二次订阅不改变该目标的频率
    assert s.freq("mailto://a@b.com") == 6
    assert s.items("feedA") == {"mailto://a@b.com": 6}
    assert s.items("feedB") == {"mailto://a@b.com": 6}


def test_set_freq_updates_existing_only(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    assert s.set_freq("mailto://nobody@x.com", 8) is False   # 不是订阅目标
    s.add("f", "mailto://a@b.com", 6)
    assert s.set_freq("mailto://a@b.com", 12) is True
    assert s.freq("mailto://a@b.com") == 12


def test_remove_forgets_freq_when_fully_unsubscribed(tmp_path):
    s = Subscribers(str(tmp_path / "subs.json"))
    s.add("a", "mailto://x@y.com", 6)
    s.add("b", "mailto://x@y.com")
    s.remove("a", "mailto://x@y.com")
    assert s.freq("mailto://x@y.com") == 6    # 仍订阅着 b
    s.remove("b", "mailto://x@y.com")
    assert s.freq("mailto://x@y.com") == 24   # 全部退订 -> 回到默认值


def test_legacy_list_format_migrates_to_mailto(tmp_path):
    """旧数据里存的是裸邮箱，读取时应迁移成 mailto:// 且频率取默认。"""
    p = tmp_path / "subs.json"
    p.write_text(json.dumps({"f": ["a@b.com", "c@d.com"]}), encoding="utf-8")
    s = Subscribers(str(p))
    assert s.items("f") == {"mailto://a@b.com": 24, "mailto://c@d.com": 24}
    assert s.list("f") == ["mailto://a@b.com", "mailto://c@d.com"]


def test_legacy_dict_format_derives_frequency(tmp_path):
    p = tmp_path / "subs.json"
    p.write_text(json.dumps({"f": {"a@b.com": 6}}), encoding="utf-8")
    s = Subscribers(str(p))
    assert s.freq("mailto://a@b.com") == 6 and s.list("f") == ["mailto://a@b.com"]
