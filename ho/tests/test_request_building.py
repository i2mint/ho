"""Request-building gaps (i2mint/ho#6) and same-name parameters (i2mint/ju#20)."""

import pytest

from ho import routes_to_funcs
from ho.tests.test_optional_params import _FakeSession

BODY = {
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "the thing's name"},
                    "pageSize": {"type": "integer"},
                },
            }
        }
    }
}

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "t", "version": "1"},
    "paths": {
        "/items/{id}": {
            "parameters": [  # shared by every operation of the path item
                {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "get": {
                "parameters": [
                    {"name": "active", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "tags", "in": "query", "schema": {"type": "array"}},
                    {"name": "Content-Type", "in": "header", "schema": {"type": "string"}},
                ],
                "requestBody": BODY,
            },
            "post": {
                "parameters": [
                    {"name": "name", "in": "query", "description": "a filter", "schema": {"type": "string"}},
                    {"name": "id", "in": "header", "schema": {"type": "integer"}},
                ],
                "requestBody": BODY,
            },
        }
    },
}


@pytest.fixture
def api():
    session = _FakeSession()
    funcs = routes_to_funcs(SPEC, "http://example.com", session=session)
    return funcs, session


def test_a_path_item_parameter_fills_the_url(api):
    funcs, session = api
    funcs["get", "/items/{id}"]("abc", name="n")
    assert session.calls[0]["url"] == "http://example.com/items/abc"


def test_a_path_parameter_cannot_be_none(api):
    funcs, session = api
    with pytest.raises(ValueError, match="'id'"):
        funcs["get", "/items/{id}"](None, name="n")
    assert session.calls == []


def test_a_slash_in_a_path_value_is_escaped(api):
    funcs, session = api
    funcs["get", "/items/{id}"]("a/b c", name="n")
    assert session.calls[0]["url"] == "http://example.com/items/a%2Fb%20c"


def test_booleans_in_the_query_are_json_style(api):
    funcs, session = api
    funcs["get", "/items/{id}"]("x", name="n", active=False, tags=[True, "a"])
    assert session.calls[0]["params"] == {"active": "false", "tags": ["true", "a"]}


def test_a_get_with_body_arguments_sends_them(api):
    funcs, session = api
    funcs["get", "/items/{id}"]("x", name="n")
    assert session.calls[0]["json"] == {"name": "n"}


def test_a_get_without_body_arguments_sends_no_body(api):
    funcs, session = api
    spec = {**SPEC, "paths": {"/p": {"get": {"responses": {}}}}}
    session = _FakeSession()
    routes_to_funcs(spec, "http://e.com", session=session)["get", "/p"]()
    assert "json" not in session.calls[0]


def test_a_content_type_header_parameter_does_not_replace_the_json_one(api):
    funcs, session = api
    funcs["get", "/items/{id}"]("x", name="n", content_type="text/plain")
    assert session.calls[0]["headers"]["Content-Type"] == "application/json"


def test_same_name_in_query_and_body_go_to_their_own_places(api):
    funcs, session = api
    func = funcs["post", "/items/{id}"]
    funcs_args = list(func.openapi_param_names.items())
    assert ("name_body", "name") in funcs_args and ("id_header", "id") in funcs_args
    func("x", name="Q", name_body="B", id_header=7)
    call = session.calls[0]
    assert call["url"] == "http://example.com/items/x"
    assert call["params"] == {"name": "Q"}
    assert call["json"] == {"name": "B"}
    assert call["headers"]["id"] == "7"


def test_the_docstring_lists_body_properties_and_renames(api):
    funcs, _ = api
    doc = funcs["post", "/items/{id}"].__doc__
    assert "name_body (sent as 'name'): the thing's name" in doc
    assert "name: a filter" in doc
    assert "pageSize" in doc
