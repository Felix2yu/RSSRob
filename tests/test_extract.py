import pytest

from rssrob.extract import parse_selector, validate_selector, extract_items


def test_parse_css_default():
    s = parse_selector("h2 a")
    assert s.engine == "css" and s.expr == "h2 a" and s.attr is None


def test_parse_css_prefix_and_attr():
    s = parse_selector("css:h2 a@href")
    assert s.engine == "css" and s.expr == "h2 a" and s.attr == "href"


def test_parse_xpath_keeps_native_attr_axis():
    s = parse_selector("xpath:.//a/@href")
    assert s.engine == "xpath" and s.expr == ".//a/@href" and s.attr is None


def test_parse_xpath_predicate_not_split_as_attr():
    s = parse_selector("xpath://div[@class='bd']//li")
    assert s.engine == "xpath" and s.expr == "//div[@class='bd']//li" and s.attr is None


def test_validate_selector_accepts_valid():
    validate_selector("css:div.post a@href")
    validate_selector("xpath://h2[normalize-space()='x']/ancestor::div[1]//li")


def test_validate_selector_rejects_garbage():
    with pytest.raises(ValueError):
        validate_selector("xpath://[[[broken")


BASE = "http://www.ipp.cas.cn/"

ITEM_XPATH = (
    "xpath://h2[normalize-space()='通知公告']"
    "/ancestor::div[contains(@class,'ipp2020-item')][1]//div[@class='bd']//ul/li"
)
FIELDS = {"title": "xpath:.//a", "link": "xpath:.//a/@href", "date": "xpath:.//span"}


def test_extract_xpath_heading_anchor(fixtures):
    html = (fixtures / "notices.html").read_text(encoding="utf-8")
    items = extract_items(html, BASE, ITEM_XPATH, FIELDS)
    assert len(items) == 2                       # 学术报告 block excluded
    assert items[0].title == "通知一"             # text stripped, <img> ignored
    assert items[0].link == "http://www.ipp.cas.cn/tzgg/1.html"  # absolute
    assert items[0].date == "06-15"
    assert items[0].id == items[0].link          # id defaults to link


def test_extract_css_with_attr_suffix(fixtures):
    html = (fixtures / "notices.html").read_text(encoding="utf-8")
    items = extract_items(
        html, BASE,
        "css:.ipp2020-item-4 .bd li",
        {"title": "css:a", "link": "css:a@href"},
    )
    assert len(items) == 3                        # css class matches both blocks
    assert items[0].link == "http://www.ipp.cas.cn/other/x.html"


def test_extract_missing_field_is_none(fixtures):
    html = (fixtures / "notices.html").read_text(encoding="utf-8")
    items = extract_items(html, BASE, ITEM_XPATH,
                          {"title": "xpath:.//a", "missing": "css:.nope"})
    assert items[0].title == "通知一"
    assert getattr(items[0], "title") is not None
    # the unknown field simply does not become a known Item attribute / stays None
    assert items[0].summary is None
