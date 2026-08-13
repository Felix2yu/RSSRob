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


# --- JSON path extraction (pageapi) -----------------------------------------

from rssrob.extract import (extract_json_items, json_get, render_json_template,
                            validate_json_selector)

MAITIX_DOC = {
    "code": 200, "success": True,
    "data": {"totalRow": 2, "dataList": [
        {"projectToken": "A1", "projectName": "话剧《茶馆》", "aliasName": "茶馆",
         "projectTypeName": "话剧", "cityName": "苏州", "minPrice": 80, "maxPrice": 580,
         "startTime": "2026-09-01 19:30", "imgUrl": "https://cdn/img/a.jpg"},
        {"projectToken": "B2", "projectName": "交响音乐会", "projectTypeName": "音乐会",
         "startTime": "2026-09-05 20:00"},
    ]},
}


def test_json_get_dotted_and_indexed():
    assert json_get(MAITIX_DOC, "$.data.dataList[0].projectName") == "话剧《茶馆》"
    assert json_get(MAITIX_DOC, "$.data.totalRow") == 2
    assert json_get(MAITIX_DOC, "$.data.dataList[5]") is None      # out of range
    assert json_get(MAITIX_DOC, "$.missing.key") is None           # missing key
    assert json_get(MAITIX_DOC, "$.data.dataList[0].minPrice") == 80  # numbers kept raw


def test_json_get_rejects_bad_paths():
    with pytest.raises(ValueError):
        json_get(MAITIX_DOC, "data.dataList")       # must start with $
    with pytest.raises(ValueError):
        json_get(MAITIX_DOC, "$.a[[[")              # malformed segment


def test_validate_json_selector():
    validate_json_selector("$.data.dataList[0].name")
    with pytest.raises(ValueError):
        validate_json_selector("dataList")
    with pytest.raises(ValueError):
        validate_json_selector("$.a[0]x")


def test_render_json_template():
    row = MAITIX_DOC["data"]["dataList"][0]
    out = render_json_template(
        "https://szwtfz.maitix.com/h5/#/pages-order/projectDetail/index?projectId={$.projectToken}",
        row)
    assert out.endswith("projectId=A1")
    assert render_json_template("x-{$.missing}", row) == "x-"


def test_extract_json_items_maitix_shape():
    fields = {
        "title": "$.projectName",
        "link": "https://szwtfz.maitix.com/h5/#/pages-order/projectDetail/index?projectId={$.projectToken}",
        "date": "$.startTime",
        "category": "$.projectTypeName",
    }
    items = extract_json_items(MAITIX_DOC, "$.data.dataList", fields)
    assert len(items) == 2
    first = items[0]
    assert first.id == ("https://szwtfz.maitix.com/h5/#/pages-order/"
                        "projectDetail/index?projectId=A1")
    assert first.title == "话剧《茶馆》"
    assert first.date == "2026-09-01 19:30"
    assert first.category == "话剧"
    assert items[1].category == "音乐会"


def test_extract_json_items_not_a_list_raises():
    with pytest.raises(ValueError):
        extract_json_items(MAITIX_DOC, "$.data.totalRow", {"title": "$.x"})
