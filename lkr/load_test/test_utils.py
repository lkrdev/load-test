from lkr.load_test.utils import (
    check_random_int_format,
    format_attributes,
    get_user_id,
    get_dashboard_load_test_system_activity_explore_url,
)


def test_check_random_int_format_valid():
    # Test valid random.randint format
    is_valid, value = check_random_int_format("random.randint(0,100)")
    assert is_valid is True
    assert value.isdigit()
    assert 0 <= int(value) <= 100

    is_valid, value = check_random_int_format("random.randint(1000,2000)")
    assert is_valid is True
    assert value.isdigit()
    assert 1000 <= int(value) <= 2000

    is_valid, value = check_random_int_format("random.randint(0.2,1000000)")
    assert is_valid is False
    assert value is None


def test_check_random_int_format_invalid():
    # Test invalid formats
    test_cases = [
        "random.randint(a,100)",  # Non-integer arguments
        "random.randint(0,b)",  # Non-integer arguments
        "random.randint(0,100",  # Missing closing parenthesis
        "random.randint(0)",  # Missing second argument
        "random.randint",  # Missing arguments
        "random.randint()",  # Empty arguments
        "something_else",  # Completely different format
        "random.randint(0, 100)",  # Extra spaces (not matching exact format)
    ]

    for test_case in test_cases:
        is_valid, value = check_random_int_format(test_case)
        assert is_valid is False
        assert value is None


def test_format_attributes():
    # Test with valid random.randint attributes
    attributes = ["key1:random.randint(0,100)", "key2:random.randint(1000,2000)"]
    formatted = format_attributes(attributes)
    print(formatted)
    assert len(formatted) == 2
    assert int(formatted["key1"]) >= 0 and int(formatted["key1"]) <= 100
    assert int(formatted["key2"]) >= 1000 and int(formatted["key2"]) <= 2000

    # Test with empty list
    assert format_attributes([]) == {}

    # Test with invalid attributes
    invalid_attributes = [
        "key1",  # Missing value
        "key2:",  # Empty value
        ":value",  # Missing key
        ":",  # Empty key and value
    ]
    formatted = format_attributes(invalid_attributes)
    assert formatted == {}


def test_get_user_id():
    user_id = get_user_id()
    assert user_id.startswith("embed-")
    assert len(user_id) == 16  # "embed-" + 10 digits
    assert user_id[6:].isdigit()  # Check if the part after "embed-" is all digits

    # Test uniqueness
    user_ids = [get_user_id() for _ in range(100)]
    assert len(set(user_ids)) == 100  # All IDs should be unique


def test_get_dashboard_load_test_system_activity_explore_url(monkeypatch):
    # Mock environment variable
    monkeypatch.setenv("LOOKERSDK_BASE_URL", "https://myinstance.looker.com")

    from urllib.parse import urlparse, parse_qs
    import json

    url = get_dashboard_load_test_system_activity_explore_url(5)
    assert url is not None

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "myinstance.looker.com"
    assert parsed.path == "/explore/system__activity/history"

    query_params = parse_qs(parsed.query)
    assert query_params["fields"] == ["history.created_minute,history.query_run_count,user.count"]
    assert "pivots" not in query_params
    assert query_params["fill_fields"] == ["history.created_minute"]
    assert query_params["sorts"] == ["history.created_minute"]
    assert query_params["limit"] == ["500"]
    assert query_params["column_limit"] == ["50"]

    # Check that the filter string is format "YYYY/MM/DD HH:MM to YYYY/MM/DD HH:MM"
    created_minute_filter = query_params["f[history.created_minute]"][0]
    import re
    assert re.match(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2} to \d{4}/\d{2}/\d{2} \d{2}:\d{2}$", created_minute_filter)

    # Check that filter_config JSON is valid
    filter_config = json.loads(query_params["filter_config"][0])
    assert "history.created_minute" in filter_config
    filters = filter_config["history.created_minute"]
    assert len(filters) == 1
    assert filters[0]["type"] == "between"
    assert filters[0]["id"] == 1
    assert "date" in filters[0]["values"][0]
    assert "date" in filters[0]["values"][1]
    assert filters[0]["values"][0]["tz"] is True
    assert filters[0]["values"][1]["tz"] is True
    assert "f[history.real_dash_id]" not in query_params


def test_get_dashboard_load_test_system_activity_explore_url_single_dashboard(monkeypatch):
    monkeypatch.setenv("LOOKERSDK_BASE_URL", "https://myinstance.looker.com")

    from urllib.parse import urlparse, parse_qs

    url = get_dashboard_load_test_system_activity_explore_url(5, ["1"])
    assert url is not None

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    assert query_params["fields"] == ["history.created_minute,history.query_run_count,user.count"]
    assert "pivots" not in query_params
    assert query_params["f[history.real_dash_id]"] == ["1"]


def test_get_dashboard_load_test_system_activity_explore_url_with_dashboards(monkeypatch):
    # Mock environment variable
    monkeypatch.setenv("LOOKERSDK_BASE_URL", "https://myinstance.looker.com")

    from urllib.parse import urlparse, parse_qs
    import json

    url = get_dashboard_load_test_system_activity_explore_url(5, ["1", "2", "3"])
    assert url is not None

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "myinstance.looker.com"
    assert parsed.path == "/explore/system__activity/history"

    query_params = parse_qs(parsed.query)
    assert query_params["fields"] == ["history.created_minute,history.query_run_count,user.count,dashboard.title"]
    assert query_params["pivots"] == ["dashboard.title"]
    assert query_params["f[history.real_dash_id]"] == ["1,2,3"]

    # Check that filter_config JSON is valid and has history.real_dash_id
    filter_config = json.loads(query_params["filter_config"][0])
    assert "history.real_dash_id" in filter_config
    filters = filter_config["history.real_dash_id"]
    assert len(filters) == 1
    assert filters[0]["type"] == "="
    assert filters[0]["id"] == 2
    assert filters[0]["values"][0]["constant"] == "1,2,3"
