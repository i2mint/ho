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
