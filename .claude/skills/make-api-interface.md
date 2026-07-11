# Skill: Make a Python Interface to an HTTP API Using `ho`

Use this skill when asked to create a Python interface/wrapper/client for an
HTTP API, REST service, or web endpoint.

## Overview

The `ho` package turns URL templates and OpenAPI specifications into callable
Python functions at runtime. See the project [README.md](../../README.md) for
full documentation and examples.

## Quick Reference

### Simplest Case: One URL → One Function

```python
from ho import route_to_func

func = route_to_func("https://api.example.com/endpoint/{param}")
result = func(param="value")
```

### With Customization

```python
import os
from ho import route_to_func

func = route_to_func(
    "https://api.example.com/v1/{resource}?limit={limit:10}&offset={offset:0}",
    method="get",                          # HTTP method (default: "get")
    description="Fetch resources",         # Becomes the docstring summary
    param_types={"limit": "integer", "offset": "integer"},  # OpenAPI types
    param_descriptions={"resource": "The resource type to fetch"},
    custom_headers={                       # Auth, content type, etc.
        "Authorization": f"Bearer {os.environ.get('API_TOKEN', '')}",
        "Accept": "application/json",
    },
    egress=lambda r: r.json(),             # Custom response processing
    timeout=60,                            # Request timeout in seconds
)
```

### Full OpenAPI Spec → Multiple Functions

```python
import yaml
from ho import routes_to_funcs
from ho.base import routes_to_namespace

# Load an OpenAPI spec (YAML or JSON)
with open("openapi.yaml") as f:
    spec = yaml.safe_load(f)

# Option A: Dict of functions keyed by (method, endpoint)
funcs = routes_to_funcs(spec, "https://api.example.com")
users = funcs["get", "/users"]()

# Option B: Namespace with dot access
api = routes_to_namespace(spec, "https://api.example.com")
users = api.get_users()
```

## Step-by-Step: Wrapping an API

Follow these steps when building an interface for a specific API:

### 1. Find the API Documentation

- Look for an OpenAPI/Swagger spec (`.yaml` or `.json`). Many APIs publish one.
- Check common locations: `https://api.example.com/openapi.json`,
  `https://api.example.com/swagger.json`, `https://api.example.com/v3/api-docs`
- If no spec exists, read the API docs and construct URL templates manually.
- See the companion skill `find-openapi-spec.md` for help locating specs.

### 2. Identify Authentication

Common patterns and how to handle them with `ho`:

| Auth Type | `custom_headers` value |
|-----------|----------------------|
| Bearer token | `{"Authorization": "Bearer TOKEN"}` |
| API key in header | `{"X-API-Key": "KEY"}` |
| API key in query | Add `?api_key={api_key}` to the URL template |
| Basic auth | `{"Authorization": "Basic BASE64"}` |

Always read secrets from environment variables, never hardcode them:
```python
import os
headers = {"Authorization": f"Bearer {os.environ['MY_API_TOKEN']}"}
```

### 3. Create the Functions

**For a small API (1-5 endpoints):** Create individual functions with
`route_to_func`, giving each a descriptive name and docstring.

```python
from ho import route_to_func

list_items = route_to_func(
    "https://api.example.com/items?page={page:1}&per_page={per_page:20}",
    description="List all items with pagination",
    param_types={"page": "integer", "per_page": "integer"},
    name="list_items",
)

get_item = route_to_func(
    "https://api.example.com/items/{item_id}",
    description="Get a single item by ID",
    name="get_item",
)

create_item = route_to_func(
    "https://api.example.com/items",
    method="post",
    description="Create a new item",
    param_types={"name": "string", "price": "number"},
    name="create_item",
)
```

**For a large API (full OpenAPI spec):** Use `routes_to_namespace` for a
clean namespace.

### 4. Handle Response Processing

The default egress tries JSON → text → binary. Override for special cases:

```python
# Return raw Response object
raw_func = route_to_func(url, egress=lambda r: r)

# Parse XML
import xml.etree.ElementTree as ET
xml_func = route_to_func(url, egress=lambda r: ET.fromstring(r.text))

# Extract specific field
data_func = route_to_func(url, egress=lambda r: r.json()["data"])
```

### 5. Package It Up

For a reusable module, group related functions:

```python
"""my_api_client.py - Python interface to MyAPI"""

import os
from ho import route_to_func

_BASE = "https://api.myservice.com/v2"
_HEADERS = {"Authorization": f"Bearer {os.environ.get('MYAPI_TOKEN', '')}"}

list_users = route_to_func(
    f"{_BASE}/users?limit={{limit:50}}",
    custom_headers=_HEADERS,
    name="list_users",
)

get_user = route_to_func(
    f"{_BASE}/users/{{user_id}}",
    custom_headers=_HEADERS,
    name="get_user",
)
```

## Key Parameters Cheatsheet

| Parameter | Type | Purpose |
|-----------|------|---------|
| `route` | str/dict/Route/tuple | URL template, OpenAPI spec, or Route object |
| `base_url` | str | Base URL (extracted from URL template if not given) |
| `method` | str | HTTP method: "get", "post", "put", "delete", "patch" |
| `custom_headers` | dict | Headers for auth, content-type, etc. |
| `egress` | callable | `Response → return_value` processing |
| `error_handler` | callable | `(response, exception) → value` error handling |
| `timeout` | int | Seconds before request times out (default: 30) |
| `param_types` | dict | `{name: openapi_type}` — "string", "integer", "number", "boolean" |
| `param_defaults` | dict | `{name: default_value}` |
| `param_descriptions` | dict | `{name: description}` |
| `name` | str | Function name (auto-generated if not given) |
| `description` | str | Endpoint description (becomes docstring summary) |
| `session` | requests.Session | Reuse connections, cookies, etc. |

## URL Template Syntax

- Path parameters: `/users/{id}` → `func(id=123)`
- Query parameters: `/search?q={query}` → `func(query="test")`
- Inline defaults: `/items?page={page:1}&limit={limit:20}` → `func()` uses defaults
- Mixed: `/v1/{resource}/search?q={query}&limit={limit:10}`

## Tips

- Use `inspect.signature(func)` to verify the generated function signature
- The generated function's `__doc__` shows endpoint info and parameters
- For APIs requiring session state (cookies, connection pooling), pass a
  `requests.Session` instance
- Use `routes_to_funcs(..., name_as_key=True)` for function-name-keyed dicts
