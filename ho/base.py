"""HO base objects"""

import json
import os
import re
from typing import Optional
from collections.abc import Callable
from urllib.parse import urlparse, parse_qs, quote

import requests

from ju.json_schema import (
    OAS_IN_KEY,
    OAS_NAME_KEY,
    json_schema_to_signature,
    schema_param_names,
)
from ju.oas import BODY_IN, PARAM_IN, Route, Routes

from ho.util import SimpleMappingNamespace

#: A parameter schema's ``x-python-name`` is the name of the Python argument to
#: send under the parameter's own (spec) name, e.g. the placeholder ``search_term``
#: of ``?q={search_term}``.
PYTHON_NAME_KEY = "x-python-name"
#: A query parameter's schema says ``x-ho-composed-into: <key>`` when it is one
#: placeholder of a query value that has more in it (``?r={lo}-{hi}``); the
#: operation's ``x-ho-query-templates`` holds that value's template (``{lo}-{hi}``).
COMPOSED_INTO_KEY = "x-ho-composed-into"
QUERY_TEMPLATES_KEY = "x-ho-query-templates"
#: The operation's constant query parameters (``?lang=en``), sent on every request.
STATIC_QUERY_KEY = "x-ho-static-query"
_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def update_spec(
    spec,
    path,
    method,
    description=None,
    param_types=None,
    param_descriptions=None,
    param_defaults=None,
    response_schema=None,
):
    """
    Update an OpenAPI spec with provided parameters for a specific path and method.

    Parameters:
    -----------
    spec : dict
        The original OpenAPI specification.
    path : str
        The endpoint path.
    method : str
        The HTTP method.
    description : str, optional
        New description to set.
    param_types : dict, optional
        Parameter types to update.
    param_descriptions : dict, optional
        Parameter descriptions to update.
    param_defaults : dict, optional
        Parameter defaults to update.
    response_schema : dict, optional
        Response schema to update.

    Returns:
    --------
    dict
        Updated OpenAPI specification.
    """
    import copy

    updated_spec = copy.deepcopy(spec)  # Avoid modifying the original
    endpoint_spec = updated_spec["paths"][path][method.lower()]

    if description:
        endpoint_spec["summary"] = description

    if any([param_types, param_descriptions, param_defaults]):
        if "parameters" not in endpoint_spec:
            endpoint_spec["parameters"] = []

        # Update existing parameters
        for param in endpoint_spec["parameters"]:
            name = param["name"]
            if param_types and name in param_types:
                param["schema"]["type"] = param_types[name]
            if param_descriptions and name in param_descriptions:
                param["description"] = param_descriptions[name]
            if param_defaults and name in param_defaults:
                if "schema" not in param:
                    param["schema"] = {}
                param["schema"]["default"] = param_defaults[name]

    if response_schema:
        endpoint_spec.setdefault("responses", {})
        endpoint_spec["responses"].setdefault(
            "200", {"description": "Successful response"}
        )
        endpoint_spec["responses"]["200"]["content"] = {
            "application/json": {"schema": response_schema}
        }

    return updated_spec


