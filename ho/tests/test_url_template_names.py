"""Query parameters are sent under the template's key, not the placeholder's
(i2mint/ho#10)."""

import inspect

import pytest

from ho.base import url_template_to_func, url_template_to_openapi
from ho.tests.test_optional_params import _FakeSession


def _call(template, *args, **kwargs):
    session = _FakeSession()
    func = url_template_to_func(template, session=session)
    func(*args, **kwargs)
    (call,) = session.calls
    return func, call


def test_query_key_is_sent_and_placeholder_is_the_argument():
    func, call = _call("https://www.google.com/search?q={search_term}", "Python")
    assert list(inspect.signature(func).parameters) == ["search_term"]
    assert call["params"] == {"q": "Python"}


def test_spec_parameter_is_named_after_the_key():
    spec = url_template_to_openapi("https://x.org/s?q={term}")
    (param,) = spec["paths"]["/s"]["get"]["parameters"]
    assert param["name"] == "q"


def test_defaults_and_types_follow_the_placeholder():
    session = _FakeSession()
    func = url_template_to_func(
        "https://x.org/items/{id}?page_size={size:10}&flag={on:true}",
        param_types={"size": "integer"},
        session=session,
    )
    sig = inspect.signature(func)
    assert list(sig.parameters) == ["id", "size", "on"]
    assert sig.parameters["size"].default == "10"
    func("a", size=5)
    (call,) = session.calls
    assert call["url"].endswith("/items/a")
    assert call["params"] == {"page_size": 5, "flag": "true"}


def test_same_name_keys_and_placeholders_are_unchanged():
    _, call = _call("https://x.org/s?q={q}", "v")
    assert call["params"] == {"q": "v"}


def test_names_can_be_swapped():
    func, call = _call("https://x.org/s?b={a}&q={b}", 1, 2)
    assert list(inspect.signature(func).parameters) == ["a", "b"]
    assert call["params"] == {"b": 1, "q": 2}
    func, call = _call("https://x.org/s?q={term}&term={q}", 1, 2)
    assert call["params"] == {"q": 1, "term": 2}


def test_a_key_used_twice_is_refused():
    with pytest.raises(ValueError, match="used 2 times"):
        url_template_to_func("https://x.org/s?q={a}&q={b}")


def test_a_placeholder_in_a_query_key_is_refused():
    with pytest.raises(ValueError, match="query key"):
        url_template_to_func("https://x.org/s?{k}=v")


# --- literal parts of the query, and arguments used in several places (ho#14) ---


def test_static_query_parts_are_always_sent():
    func, call = _call("https://x.org/s?lang=en&q={term}&flag=", "py")
    assert list(inspect.signature(func).parameters) == ["term"]
    assert call["params"] == {"lang": "en", "flag": "", "q": "py"}


def test_a_value_with_text_around_the_placeholder():
    func, call = _call("https://x.org/s?q=lang:{x}&r={lo}-{hi:9}", "py", 1)
    assert list(inspect.signature(func).parameters) == ["x", "lo", "hi"]
    assert call["params"] == {"q": "lang:py", "r": "1-9"}


def test_a_composed_value_formats_booleans_like_other_query_values():
    _, call = _call("https://x.org/s?q=is:{on}", True)
    assert call["params"] == {"q": "is:true"}


def test_one_placeholder_in_two_keys_is_one_argument_sent_twice():
    func, call = _call("https://x.org/s?a={x}&b={x}", "v")
    assert list(inspect.signature(func).parameters) == ["x"]
    assert call["params"] == {"a": "v", "b": "v"}


def test_a_path_placeholder_reused_in_the_query_is_one_argument():
    func, call = _call("https://x.org/i/{id}?item={id}", "7")
    assert list(inspect.signature(func).parameters) == ["id"]
    assert call["url"].endswith("/i/7") and call["params"] == {"item": "7"}
    func, call = _call("https://x.org/i/{id}?id={id}", "7")
    assert list(inspect.signature(func).parameters) == ["id"]
    assert call["url"].endswith("/i/7") and call["params"] == {"id": "7"}


def test_a_placeholder_alone_and_inside_a_composed_value():
    func, call = _call("https://x.org/s?a={x}&b=<{x}>", "v")
    assert list(inspect.signature(func).parameters) == ["x"]
    assert call["params"] == {"a": "v", "b": "<v>"}
    func, call = _call("https://x.org/s?b=<{x}>&a={x}", "v")
    assert call["params"] == {"a": "v", "b": "<v>"}


# --- the review's repros ---


def test_placeholders_that_are_not_identifiers():
    func, call = _call("https://x.org/s?a={item-id}&b={item-id}", "v")
    assert list(inspect.signature(func).parameters) == ["item_id"]
    assert call["params"] == {"a": "v", "b": "v"}
    func, call = _call("https://x.org/i/{class}?c={class}", "7")
    assert call["params"] == {"c": "7"} and call["url"].endswith("/i/7")
    func, call = _call("https://x.org/s?r={a-b}-x", "v")
    assert call["params"] == {"r": "v-x"}
    _, call = _call("https://x.org/s?r={class}-x", "v")
    assert call["params"] == {"r": "v-x"}


def test_a_composed_placeholder_named_like_another_query_key():
    func, call = _call("https://x.org/s?lo={a}&r={lo}-x", "A", "L")
    assert list(inspect.signature(func).parameters) == ["a", "lo"]
    assert call["params"] == {"lo": "A", "r": "L-x"}
    _, call = _call("https://x.org/s?lo={a}&r={lo}-x&s={lo}", "A", "L")
    assert call["params"] == {"lo": "A", "r": "L-x", "s": "L"}


def test_a_part_used_in_two_values_is_one_argument():
    spec = url_template_to_openapi("https://x.org/s?r={a}-x&s={a}-y")
    params = spec["paths"]["/s"]["get"]["parameters"]
    assert len({(p["name"], p["in"]) for p in params}) == len(params)  # valid OpenAPI
    func, call = _call("https://x.org/s?r={a}-x&s={a}-y", "v")
    assert list(inspect.signature(func).parameters) == ["a"]
    assert call["params"] == {"r": "v-x", "s": "v-y"}


def test_lists_in_a_composed_value_are_comma_joined():
    _, call = _call("https://x.org/s?q=is:{l}", ["a", True])
    assert call["params"] == {"q": "is:a,true"}
    with pytest.raises(TypeError, match="dict"):
        _call("https://x.org/s?q=is:{d}", {"k": 1})


@pytest.mark.parametrize(
    "template",
    ["https://x.org/s?q={x:a&b}", "https://x.org/s?q={x", "https://x.org/s?q=x}"],
)
def test_malformed_placeholders_are_refused(template):
    with pytest.raises(ValueError, match="Malformed"):
        url_template_to_func(template)


def test_conflicting_inline_defaults_are_refused():
    with pytest.raises(ValueError, match="two defaults"):
        url_template_to_func("https://x.org/s?q={x:1}&r={x:2}-z")
    func, call = _call("https://x.org/s?q={x:1}&r={x:1}-z")
    assert call["params"] == {"q": "1", "r": "1-z"}
