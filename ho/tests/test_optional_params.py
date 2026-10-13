"""Regression test for i2mint/ho#1: OpenAPI-optional parameters must be optional."""

import inspect

from ho import routes_to_funcs

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "t", "version": "1"},
    "paths": {
        "/items/{item_id}": {
            "get": {
                "parameters": [
                    {
                        "name": "item_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {"name": "first", "in": "query", "schema": {"type": "integer"}},
                    {"name": "role", "in": "query", "schema": {"type": "string"}},
                ],
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}


class _FakeResponse:
    status_code = 200
    ok = True
    text = "{}"

    def json(self):
        return {}

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse()

    post = put = delete = patch = get


def test_optional_openapi_params_are_optional():
    session = _FakeSession()
    funcs = routes_to_funcs(SPEC, "http://example.com", session=session)
    (func,) = funcs.values()
    params = inspect.signature(func).parameters
    assert params["item_id"].default is inspect.Parameter.empty
    assert params["first"].default is None
    assert params["role"].default is None

    func("abc", first=1)  # used to raise: missing a required argument: 'role'
    (call,) = session.calls
    assert call["url"] == "http://example.com/items/abc"
    assert call["params"] == {"first": 1}  # None-valued optionals are not sent


# --- i2mint/ho#2: names that are not identifiers, and header parameters ---

RENAMING_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "t", "version": "1"},
    "paths": {
        "/things/{thingId}": {
            "post": {
                "parameters": [
                    {
                        "name": "thingId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {"name": "$first", "in": "query", "schema": {"type": "integer"}},
                    {"name": "pageSize", "in": "query", "schema": {"type": "integer"}},
                    {"name": "X-MS-API-ROLE", "in": "header", "schema": {"type": "string"}},
                    {"name": "session-id", "in": "cookie", "schema": {"type": "string"}},
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"displayName": {"type": "string"}},
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}


def _renaming_func():
    session = _FakeSession()
    (func,) = routes_to_funcs(RENAMING_SPEC, "http://example.com", session=session).values()
    return func, session


def test_renamed_params_are_sent_under_their_spec_names():
    func, session = _renaming_func()
    names = func.openapi_param_names
    py = {spec: name for name, spec in names.items()}
    func(
        **{
            py["thingId"]: "t 1",
            py["$first"]: 5,
            py["pageSize"]: 20,
            py["X-MS-API-ROLE"]: "admin",
            py["session-id"]: "s1",
            py["displayName"]: "Thing",
        }
    )
    (call,) = session.calls
    assert call["url"] == "http://example.com/things/t%201"
    assert call["params"] == {"$first": 5, "pageSize": 20}
    assert call["headers"]["X-MS-API-ROLE"] == "admin"
    assert call["cookies"] == {"session-id": "s1"}
    assert call["json"] == {"displayName": "Thing"}, "only body properties in the body"


def test_omitted_header_and_query_params_are_not_sent():
    func, session = _renaming_func()
    py = {spec: name for name, spec in func.openapi_param_names.items()}
    func(**{py["thingId"]: "x"})
    (call,) = session.calls
    assert call["params"] == {}
    assert "X-MS-API-ROLE" not in call["headers"]
    assert "cookies" not in call


def test_the_mapping_is_exposed_and_documented():
    func, _ = _renaming_func()
    names = func.openapi_param_names
    assert set(names.values()) >= {"$first", "X-MS-API-ROLE", "pageSize", "thingId"}
    assert all(name.isidentifier() for name in names)
    py_first = next(n for n, spec in names.items() if spec == "$first")
    assert f"{py_first} (sent as '$first')" in func.__doc__
