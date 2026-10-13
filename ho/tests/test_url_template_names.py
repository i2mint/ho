"""Query parameters are sent under the template's key, not the placeholder's
(i2mint/ho#10)."""

import inspect

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


def test_a_key_used_twice_keeps_the_later_placeholder_name():
    _, call = _call("https://x.org/s?q={a}&q={b}", "1", "2")
    assert call["params"] == {"q": "1", "b": "2"}
