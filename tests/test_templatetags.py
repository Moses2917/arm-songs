from hymns.templatetags.hymns_extras import qs_without_page


def test_qs_without_page_removes_page_key():
    assert qs_without_page("q=love&page=3&book=New") == "q=love&book=New"


def test_qs_without_page_handles_empty_input():
    assert qs_without_page("") == ""
    assert qs_without_page(None) == ""


def test_qs_without_page_without_page_key_returns_input():
    # parse_qsl + urlencode preserve insertion order
    assert qs_without_page("book=New&q=love") == "book=New&q=love"


def test_qs_without_page_keeps_blank_values():
    assert qs_without_page("q=&book=New") == "q=&book=New"


def test_qs_without_page_only_page_present():
    assert qs_without_page("page=5") == ""


def test_qs_without_page_strips_multiple_page_keys():
    assert qs_without_page("page=1&q=x&page=2") == "q=x"
