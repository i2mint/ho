# ho.base

HO base objects

### Module Attributes

| [`PYTHON_NAME_KEY`](#ho.base.PYTHON_NAME_KEY)   | A parameter schema's `x-python-name` is the name of the Python argument to send under the parameter's own (spec) name, e.g. the placeholder `search_term` of `?q={search_term}`.                                                |
|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`COMPOSED_INTO_KEY`](#ho.base.COMPOSED_INTO_KEY) | A query parameter's schema says `x-ho-composed-into: <key>` when it is one placeholder of a query value that has more in it (`?r={lo}-{hi}`); the operation's `x-ho-query-templates` holds that value's template (`{lo}-{hi}`). |
| [`STATIC_QUERY_KEY`](#ho.base.STATIC_QUERY_KEY)  | The operation's constant query parameters (`?lang=en`), sent on every request.                                                                                                                                                  |

### Functions

| [`default_error_handler`](#ho.base.default_error_handler)(response[, exception])      | Default error handling: raise for status and return exception info if any              |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| [`default_response_processor`](#ho.base.default_response_processor)(response)              | Try to return response as JSON, fallback to text and then content                      |
| [`default_route_maker`](#ho.base.default_route_maker)(route_spec[, method, ...])    | Convert various input formats to a ju.oas.Route object, optionally modifying the spec. |
| [`minimal_openapi_template`](#ho.base.minimal_openapi_template)(api_path[, method, ...]) | Create a minimal OpenAPI template with just the essential elements.                    |
| [`route_to_func`](#ho.base.route_to_func)(route[, base_url, ...])             | Generate a Python function from an OpenAPI route specification.                        |
| [`routes_to_funcs`](#ho.base.routes_to_funcs)(spec_or_routes, base_url, \*)     | Convert all routes in an OpenAPI specification to Python functions.                    |
| `routes_to_namespace`(spec_or_routes, ...)                                                         |                                                                                        |
| [`update_spec`](#ho.base.update_spec)(spec, path, method[, ...])            | Update an OpenAPI spec with provided parameters for a specific path and method.        |
| [`url_template_to_func`](#ho.base.url_template_to_func)(url_template, \*[, ...])     | Convert a URL template directly to a Python function.                                  |
| [`url_template_to_openapi`](#ho.base.url_template_to_openapi)(url_template, \*[, ...])  | Convert a URL template with placeholders to an OpenAPI specification.                  |

### ho.base.COMPOSED_INTO_KEY *= 'x-ho-composed-into'*

A query parameter’s schema says `x-ho-composed-into: <key>` when it is one
placeholder of a query value that has more in it (`?r={lo}-{hi}`); the
operation’s `x-ho-query-templates` holds that value’s template (`{lo}-{hi}`).

### ho.base.PYTHON_NAME_KEY *= 'x-python-name'*

A parameter schema’s `x-python-name` is the name of the Python argument to
send under the parameter’s own (spec) name, e.g. the placeholder `search_term`
of `?q={search_term}`.

### ho.base.STATIC_QUERY_KEY *= 'x-ho-static-query'*

The operation’s constant query parameters (`?lang=en`), sent on every request.

### ho.base.default_error_handler(response, exception=None)

Default error handling: raise for status and return exception info if any

### ho.base.default_response_processor(response)

Try to return response as JSON, fallback to text and then content

### ho.base.default_route_maker(route_spec, method='get', description='', param_types=None, param_descriptions=None, param_defaults=None, response_schema=None, openapi_template=None)

Convert various input formats to a ju.oas.Route object, optionally modifying the spec.

### Parameters

> - ju.oas.Route: returned unchanged
> - str: treated as a URL template and converted to a Route
> - dict: treated as an OpenAPI spec and converted to a Route
> - tuple: (method, endpoint) or (method, endpoint, spec)

method
: HTTP method to use when route_spec is a string (default: “get”)

description
: Description to override or set for the endpoint

param_types
: Dictionary mapping parameter names to their types

param_descriptions
: Dictionary mapping parameter names to their descriptions

param_defaults
: Dictionary mapping parameter names to their default values

response_schema
: Schema for the response

openapi_template
: Custom OpenAPI template for string inputs

### Returns

### ho.base.minimal_openapi_template(api_path, method='get', description='')

Create a minimal OpenAPI template with just the essential elements.

### ho.base.route_to_func(route, base_url=None, , route_maker=None, method='get', session=None, error_handler=None, timeout=30, egress=None, custom_headers=None, name=None, description='', param_types=None, param_descriptions=None, param_defaults=None, response_schema=None, openapi_template=None)

Generate a Python function from an OpenAPI route specification.

The generated function will make HTTP requests to the web service
according to the route’s method and parameters.

### Parameters

> - ju.oas.Route: An OpenAPI route specification
> - str: A URL template with placeholders (e.g., “[https://api.example.com/items](https://api.example.com/items)/{id}”)
> - dict: An OpenAPI specification dictionary
> - tuple: (method, endpoint) or (method, endpoint, spec)

base_url
: The base URL of the web service. If None, attempts to extract from the OpenAPI spec’s
  servers array. At least one of base_url or a server URL in the spec must be provided.

route_maker
: A function to convert the route parameter to a ju.oas.Route object.
  If None, default_route_maker is used.

method
: HTTP method to use when route is a string template (default: “get”)

session
: A session object to use for requests. If None, a new session will be created for each request.

error_handler
: A function to handle request errors. Should accept (response, exception) and return a value or raise.

timeout
: Request timeout in seconds.

egress
: A function to process the response before returning. If None, JSON will be attempted first,
  then text, then binary content.

custom_headers
: Custom headers to include in all requests.

name
: The name of the generated function. If None, a default name will be generated based on the route.

### Returns

### Example

---
```pycon
>>> # Using a Route object
>>> from ju.oas import Routes
>>> routes = Routes(openapi_spec)
>>> get_items = route_to_func(routes['get', '/items'], 'https://api.example.com')
```

```pycon
>>> # Using a URL template
>>> get_item = route_to_func("https://api.example.com/items/{item_id}", 'https://api.example.com')
>>> item = get_item(item_id="abc123")
```

```pycon
>>> # Using an OpenAPI spec dictionary
>>> spec = {"openapi": "3.0.3", "paths": {"/items": {"get": {"parameters": [...]}}}}
>>> get_items = route_to_func(spec, 'https://api.example.com')
```

### ho.base.routes_to_funcs(spec_or_routes, base_url, , name_as_key=False, \*\*route_to_func_kwargs)

Convert all routes in an OpenAPI specification to Python functions.

### Parameters

base_url
: The base URL of the web service.

name_as_key
: If True, use the function name as the key in the returned dictionary.
  If False, use a tuple of (method, endpoint) as the key.

\*\*route_to_func_kwargs :
: Additional keyword arguments to pass to route_to_func.

### Returns

### Example

---
```pycon
>>> from ju.oas import Routes
>>> routes = Routes(openapi_spec)
>>> api_functions = routes_to_funcs(routes, 'https://api.example.com')
>>> items = api_functions['get', '/items'](type='electronics')
```

### ho.base.update_spec(spec, path, method, description=None, param_types=None, param_descriptions=None, param_defaults=None, response_schema=None)

Update an OpenAPI spec with provided parameters for a specific path and method.

### Parameters

path
: The endpoint path.

method
: The HTTP method.

description
: New description to set.

param_types
: Parameter types to update.

param_descriptions
: Parameter descriptions to update.

param_defaults
: Parameter defaults to update.

response_schema
: Response schema to update.

### Returns

### ho.base.url_template_to_func(url_template, , method='get', description='', param_types=None, param_descriptions=None, param_defaults=None, response_schema=None, openapi_template=None, session=None, error_handler=None, timeout=30, egress=None, custom_headers=None)

Convert a URL template directly to a Python function.

### Parameters

> - Simple: {param_name}
> - With default: {param_name:default_value}
>   Examples:
> - “[https://example.com/mall](https://example.com/mall)/{store}/{item_id:1}”
> - “[https://www.google.com/search](https://www.google.com/search)?q={search_term}”

method
: HTTP method for the endpoint (default: “get”)

description
: Description of the endpoint

param_types
: Dictionary mapping parameter names to their types (string, integer, etc.)

param_descriptions
: Dictionary mapping parameter names to their descriptions

param_defaults
: Dictionary mapping parameter names to their default values

response_schema
: Schema for the response

openapi_template
: Custom OpenAPI template instead of using the minimal default

session
: A session object to use for requests

error_handler
: A function to handle request errors

timeout
: Request timeout in seconds

egress
: A function to process the response before returning

custom_headers
: Custom headers to include in all requests

### Returns

### Example

---
```pycon
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
```

```pycon
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
```

```pycon
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
```

### ho.base.url_template_to_openapi(url_template, , method='get', description='', param_types=None, param_descriptions=None, param_defaults=None, response_schema=None, openapi_template=None)

Convert a URL template with placeholders to an OpenAPI specification.

### Parameters

> - Simple: {param_name}
> - With default: {param_name:default_value}

method
: HTTP method for the endpoint (default: “get”)

description
: Description of the endpoint

param_types
: Dictionary mapping parameter names to their types

param_descriptions
: Dictionary mapping parameter names to their descriptions

param_defaults
: Dictionary mapping parameter names to their default values

response_schema
: Schema for the response

openapi_template
: Custom OpenAPI template to use instead of the default minimal one

### Returns
