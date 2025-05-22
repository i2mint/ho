"""HO base objects"""

import re
from typing import Optional, Callable
from urllib.parse import urlparse, parse_qs, quote

import requests

from ju.json_schema import json_schema_to_signature
from ju.oas import Route, Routes

from ho.util import SimpleMappingNamespace


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


def route_to_func(
    route,
    base_url: Optional[str] = None,
    *,
    route_maker=None,
    method: str = "get",
    session=None,
    error_handler=None,
    timeout=30,
    egress: Optional[Callable] = None,
    custom_headers=None,
    name: Optional[str] = None,
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

    # Get the function signature from the route parameters
    sig = json_schema_to_signature(route.params)

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

    def _extract_query_params(params, required_params):
        """Extract query parameters from all parameters"""
        query_params = {}
        for name, param in params.items():
            # Check if this is a query parameter, or if the parameter is in the request body
            if route.input_specs.get("parameters"):
                for route_param in route.input_specs["parameters"]:
                    if (
                        route_param.get("name") == name
                        and route_param.get("in") == "query"
                    ):
                        if param is not None:  # Only include non-None parameters
                            query_params[name] = param
                        break
        return query_params

    def _extract_path_params(params):
        """Extract path parameters from all parameters"""
        path_params = {}
        for name, param in params.items():
            # Check if this parameter is in the path
            if route.input_specs.get("parameters"):
                for route_param in route.input_specs["parameters"]:
                    if (
                        route_param.get("name") == name
                        and route_param.get("in") == "path"
                    ):
                        path_params[name] = param
                        break
        return path_params

    def _extract_body_params(params, query_params, path_params):
        """Extract body parameters (all parameters not in query or path)"""
        body_params = {}
        # If there's a requestBody in the spec, include all parameters that aren't query or path
        if route.input_specs.get("requestBody"):
            for name, param in params.items():
                if name not in query_params and name not in path_params:
                    if param is not None:  # Only include non-None parameters
                        body_params[name] = param
        return body_params

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

        # Extract different types of parameters
        query_params = _extract_query_params(params, sig.parameters)
        path_params = _extract_path_params(params)
        body_params = _extract_body_params(params, query_params, path_params)

        # Format URL with path parameters
        formatted_url = full_url
        if path_params:
            for name, value in path_params.items():
                formatted_url = formatted_url.replace(f"{{{name}}}", quote(str(value)))

        # Set up headers
        headers = {"Content-Type": "application/json"}
        if custom_headers:
            headers.update(custom_headers)

        # Send the request using either the provided session or a new session
        current_session = session or requests

        try:
            # Map HTTP methods to their corresponding session methods
            method_map = {
                method: getattr(current_session, method)
                for method in ["get", "post", "put", "delete", "patch"]
            }

            if http_method not in method_map:
                raise ValueError(f"Unsupported HTTP method: {http_method}")
            else:
                method_func = method_map[http_method]

            method_kwargs = dict(
                url=formatted_url,
                params=query_params,
                json=body_params,
                headers=headers,
                timeout=timeout,
            )

            if http_method == "get":
                # For GET requests, don't include the json parameter
                method_kwargs.pop("json", None)

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
    for param in route.input_specs.get("parameters", []):
        params_description += (
            f"\n    {param.get('name')}: {param.get('description', '')}"
        )

    func.__doc__ = f"""{method_description}
    
    Endpoint: {http_method.upper()} {route.endpoint}
    
    Parameters:{params_description}
    
    Returns:
    --------
    The processed response from the API, typically as JSON.
    """

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

    # Extract query parameters from the URL template
    query_string = parsed_url.query
    query_params = []

    if query_string:
        # Extract parameters from the query string
        template_query_params = parse_qs(query_string)

        # Process each query parameter
        for param_name, values in template_query_params.items():
            # Check if this is a template parameter
            param_match = re.search(r"\{([^{}]+)\}", param_name)
            if param_match:
                # This is a template parameter in the query parameter name
                param_content = param_match.group(1)
                if ":" in param_content:
                    param_name, default_value = param_content.split(":", 1)
                    param_defaults[param_name] = default_value
                else:
                    param_name = param_content
                query_params.append(param_name)
            else:
                # Check if the value contains a template
                for value in values:
                    param_match = re.search(r"\{([^{}]+)\}", value)
                    if param_match:
                        param_content = param_match.group(1)
                        if ":" in param_content:
                            param_name, default_value = param_content.split(":", 1)
                            param_defaults[param_name] = default_value
                        else:
                            param_name = param_content
                        query_params.append(param_name)

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

    # Add query parameters
    for param in query_params:
        param_spec = {
            "name": param,
            "in": "query",
            "required": param not in param_defaults,
            "schema": {"type": param_types.get(param, "string")},
            "description": param_descriptions.get(param, f"Parameter {param}"),
        }

        if param in param_defaults:
            param_spec["schema"]["default"] = param_defaults[param]

        endpoint_spec["parameters"].append(param_spec)

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
    >>> search_google = url_template_to_func(
    ...     "https://www.google.com/search?q={search_term}",
    ...     description="Search Google",
    ...     egress=lambda response: response.text
    ... )
    >>> results = search_google(search_term="Python")

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
