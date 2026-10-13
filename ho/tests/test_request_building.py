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
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "get": {
                "parameters": [
                    {"name": "active", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "tags", "in": "query", "schema": {"type": "array"}},
                    {
                        "name": "Content-Type",
                        "in": "header",
                        "schema": {"type": "string"},
                    },
                ],
                "requestBody": BODY,
            },
            "post": {
                "parameters": [
                    {
                        "name": "name",
                        "in": "query",
                        "description": "a filter",
                        "schema": {"type": "string"},
                    },
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


def test_content_type_header_parameters_are_not_arguments(api):
    """OpenAPI: Accept, Content-Type and Authorization header parameters are ignored."""
    import inspect

    funcs, session = api
    func = funcs["get", "/items/{id}"]
    assert "content_type" not in inspect.signature(func).parameters
    func("x", name="n")
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


def test_a_session_only_needs_the_method_the_route_uses():
    from types import SimpleNamespace

    calls = []
    session = SimpleNamespace(get=lambda **kw: calls.append(kw) or _FakeSession().get())
    spec = {"openapi": "3.0.0", "paths": {"/p": {"get": {"responses": {}}}}}
    routes_to_funcs(spec, "http://e.com", session=session)["get", "/p"]()
    assert calls[0]["url"] == "http://e.com/p"


_FORMS_SPEC = {
    "openapi": "3.0.0",
    "paths": {
        "/form/{flag}": {
            "post": {
                "parameters": [
                    {
                        "name": "flag",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "boolean"},
                    },
                    {
                        "name": "Accept",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "Authorization",
                        "in": "header",
                        "schema": {"type": "string"},
                    },
                ],
                "requestBody": {
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "properties": {
                                    "on": {"type": "boolean"},
                                    "tags": {"type": "array"},
                                }
                            }
                        }
                    }
                },
            }
        },
        "/upload": {
            "post": {
                "requestBody": {
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "properties": {
                                    "file": {"type": "string"},
                                    "n": {"type": "integer"},
                                }
                            }
                        }
                    }
                }
            }
        },
    },
}


@pytest.fixture
def forms():
    session = _FakeSession()
    return routes_to_funcs(_FORMS_SPEC, "http://e.com", session=session), session


def test_path_booleans_and_lists_are_serialised_not_str_ed(forms):
    funcs, session = forms
    funcs["post", "/form/{flag}"](True)
    assert session.calls[0]["url"] == "http://e.com/form/true"


def test_ignored_header_parameters_are_dropped_from_the_signature(forms):
    import inspect

    funcs, _ = forms
    names = set(inspect.signature(funcs["post", "/form/{flag}"]).parameters)
    assert not {"accept", "authorization"} & names


def test_a_form_body_is_sent_as_form_data_without_a_json_content_type(forms):
    funcs, session = forms
    funcs["post", "/form/{flag}"](False, on=True, tags=["a", "b"])
    call = session.calls[0]
    assert call["data"] == {"on": "true", "tags": ["a", "b"]}
    assert "json" not in call and "Content-Type" not in call["headers"]


def test_a_multipart_body_is_sent_as_files(forms):
    funcs, session = forms
    funcs["post", "/upload"](file=b"bytes", n=3)
    call = session.calls[0]
    assert call["files"] == [("file", ("file", b"bytes")), ("n", (None, "3"))]
    assert "json" not in call and "Content-Type" not in call["headers"]


def test_a_path_parameter_that_does_not_say_where_is_found_in_the_url():
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/i/{id}": {
                "get": {"parameters": [{"name": "id", "schema": {"type": "string"}}]}
            }
        },
    }
    session = _FakeSession()
    routes_to_funcs(spec, "http://e.com", session=session)["get", "/i/{id}"]("7")
    assert session.calls[0]["url"] == "http://e.com/i/7"


def test_multipart_files_get_a_filename_and_lists_one_part_per_item():
    import io

    from ho.base import _multipart_fields

    handle = io.BytesIO(b"x")
    handle.name = "/tmp/dir/report.csv"
    assert _multipart_fields({"f": handle, "t": ["a", "b"], "o": {"k": [1]}}) == [
        ("f", ("report.csv", handle)),
        ("t", (None, "a")),
        ("t", (None, "b")),
        ("o", (None, '{"k": [1]}')),
    ]


def test_form_objects_are_sent_as_json_text(forms):
    funcs, session = forms
    funcs["post", "/form/{flag}"](True, on=False, tags=[{"k": 1}])
    assert session.calls[0]["data"] == {"on": "false", "tags": ['{"k": 1}']}


def test_a_path_parameter_without_in_is_found_even_when_its_name_clashes():
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/u/{id}": {
                "post": {
                    "parameters": [
                        {
                            "name": "id",
                            "description": "THE ID",
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"properties": {"id": {"type": "string"}}}
                            }
                        }
                    },
                }
            }
        },
    }
    session = _FakeSession()
    func = routes_to_funcs(spec, "http://x", session=session)["post", "/u/{id}"]
    func("A", id_body="B")
    call = session.calls[0]
    assert call["url"] == "http://x/u/A" and call["json"] == {"id": "B"}
    assert "id: THE ID" in func.__doc__


def test_a_route_like_without_body_content_type_still_works():
    from ju.oas import Routes

    route = Routes(SPEC)["get", "/items/{id}"]

    class RouteLike:
        def __init__(self, route):
            self.__dict__.update(
                method=route.method,
                endpoint=route.endpoint,
                params=route.params,
                input_specs=route.input_specs,
                method_data=route.method_data,
            )

    session = _FakeSession()
    from ho import route_to_func

    f = route_to_func(
        RouteLike(route),
        "http://e.com",
        route_maker=lambda route_like: route_like,
        session=session,
    )
    f("x", name="n")
    assert session.calls[0]["url"] == "http://e.com/items/x"