def default_route_maker(
    route_spec,
    method="get",
    description="",
    param_types=None,
    param_descriptions=None,
    param_defaults=None,
    response_schema=None,
    openapi_template=None,
):
    """
    Convert various input formats to a ju.oas.Route object, optionally modifying the spec.

    Parameters:
    -----------
    route_spec : Union[ju.oas.Route, str, dict, tuple]
        The route specification in one of several formats:
        - ju.oas.Route: returned unchanged
        - str: treated as a URL template and converted to a Route
        - dict: treated as an OpenAPI spec and converted to a Route
        - tuple: (method, endpoint) or (method, endpoint, spec)
    method : str, optional
        HTTP method to use when route_spec is a string (default: "get")
    description : str, optional
        Description to override or set for the endpoint
    param_types : dict, optional
        Dictionary mapping parameter names to their types
    param_descriptions : dict, optional
        Dictionary mapping parameter names to their descriptions
    param_defaults : dict, optional
        Dictionary mapping parameter names to their default values
    response_schema : dict, optional
        Schema for the response
    openapi_template : dict, optional
        Custom OpenAPI template for string inputs

    Returns:
    --------
    ju.oas.Route
        A Route object representing the API endpoint
    """
    from ju.oas import Routes, Route

    # Case 1: Already a Route object
    if isinstance(route_spec, Route):
        route = route_spec
        # If additional parameters are provided, update the spec
        if any(
            [
                description,
                param_types,
                param_descriptions,
                param_defaults,
                response_schema,
            ]
        ):
            updated_spec = update_spec(
                route.spec,
                route.endpoint,
                route.method,
                description=description,
                param_types=param_types,
                param_descriptions=param_descriptions,
                param_defaults=param_defaults,
                response_schema=response_schema,
            )
            route = Route(route.method, route.endpoint, updated_spec)
        return route

    # Case 2: String (URL template)
    elif isinstance(route_spec, str):
        # Handle URL template
        parsed_url = urlparse(route_spec)
        if parsed_url.scheme and parsed_url.netloc:
            # Full URL template with scheme and domain
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            endpoint_path = parsed_url.path
            if parsed_url.query:
                endpoint_path += f"?{parsed_url.query}"

            # Convert to OpenAPI spec with all the provided parameters
            spec = url_template_to_openapi(
                route_spec,
                method=method,
                description=description,
                param_types=param_types or {},
                param_descriptions=param_descriptions or {},
                param_defaults=param_defaults or {},
                response_schema=response_schema,
                openapi_template=openapi_template,
            )
            routes = Routes(spec)
            path = list(spec["paths"].keys())[0]
            return routes[method.lower(), path]
        else:
            # Just an endpoint path
            raise ValueError(
                f"URL template must include scheme and domain: {route_spec}"
            )

    # Case 3: Dict (OpenAPI spec)
    elif isinstance(route_spec, dict):
        # Assume it's an OpenAPI spec
        if "paths" not in route_spec:
            raise ValueError("Dict must be a valid OpenAPI spec with 'paths' key")

        routes = Routes(route_spec)
        # If there's only one path and method, use that
        if len(list(routes)) == 1:
            route = routes[next(iter(routes))]
            # If additional parameters are provided, update the spec
            if any(
                [
                    description,
                    param_types,
                    param_descriptions,
                    param_defaults,
                    response_schema,
                ]
            ):
                updated_spec = update_spec(
                    route.spec,
                    route.endpoint,
                    route.method,
                    description=description,
                    param_types=param_types,
                    param_descriptions=param_descriptions,
                    param_defaults=param_defaults,
                    response_schema=response_schema,
                )
                route = Route(route.method, route.endpoint, updated_spec)
            return route
        else:
            raise ValueError(
                "OpenAPI spec contains multiple routes. Please specify method and endpoint."
            )

    # Case 4: Tuple of (method, endpoint, spec)
    elif isinstance(route_spec, tuple) and len(route_spec) >= 2:
        method, endpoint = route_spec[0], route_spec[1]
        spec = (
            route_spec[2]
            if len(route_spec) > 2
            else {"openapi": "3.0.3", "paths": {endpoint: {method: {}}}}
        )

        # If additional parameters are provided, update the spec
        if any(
            [
                description,
                param_types,
                param_descriptions,
                param_defaults,
                response_schema,
            ]
        ):
            spec = update_spec(
                spec,
                endpoint,
                method,
                description=description,
                param_types=param_types,
                param_descriptions=param_descriptions,
                param_defaults=param_defaults,
                response_schema=response_schema,
            )

        return Route(method, endpoint, spec)

    else:
        raise TypeError(
            f"Cannot convert {type(route_spec)} to Route. Expected Route, string URL template, or OpenAPI spec dict."
        )


