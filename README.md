# ho

Http Objects - Tools to make python interfaces to http services.
Technically speaking, this is lightweight Python library for turning URL templates and OpenAPI specifications into usable Python functions.
Informally speaking, this package gives you tools to make task-specific python objects that talk to the internet. 

To install:	```pip install ho```


## Quick Start

The most common scenario: You have a URL template with placeholders and want to quickly create a Python function to make API calls:

```python
from ho.oas import template_to_func

# Create a function from a URL template
search_google = template_to_func(
    "https://www.google.com/search?q={search_term}",
    description="Search Google",
    egress=lambda response: response.text  # Return HTML instead of trying to parse JSON
)

# Use the function as if it were hand-written
results = search_google(search_term="python openapi")
```

That's it! The library handles parameter extraction, HTTP requests, and response processing automatically.

## How It Works

Under the hood, this library:

1. Parses your URL template
2. Generates an [OpenAPI Specification](https://www.openapis.org/) (formerly known as Swagger)
3. Creates a Python function with the correct signature based on this specification
4. Sets up all the necessary HTTP request handling

The OpenAPI Specification is an industry standard for describing HTTP APIs in a language-agnostic way. Today, most significant APIs publish such specifications, enabling automatic code generation in various programming languages.

While traditional approaches often use static code generation, this library provides a dynamic runtime solution to create Python interfaces to HTTP services using OpenAPI specifications.

## More Examples

### Path Parameters with Default Values

```python
# URL with path and query parameters including defaults
get_country = template_to_func(
    "https://restcountries.com/v3.1/name/{country_name}?fullText={full_text:false}",
    description="Get country information by name",
    param_types={"country_name": "string", "full_text": "boolean"}
)

# Call with required parameters, using defaults for the rest
countries = get_country(country_name="germany")

# Or override the defaults
exact_match = get_country(country_name="germany", full_text=True)
```

### Custom Headers and Authentication

```python
# API requiring authentication
github_api = template_to_func(
    "https://api.github.com/repos/{owner}/{repo}/issues",
    description="List issues for a repository",
    custom_headers={
        "Authorization": "Bearer YOUR_TOKEN_HERE",
        "Accept": "application/vnd.github.v3+json"
    }
)

issues = github_api(owner="openai", repo="openai-python")
```

### POST Requests with JSON Body

```python
# Creating resources with POST
create_item = template_to_func(
    "https://api.example.com/items",
    method="post",
    description="Create a new item",
    param_types={"name": "string", "price": "number"}
)

new_item = create_item(name="New Product", price=19.99)
```

### Working with Full OpenAPI Specifications

If you have an existing OpenAPI specification file:

```python
import yaml
from ho.oas import routes_to_functions

# Load the OpenAPI spec
with open('api_spec.yaml', 'r') as f:
    spec = yaml.safe_load(f)

# Create functions for all endpoints
api_client = routes_to_functions(spec, "https://api.example.com")

# Use the functions
users = api_client['get', '/users']()
user = api_client['get', '/users/{id}'](id=123)
```

Or convert them to a namespace for even easier access:

```python
from ho.oas import routes_to_namespace

# Create a namespace with all API functions
api = routes_to_namespace(spec, "https://api.example.com")

# Access functions by their generated names
users = api.get_users()
user = api.get_users_id_(id=123)
```

## Advanced Features

### Custom Response Processing

```python
def process_xml_response(response):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(response.text)
    # Process the XML
    return {"processed": True, "data": root}

xml_api = template_to_func(
    "https://api.example.com/xml/{resource}",
    egress=process_xml_response
)
```

### Error Handling

```python
def custom_error_handler(response, exception=None):
    if exception:
        print(f"Request failed: {exception}")
        return {"error": str(exception)}
    
    if response.status_code >= 400:
        print(f"API error: {response.status_code}")
        return {"error": response.text}
    
    return response

api = template_to_func(
    "https://api.example.com/{resource}",
    error_handler=custom_error_handler
)
```

## Why Use This Library?

1. **No Code Generation**: Unlike traditional OpenAPI tools that generate static code, this library creates functions dynamically at runtime.
2. **Simplified Interface**: Turn complex HTTP API calls into simple Python function calls.
3. **Type Hints and Documentation**: Generated functions include proper signatures and docstrings.
4. **Flexibility**: Works with both simple URL templates and complete OpenAPI specifications.
5. **Lightweight**: No complex dependencies or build processes required.

## Comparison to Other Tools

Most OpenAPI tools like [OpenAPI Generator](https://openapi-generator.tech/) generate static code in multiple languages. This approach requires a build step and often results in large codebases. Our library provides a lightweight alternative with dynamic function creation at runtime, which is perfect for Python's dynamic nature and for rapid prototyping.

## Installation

```bash
pip install ho-openapi
```

## License

MIT