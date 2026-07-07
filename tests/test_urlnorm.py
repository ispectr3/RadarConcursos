from urlnorm import normalize_url


def test_normalize_url_strips_fragment():
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_normalize_url_removes_www():
    assert normalize_url("https://www.example.com/page") == "https://example.com/page"


def test_normalize_url_upgrades_http():
    assert normalize_url("http://example.com/page") == "https://example.com/page"


def test_normalize_url_lowercases():
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


def test_normalize_url_standardizes_trailing_slash():
    norm = normalize_url("https://example.com/page/")
    assert norm == "https://example.com/page"


def test_normalize_url_strips_query():
    assert normalize_url("https://example.com/page?q=1") == "https://example.com/page"


def test_normalize_url_invalid_returns_raw():
    assert normalize_url("not a url") == "not a url"