def _simple_style(value) -> str:
    """A header or cookie value serialised the way OpenAPI's ``simple`` style does.

    >>> _simple_style(True), _simple_style(3), _simple_style(['a', 'b'])
    ('true', '3', 'a,b')
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_simple_style(v) for v in value)
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _composed_text(value) -> str:
    """A value as text inside a larger query value (``?q=is:{x}``): lists comma-joined.

    >>> _composed_text(True), _composed_text([1, 'a']), _composed_text(3)
    ('true', '1,a', '3')
    """
    if isinstance(value, dict):
        raise TypeError(f"A dict cannot be part of a query value: {value!r}")
    shown = _query_value(value)
    return ",".join(map(str, shown)) if isinstance(shown, list) else str(shown)


def _query_value(value):
    """A query value as ``requests`` should send it: booleans as ``true``/``false``
    (``requests`` would send ``True``), lists as repeated values.

    >>> _query_value(False), _query_value(3), _query_value([True, 'a'])
    ('false', 3, ['true', 'a'])
    """
    if isinstance(value, bool):
        return _simple_style(value)
    if isinstance(value, (list, tuple)):
        return [_query_value(v) for v in value]
    return value


#: HTTP methods a generated function can send.
_HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch"})

#: Header parameters OpenAPI says to ignore (the request's own settings win;
#: ``custom_headers`` is how a caller sets ``Authorization``).
_IGNORED_HEADER_PARAMS = frozenset({"accept", "content-type", "authorization"})

#: Media types of request bodies that are not sent as JSON.
_FORM_MEDIA_TYPE = "application/x-www-form-urlencoded"
_MULTIPART_MEDIA_TYPE = "multipart/form-data"


def _path_value(value) -> str:
    """A path value, serialised as OpenAPI's ``simple`` style and percent-encoded
    (``/`` included), a list's items joined with an unescaped comma.

    >>> _path_value(True), _path_value('a/b c'), _path_value(['x y', 2])
    ('true', 'a%2Fb%20c', 'x%20y,2')
    """
    if isinstance(value, (list, tuple)):
        return ",".join(_path_value(v) for v in value)
    return quote(_simple_style(value), safe="")


def _form_value(value):
    """A form field value for ``requests``: booleans as ``true``/``false``, objects
    as JSON, lists as repeated values.

    >>> _form_value(True), _form_value({'k': 1}), _form_value([False, 'a'])
    ('true', '{"k": 1}', ['false', 'a'])
    """
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return [_form_value(v) for v in value]
    return _query_value(value)


def _multipart_fields(body: dict) -> list:
    """The ``files=`` list ``requests`` builds a multipart body from: bytes and
    files as file parts (with a filename, as servers need to see an upload), lists
    as one part per item, the rest as text parts.

    >>> _multipart_fields({'n': 3, 'tags': ['a', True], 'raw': b'x', 'o': {'k': 1}})
    [('n', (None, '3')), ('tags', (None, 'a')), ('tags', (None, 'true')), ('raw', ('raw', b'x')), ('o', (None, '{"k": 1}'))]
    """

    def part(key, value):
        if isinstance(value, bytes):
            return (key, (key, value))
        if hasattr(value, "read"):
            filename = os.path.basename(str(getattr(value, "name", None) or key))
            return (key, (filename, value))
        text = json.dumps(value) if isinstance(value, dict) else _simple_style(value)
        return (key, (None, text))

    return [
        part(key, item)
        for key, value in body.items()
        for item in (value if isinstance(value, (list, tuple)) else [value])
    ]


def _without_ignored_headers(params_schema: dict, param_places: dict) -> dict:
    """The parameters schema minus the header parameters OpenAPI says to ignore.

    >>> schema = {'properties': {'a': {}, 'Accept': {}}, 'required': ['Accept']}
    >>> _without_ignored_headers(schema, {'Accept': 'header', 'a': 'query'})
    {'properties': {'a': {}}, 'required': []}
    """
    ignored = set()
    for key, prop in params_schema["properties"].items():
        name = prop.get(OAS_NAME_KEY, key)
        where = prop.get(OAS_IN_KEY) or param_places.get(name)
        if where == "header" and name.lower() in _IGNORED_HEADER_PARAMS:
            ignored.add(key)
    return {
        **params_schema,
        "properties": {
            k: v for k, v in params_schema["properties"].items() if k not in ignored
        },
        "required": [k for k in params_schema.get("required", []) if k not in ignored],
    }


def _with_python_names(params_schema: dict):
    """The parameters schema with each ``x-python-name`` property keyed by that name
    (recording its old key, the name the spec sends it under, as ``x-oas-name``), and
    the ``echoes``: properties that name an argument another property already has,
    which send that one argument in one more place.

    >>> schema = {'properties': {'q': {'x-python-name': 'term'}, 'n': {}},
    ...           'required': ['q']}
    >>> _with_python_names(schema)
    ({'properties': {'term': {'x-oas-name': 'q'}, 'n': {}}, 'required': ['term']}, {})
    >>> schema = {'properties': {'id': {}, 'item': {'x-python-name': 'id'}}}
    >>> _with_python_names(schema)
    ({'properties': {'id': {}}}, {'id': [('item', {'x-oas-name': 'item'})]})
    """
    # All the renames happen at once, so that names can be swapped
    # (``?b={a}&a={b}``).
    names = {
        key: prop.get(PYTHON_NAME_KEY) or key
        for key, prop in params_schema["properties"].items()
    }
    if all(key == name for key, name in names.items()):
        return params_schema, {}
    properties, echoes = {}, {}
    for key, prop in params_schema["properties"].items():
        if PYTHON_NAME_KEY in prop:
            prop = {k: v for k, v in prop.items() if k != PYTHON_NAME_KEY}
            if names[key] != key:
                prop.setdefault(OAS_NAME_KEY, key)
        if names[key] in properties:
            echoes.setdefault(names[key], []).append((key, prop))
        else:
            properties[names[key]] = prop
    renamed = {**params_schema, "properties": properties}
    if "required" in params_schema:
        required = dict.fromkeys(names[k] for k in params_schema["required"])
        renamed["required"] = list(required)
    return renamed, echoes


def route_to_func(
    route,
    base_url: str | None = None,
    *,
    route_maker=None,
    method: str = "get",
    session=None,
    error_handler=None,
    timeout=30,
    egress: Callable | None = None,
    custom_headers=None,
    name: str | None = None,
    # arguments for customizing the route specification:
    description: str = "",
    param_types: dict = None,
    param_descriptions: dict = None,
    param_defaults: dict = None,
    response_schema: dict = None,
    openapi_template=None,
):
    """
    Generate a Python function from an OpenAPI route specification.

    The generated function will make HTTP requests to the web service
    according to the route's method and parameters.

    Parameters:
    -----------
    route : Union[ju.oas.Route, str, dict, tuple]
        The route specification in one of several formats:
        - ju.oas.Route: An OpenAPI route specification
        - str: A URL template with placeholders (e.g., "https://api.example.com/items/{id}")
        - dict: An OpenAPI specification dictionary
        - tuple: (method, endpoint) or (method, endpoint, spec)
    base_url : str, optional
        The base URL of the web service. If None, attempts to extract from the OpenAPI spec's
        servers array. At least one of base_url or a server URL in the spec must be provided.
    route_maker : callable, optional
        A function to convert the route parameter to a ju.oas.Route object.
        If None, default_route_maker is used.
    method : str, optional
        HTTP method to use when route is a string template (default: "get")
    session : requests.Session, optional
        A session object to use for requests. If None, a new session will be created for each request.
    error_handler : callable, optional
        A function to handle request errors. Should accept (response, exception) and return a value or raise.
    timeout : int, optional
        Request timeout in seconds.
    egress : callable, optional
        A function to process the response before returning. If None, JSON will be attempted first,
        then text, then binary content.
    custom_headers : dict, optional
        Custom headers to include in all requests.
    name : str, optional
        The name of the generated function. If None, a default name will be generated based on the route.

    Returns:
    --------
    callable
        A Python function that implements the specified route.

    Example:
    --------
    >>> # Using a Route object
    >>> from ju.oas import Routes
    >>> routes = Routes(openapi_spec)  # doctest: +SKIP
    >>> get_items = route_to_func(routes['get', '/items'], 'https://api.example.com')  # doctest: +SKIP

    >>> # Using a URL template
    >>> get_item = route_to_func("https://api.example.com/items/{item_id}", 'https://api.example.com')  # doctest: +SKIP
    >>> item = get_item(item_id="abc123")  # doctest: +SKIP

    >>> # Using an OpenAPI spec dictionary
    >>> spec = {"openapi": "3.0.3", "paths": {"/items": {"get": {"parameters": [...]}}}}  # doctest: +SKIP
    >>> get_items = route_to_func(spec, 'https://api.example.com')  # doctest: +SKIP
    """
    # Convert route to a ju.oas.Route object
    if route_maker is None:
        route_maker = lambda r: default_route_maker(
            r,
            method=method,
            description=description,
            param_types=param_types,
            param_descriptions=param_descriptions,
            param_defaults=param_defaults,
            response_schema=response_schema,
            openapi_template=openapi_template,
        )

    route = route_maker(route)

    # Try to get base_url from the OpenAPI spec if not provided
    if base_url is None:
        # Look for servers in the OpenAPI spec
        if hasattr(route, "spec") and "servers" in route.spec and route.spec["servers"]:
            # Use the first server URL as the base URL
            base_url = route.spec["servers"][0]["url"]
        else:
            # Special case for URL templates that already include base URL
            if isinstance(route, Route) and route.endpoint.startswith("http"):
                # For URL templates with full URLs as endpoints
                parsed = urlparse(route.endpoint)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                # Adjust the endpoint to be just the path
                route.endpoint = parsed.path + (
                    "?" + parsed.query if parsed.query else ""
                )
            else:
                raise ValueError(
                    "No base_url provided and no servers defined in the OpenAPI spec"
                )

    # Where each OpenAPI parameter goes, by its spec name
    param_places = {
        p["name"]: p.get("in") for p in route.input_specs.get("parameters") or ()
    }
    # The route's parameters, minus the headers OpenAPI says to ignore
    params_schema = _without_ignored_headers(route.params, param_places)
    params_schema, echoes = _with_python_names(params_schema)

    # Get the function signature from the route parameters
    sig = json_schema_to_signature(params_schema)

    # Ensure the base URL doesn't end with a slash if the endpoint starts with one
    clean_base_url = base_url.rstrip("/")
    endpoint = route.endpoint
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    full_url = clean_base_url + endpoint
    http_method = route.method.lower()

    # Use provided handlers or defaults
    _error_handler = error_handler or default_error_handler
    _egress = egress or default_response_processor

    # The signature's names are Python identifiers; the spec's are not always
    # (``$first``, ``X-MS-API-ROLE``, ``pageSize``). Requests must use the
    # spec's, so every argument is sent under its original name (i2mint/ho#2).
    original_names = schema_param_names(params_schema)  # python name -> spec name
    # Where each argument goes -- 'query', 'path', 'header', 'cookie' or 'body' --
    # by Python name. A property that shares its spec name with another says where
    # it goes itself (``x-oas-in``, ju#20); the others are told apart by name.
    has_body = bool(route.input_specs.get("requestBody"))
    def _where(spec_name, prop):
        if COMPOSED_INTO_KEY in prop:
            return "composed"  # a part of a query value (below), not sent by itself
        where = prop.get(OAS_IN_KEY) or param_places.get(spec_name)
        if where in (None, PARAM_IN) and f"{{{spec_name}}}" in route.endpoint:
            where = "path"  # a parameter that does not say where, the URL does
        if where == BODY_IN or (where in (None, PARAM_IN) and has_body):
            where = "body"
        return where

    locations = {}  # python name -> [(spec name, where), ...]: where it is sent
    for (pyname, spec_name), prop in zip(
        original_names.items(), params_schema["properties"].values()
    ):
        locations[pyname] = [(spec_name, _where(spec_name, prop))]
    pyname_of_key = dict(zip(params_schema["properties"], original_names))
    for key_, more in echoes.items():  # (the argument is also sent as these)
        pyname = pyname_of_key[key_]
        for key, prop in more:
            spec_name = prop.get(OAS_NAME_KEY, key)
            locations[pyname].append((spec_name, _where(spec_name, prop)))
    method_data = getattr(route, "method_data", None) or {}
    query_templates = method_data.get(QUERY_TEMPLATES_KEY, {})
    static_query = method_data.get(STATIC_QUERY_KEY, {})

    def _by_location(params):
        """Split bound arguments by where the spec sends them, under spec names."""
        split = {"query": dict(static_query), "path": {}, "header": {}, "cookie": {}}
        split["body"] = {}
        for pyname, value in params.items():
            for name, where in locations.get(pyname, [(pyname, None)]):
                if where == "path":
                    if value is None:
                        raise ValueError(
                            f"Path parameter {name!r} is required, got None."
                        )
                    split["path"][name] = value
                elif value is None:  # an omitted optional is not sent at all
                    continue
                elif where == "query":
                    split["query"][name] = _query_value(value)
                elif where in ("header", "cookie"):
                    split[where][name] = _simple_style(value)
                elif where == "body":
                    split["body"][name] = value
        for key, template in query_templates.items():
            parts = {part: pyname_of_key.get(part, part) for part in _PLACEHOLDER.findall(template)}
            if all(params.get(py) is not None for py in parts.values()):
                split["query"][key] = _PLACEHOLDER.sub(
                    lambda m: _composed_text(params[parts[m.group(1)]]), template
                )
        return split

    # (a Route-like object from a custom route_maker may not have the attribute)
    body_type = (getattr(route, "body_content_type", None) or "").split(";")[0]
    body_type = body_type.strip().lower()

    @sig
    def func(*args, **kwargs):
        """
        Implementation of the {http_method} {endpoint} endpoint.

        This function was automatically generated from the OpenAPI specification.
        It sends a {http_method} request to {full_url}.
        """
        # Bind the arguments to the parameters
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        params = bound_args.arguments

        # Split them by where the spec sends them, under the spec's names
        split = _by_location(params)
        query_params, path_params, body_params = (
            split["query"],
            split["path"],
            split["body"],
        )

        # Format URL with path parameters
        formatted_url = full_url
        if path_params:
            for name, value in path_params.items():
                formatted_url = formatted_url.replace(f"{{{name}}}", _path_value(value))

        # Set up headers
        sent_as_form = body_type in (_FORM_MEDIA_TYPE, _MULTIPART_MEDIA_TYPE)
        # A form body's Content-Type is for ``requests`` to set (multipart needs
        # its boundary); everything else is sent as JSON.
        headers = {} if sent_as_form else {"Content-Type": "application/json"}
        if custom_headers:
            headers.update(custom_headers)
        headers.update(split["header"])  # the call's own, over the defaults

        # Send the request using either the provided session or a new session
        current_session = session or requests

        try:
            if http_method not in _HTTP_METHODS:
                raise ValueError(f"Unsupported HTTP method: {http_method}")
            # Only the method this route uses is needed from the session
            method_func = getattr(current_session, http_method)

            method_kwargs = dict(
                url=formatted_url,
                params=query_params,
                headers=headers,
                timeout=timeout,
            )
            if body_type == _FORM_MEDIA_TYPE:
                method_kwargs["data"] = {
                    k: _form_value(v) for k, v in body_params.items()
                }
            elif body_type == _MULTIPART_MEDIA_TYPE:
                method_kwargs["files"] = _multipart_fields(body_params)
            elif http_method != "get" or body_params:
                # (a GET without body arguments has no body to send)
                method_kwargs["json"] = body_params
            if split["cookie"]:
                method_kwargs["cookies"] = split["cookie"]

            response = method_func(**method_kwargs)

            # Handle errors
            _error_handler(response)

            # Process and return the response
            return _egress(response)

        except Exception as e:
            return _error_handler(None, e)

    # Set the function name and docstring -------------------------------------------

    def name_func(func, name):
        if name is None:
            # Find all path parameters and replace them
            import re

            clean_endpoint = route.endpoint
            path_param_pattern = re.compile(r"{([^}]+)}")
            clean_endpoint = path_param_pattern.sub(r"_\1_", clean_endpoint)
            name = f"{http_method}_{clean_endpoint.replace('/', '_').strip('_')}"

        func.__name__ = name
        return func

    func = name_func(func, name)
    method_description = route.method_data.get("summary", "")
    params_description = ""
    described = {
        (p.get("name"), p.get("in")): p.get("description", "")
        for p in route.input_specs.get("parameters") or ()
    }
    for (pyname, spec_name), prop in zip(
        original_names.items(), params_schema["properties"].values()
    ):
        shown = (
            f"{pyname} (sent as {spec_name!r})" if pyname != spec_name else spec_name
        )
        where = locations[pyname][0][1]
        if where == "composed":
            into = prop[COMPOSED_INTO_KEY]
            params_description += f"\n    {pyname}: (part of the query value {into!r})"
            continue
        description = described.get(
            (spec_name, where),
            # (a parameter that did not say where is keyed by None)
            described.get((spec_name, None), prop.get("description", "")),
        )
        params_description += f"\n    {shown}: {description}"

    func.__doc__ = f"""{method_description}
    
    Endpoint: {http_method.upper()} {route.endpoint}
    
    Parameters:{params_description}
    
    Returns:
    --------
    The processed response from the API, typically as JSON.
    """
    # Python name -> the name the spec uses, for callers that must translate
    # back (a pagination cursor named ``$after``, say). i2mint/ho#1, #2.
    func.openapi_param_names = dict(original_names)

    return func


def routes_to_funcs(
    spec_or_routes, base_url, *, name_as_key: bool = False, **route_to_func_kwargs
):
    """
    Convert all routes in an OpenAPI specification to Python functions.

    Parameters:
    -----------
    spec_or_routes : dict or ju.oas.Routes
        Either an OpenAPI specification dictionary or a ju.oas.Routes instance.
    base_url : str
        The base URL of the web service.
    name_as_key : bool, optional
        If True, use the function name as the key in the returned dictionary.
        If False, use a tuple of (method, endpoint) as the key.
    **route_to_func_kwargs :
        Additional keyword arguments to pass to route_to_func.

    Returns:
    --------
    dict
        A dictionary mapping (method, endpoint) tuples to functions.

    Example:
    --------

    >>> from ju.oas import Routes
    >>> routes = Routes(openapi_spec)  # doctest: +SKIP
    >>> api_functions = routes_to_funcs(routes, 'https://api.example.com')  # doctest: +SKIP
    >>> items = api_functions['get', '/items'](type='electronics')  # doctest: +SKIP
    """
    from ju.oas import Routes

    if not isinstance(spec_or_routes, Routes):
        routes = Routes(spec_or_routes)
    else:
        routes = spec_or_routes

    functions = {}
    for method, endpoint in routes:
        route = routes[method, endpoint]
        func = route_to_func(route, base_url, **route_to_func_kwargs)
        func.method = method
        func.endpoint = endpoint
        if name_as_key:
            # Use the function name as the key
            functions[func.__name__] = func
        else:
            functions[method, endpoint] = func

    return functions


def routes_to_namespace(spec_or_routes, base_url, **route_to_func_kwargs):
    funcs = routes_to_funcs(
        spec_or_routes, base_url, name_as_key=True, **route_to_func_kwargs
    )
    return SimpleMappingNamespace(**funcs)


def default_error_handler(response, exception=None):
    """Default error handling: raise for status and return exception info if any"""
    if exception:
        raise exception
    response.raise_for_status()
    return response


def default_response_processor(response):
    """Try to return response as JSON, fallback to text and then content"""
    try:
        return response.json()
    except ValueError:
        if "text" in response.headers.get("Content-Type", "").lower():
            return response.text
        return response.content


# --------------------------------------------------------------------------------------


def minimal_openapi_template(api_path, method="get", description=""):
    """Create a minimal OpenAPI template with just the essential elements."""
    return {
        "openapi": "3.0.3",
        "paths": {
            api_path: {
                method.lower(): {
                    "summary": description,
                    "parameters": [],
                    "responses": {"200": {"description": "Successful response"}},
                }
            }
        },
    }


def url_template_to_openapi(
    url_template: str,
    *,
    method: str = "get",
    description: str = "",
    param_types: dict = None,
    param_descriptions: dict = None,
    param_defaults: dict = None,
    response_schema: dict = None,
    openapi_template=None,
):
    """
    Convert a URL template with placeholders to an OpenAPI specification.

    Parameters:
    -----------
    url_template : str
        URL template with placeholders in format:
        - Simple: {param_name}
        - With default: {param_name:default_value}
    method : str, optional
        HTTP method for the endpoint (default: "get")
    description : str, optional
        Description of the endpoint
    param_types : dict, optional
        Dictionary mapping parameter names to their types
    param_descriptions : dict, optional
        Dictionary mapping parameter names to their descriptions
    param_defaults : dict, optional
        Dictionary mapping parameter names to their default values
    response_schema : dict, optional
        Schema for the response
    openapi_template : dict, optional
        Custom OpenAPI template to use instead of the default minimal one

    Returns:
    --------
    dict
        OpenAPI specification as a dictionary
    """
    param_types = param_types or {}
    param_descriptions = param_descriptions or {}
    param_defaults = param_defaults or {}

    # Parse the URL to get path and base URL
    parsed_url = urlparse(url_template)
    path = parsed_url.path
    base_url = (
        f"{parsed_url.scheme}://{parsed_url.netloc}"
        if parsed_url.scheme and parsed_url.netloc
        else None
    )

    # Extract path parameters with optional defaults
    path_params_match = re.findall(r"\{([^{}]+)\}", path)
    path_params = []

    # Process inline defaults in path parameters
    for param_match in path_params_match:
        if ":" in param_match:
            param_name, default_value = param_match.split(":", 1)
            param_defaults[param_name] = default_value
            path_params.append(param_name)
            # Update the path to use the parameter name without default
            path = path.replace(f"{{{param_match}}}", f"{{{param_name}}}")
        else:
            path_params.append(param_match)

    # Extract query parameters from the URL template. Each is a (name, key, into)
    # triple: the placeholder's name (the Python argument), the key the service
    # expects in the query string (the OpenAPI parameter's name; i2mint/ho#10), and,
    # if the value holds more than the placeholder (``r={lo}-{hi}``), that value's key.
    query_params = []
    static_query = {}  # key -> value, for the parts of the query that are no template
    query_templates = {}  # key -> value template, for the values with several parts
    composed_seen = set()

    inline_defaults = {}

    def _split_placeholder(content):
        name, sep, default_value = content.partition(":")
        if sep:
            if inline_defaults.setdefault(name, default_value) != default_value:
                raise ValueError(
                    f"The placeholder {{{name}}} has two defaults: "
                    f"{inline_defaults[name]!r} and {default_value!r}."
                )
            param_defaults[name] = default_value
        return name

    for key, values in parse_qs(parsed_url.query, keep_blank_values=True).items():
        if _PLACEHOLDER.search(key) or "{" in key or "}" in key:
            raise ValueError(
                f"A placeholder in the query key {key!r} is not supported: the key "
                "is part of the request's shape, not an argument."
            )
        if len(values) > 1:
            raise ValueError(
                f"The query key {key!r} is used {len(values)} times: use it once, "
                "with a list as the argument if it takes several values."
            )
        (value,) = values
        contents = _PLACEHOLDER.findall(value)
        if "{" in _PLACEHOLDER.sub("", value) or "}" in _PLACEHOLDER.sub("", value):
            raise ValueError(f"Malformed placeholder in the query: {key}={value}")
        if not contents:
            static_query[key] = value
        elif _PLACEHOLDER.fullmatch(value):
            query_params.append((_split_placeholder(contents[0]), key, None))
        else:  # literal text around the placeholder(s)
            for name in dict.fromkeys(_split_placeholder(c) for c in contents):
                if (name, key) not in composed_seen:  # (one parameter per part)
                    composed_seen.add((name, key))
                    query_params.append((name, f"{key}[{name}]", key))
            query_templates[key] = _PLACEHOLDER.sub(
                lambda m: "{%s}" % m.group(1).partition(":")[0], value
            )

    # Create OpenAPI spec from template or default
    if openapi_template is None:
        openapi_spec = minimal_openapi_template(path, method, description)
    else:
        import copy

        openapi_spec = copy.deepcopy(openapi_template)
        # Make sure the path and method exist in the template
        if "paths" not in openapi_spec:
            openapi_spec["paths"] = {}
        if path not in openapi_spec["paths"]:
            openapi_spec["paths"][path] = {}
        if method.lower() not in openapi_spec["paths"][path]:
            openapi_spec["paths"][path][method.lower()] = {
                "summary": description,
                "parameters": [],
                "responses": {"200": {"description": "Successful response"}},
            }

    # Add server information if we have a base URL
    if base_url:
        if "servers" not in openapi_spec:
            openapi_spec["servers"] = []
        openapi_spec["servers"].append(
            {"url": base_url, "description": "Generated from URL template"}
        )

    # Add parameters to the spec
    endpoint_spec = openapi_spec["paths"][path][method.lower()]
    if "parameters" not in endpoint_spec:
        endpoint_spec["parameters"] = []

    # Add path parameters
    for param in path_params:
        param_spec = {
            "name": param,
            "in": "path",
            "required": True,
            "schema": {"type": param_types.get(param, "string")},
            "description": param_descriptions.get(param, f"Parameter {param}"),
        }

        if param in param_defaults:
            param_spec["schema"]["default"] = param_defaults[param]

        endpoint_spec["parameters"].append(param_spec)

    # Add query parameters, named after the template's key; the placeholder's name
    # (the Python argument) rides along as ``x-python-name`` (see `route_to_func`),
    # which is also how an argument is shared with a path parameter or another key.
    taken = set(path_params)
    for param, key, into in query_params:
        schema = {"type": param_types.get(param, "string")}
        if param in param_defaults:
            schema["default"] = param_defaults[param]
        if key != param or param in taken or into is not None:
            schema[PYTHON_NAME_KEY] = param
        if into is not None:
            schema[COMPOSED_INTO_KEY] = into
        taken.add(param)
        endpoint_spec["parameters"].append(
            {
                "name": key,
                "in": "query",
                "required": param not in param_defaults,
                "schema": schema,
                "description": param_descriptions.get(param, f"Parameter {param}"),
            }
        )
    if static_query:
        endpoint_spec[STATIC_QUERY_KEY] = static_query
    if query_templates:
        endpoint_spec[QUERY_TEMPLATES_KEY] = query_templates

    # Add response schema if provided
    if response_schema:
        if "responses" not in endpoint_spec:
            endpoint_spec["responses"] = {}
        if "200" not in endpoint_spec["responses"]:
            endpoint_spec["responses"]["200"] = {"description": "Successful response"}

        endpoint_spec["responses"]["200"]["content"] = {
            "application/json": {"schema": response_schema}
        }

    return openapi_spec


def url_template_to_func(
    url_template: str,
    *,
    method: str = "get",
    description: str = "",
    param_types: dict = None,
    param_descriptions: dict = None,
    param_defaults: dict = None,
    response_schema: dict = None,
    openapi_template: dict = None,
    session=None,
    error_handler=None,
    timeout=30,
    egress=None,
    custom_headers=None,
):
    """
    Convert a URL template directly to a Python function.

    Parameters:
    -----------
    url_template : str
        URL template with placeholders in format:
        - Simple: {param_name}
        - With default: {param_name:default_value}
        Examples:
        - "https://example.com/mall/{store}/{item_id:1}"
        - "https://www.google.com/search?q={search_term}"
    method : str, optional
        HTTP method for the endpoint (default: "get")
    description : str, optional
        Description of the endpoint
    param_types : dict, optional
        Dictionary mapping parameter names to their types (string, integer, etc.)
    param_descriptions : dict, optional
        Dictionary mapping parameter names to their descriptions
    param_defaults : dict, optional
        Dictionary mapping parameter names to their default values
    response_schema : dict, optional
        Schema for the response
    openapi_template : dict, optional
        Custom OpenAPI template instead of using the minimal default
    session : requests.Session, optional
        A session object to use for requests
    error_handler : callable, optional
        A function to handle request errors
    timeout : int, optional
        Request timeout in seconds
    egress : callable, optional
        A function to process the response before returning
    custom_headers : dict, optional
        Custom headers to include in all requests

    Returns:
    --------
    callable
        A Python function that implements the URL template

    Example:
    --------
    >>> from types import SimpleNamespace
    >>> sent = []
    >>> def fake_get(**kwargs):  # stands in for a real session, so no network
    ...     sent.append(kwargs)
    ...     return SimpleNamespace(text="<html>", raise_for_status=lambda: None)
    >>> search_google = url_template_to_func(
    ...     "https://www.google.com/search?q={search_term}",
    ...     description="Search Google",
    ...     egress=lambda response: response.text,
    ...     session=SimpleNamespace(get=fake_get),
    ... )
    >>> search_google(search_term="Python")
    '<html>'
    >>> sent[0]["url"]
    'https://www.google.com/search'
    >>> sent[0]["params"]  # sent under the template's key, not the argument's name
    {'q': 'Python'}

    >>> # Example using REST Countries API with path and query parameters
    >>> get_country = url_template_to_func(
    ...     "https://restcountries.com/v3.1/name/{country_name}?fullText={full_text:false}&fields={fields:name,capital,population}",
    ...     description="Get country information by name",
    ...     param_types={"country_name": "string", "full_text": "boolean", "fields": "string"},
    ...     param_descriptions={
    ...         "country_name": "Name of the country to search for",
    ...         "full_text": "Whether to match the full text of the name (true) or partial match (false)",
    ...         "fields": "Comma-separated list of fields to include in the response"
    ...     }
    ... )
    >>> import inspect
    >>> print(inspect.signature(get_country))  # View the generated function signature
    (country_name: str, full_text: bool = 'false', fields: str = 'name,capital,population')

    >>> # Example using TheMealDB API with multiple query parameters
    >>> search_meals = url_template_to_func(
    ...     "https://www.themealdb.com/api/json/v1/1/filter.php?c={category:Dessert}&a={area:}",
    ...     description="Search for meals by category and area",
    ...     param_types={"category": "string", "area": "string"},
    ...     param_descriptions={
    ...         "category": "The category of meals to search for (e.g., Seafood, Dessert)",
    ...         "area": "The area/country of origin (optional, e.g., Italian, American)"
    ...     }
    ... )
    >>> # search_meals can be called with either or both parameters:
    >>> # italian_desserts = search_meals(area="Italian")  # Uses default category="Dessert"
    >>> # seafood_meals = search_meals(category="Seafood")  # No area specified
    """

    # Parse the URL to get base URL
    parsed_url = urlparse(url_template)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # Convert URL template to OpenAPI spec
    spec = url_template_to_openapi(
        url_template,
        method=method,
        description=description,
        param_types=param_types,
        param_descriptions=param_descriptions,
        param_defaults=param_defaults,
        response_schema=response_schema,
        openapi_template=openapi_template,
    )

    # Create Routes object
    routes = Routes(spec)

    # Get the path from the spec (should be only one)
    path = list(spec["paths"].keys())[0]

    # Convert route to function
    route_kwargs = {
        "session": session,
        "error_handler": error_handler,
        "timeout": timeout,
        "egress": egress,
        "custom_headers": custom_headers,
    }
    # Remove None values to use defaults in route_to_func
    route_kwargs = {k: v for k, v in route_kwargs.items() if v is not None}

    return route_to_func(routes[method.lower(), path], base_url, **route_kwargs)
