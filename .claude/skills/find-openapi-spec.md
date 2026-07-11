# Skill: Find an OpenAPI Specification for a Service

Use this skill when you need to locate an OpenAPI (Swagger) specification for
an API so it can be used with `ho` to generate Python functions.

## Strategy

Try these approaches in order. Stop as soon as you find a usable spec.

### 1. Check Well-Known URLs

Many APIs serve their OpenAPI spec at standard paths. Try fetching these
(replace `BASE` with the API's base URL):

```
{BASE}/openapi.json
{BASE}/openapi.yaml
{BASE}/swagger.json
{BASE}/swagger.yaml
{BASE}/api-docs
{BASE}/v3/api-docs
{BASE}/docs/openapi.json
{BASE}/.well-known/openapi.json
{BASE}/api/openapi.json
{BASE}/api/swagger.json
```

Use `curl -s -o /dev/null -w "%{http_code}" URL` to quickly check which
return 200.

### 2. Check the API Documentation Site

- Look for "API Reference", "Swagger UI", or "OpenAPI" links on the docs site
- Swagger UI pages often load the spec from a URL visible in the browser
  network tab or in the page source (search for `url:` or `spec-url`)
- Look for download links for the spec in YAML/JSON format

### 3. Search Public Directories

These directories aggregate OpenAPI specs:

- **APIs.guru**: https://apis.guru/ — Large curated directory
  - API: `https://api.apis.guru/v2/list.json` (lists all specs)
  - Search: `https://api.apis.guru/v2/{provider}.json`
- **SwaggerHub**: https://app.swaggerhub.com/search — Swagger's hosted registry
- **Postman**: https://www.postman.com/explore — Collections often have OpenAPI
- **RapidAPI**: https://rapidapi.com/ — API marketplace with specs
- **GitHub search**: `openapi.json` or `swagger.json` in the API's org

### 4. Search GitHub

```bash
# Search for OpenAPI specs in the API provider's GitHub org
gh search code "openapi" --owner=ORGNAME --filename=openapi
gh search code "swagger" --owner=ORGNAME --extension=json
gh search code "swagger" --owner=ORGNAME --extension=yaml

# Search more broadly
gh search repos "SERVICENAME openapi spec"
```

### 5. Use apis.guru API Programmatically

```python
import requests

# List all available APIs
all_apis = requests.get("https://api.apis.guru/v2/list.json").json()

# Search for a specific provider (e.g., "github", "stripe", "twilio")
provider = "github.com"
if provider in all_apis:
    api_info = all_apis[provider]
    # Get the preferred version's spec URL
    preferred = api_info["preferred"]
    spec_url = api_info["versions"][preferred]["swaggerUrl"]
    print(f"Spec URL: {spec_url}")
```

### 6. Web Search

Search for:
- `"SERVICENAME" openapi specification`
- `"SERVICENAME" swagger.json`
- `"SERVICENAME" API spec yaml`
- `site:github.com "SERVICENAME" openapi.yaml`

### 7. Construct from Documentation (Last Resort)

If no spec exists, build one manually from the API docs:

```python
from ho.base import url_template_to_openapi

# Build spec endpoint by endpoint
spec = url_template_to_openapi(
    "https://api.example.com/v1/users/{user_id}",
    method="get",
    description="Get user by ID",
    param_types={"user_id": "string"},
)

# Or construct the OpenAPI dict directly
spec = {
    "openapi": "3.0.3",
    "info": {"title": "MyAPI", "version": "1.0"},
    "servers": [{"url": "https://api.example.com/v1"}],
    "paths": {
        "/users/{user_id}": {
            "get": {
                "summary": "Get user by ID",
                "parameters": [{
                    "name": "user_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"}
                }],
                "responses": {"200": {"description": "Success"}}
            }
        }
    }
}
```

## Using a Found Spec with `ho`

Once you have a spec (dict, file path, or URL):

```python
import yaml  # or json
import requests as req
from ho import routes_to_funcs
from ho.base import routes_to_namespace

# From a URL
spec = req.get("https://api.example.com/openapi.json").json()

# From a file
with open("openapi.yaml") as f:
    spec = yaml.safe_load(f)

# Create functions
api = routes_to_namespace(spec, "https://api.example.com")

# Or selective functions
funcs = routes_to_funcs(spec, "https://api.example.com")
get_users = funcs["get", "/users"]
```

## Validating a Spec

Quick sanity checks before using a spec:

```python
# Check it has the expected structure
assert "paths" in spec, "Not a valid OpenAPI spec"
assert "openapi" in spec, "Missing openapi version field"

# List available endpoints
for path, methods in spec["paths"].items():
    for method in methods:
        if method in ("get", "post", "put", "delete", "patch"):
            print(f"  {method.upper()} {path}")
```

## Common Gotchas

- Some specs use `$ref` extensively — `ho` (via `ju`) handles most refs but
  deeply nested `$ref` chains may need resolution first
- Specs may have `servers[0].url` that differs from the actual base URL — pass
  `base_url` explicitly to override
- Large specs (hundreds of endpoints) work fine but namespace attribute names
  are auto-generated and may be awkward — use `routes_to_funcs` with
  `name_as_key=True` and inspect the keys
