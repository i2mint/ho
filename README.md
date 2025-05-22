# ho

Http Objects - Tools to make python interfaces to http services.

Technically speaking, this is lightweight Python library for turning URL templates and OpenAPI specifications into usable Python functions.

Informally speaking, this package gives you tools to make task-specific python objects that talk to the internet.

To install:	`pip install ho`

## Quick Start

The most common scenario: You have a URL template with placeholders and want to quickly create a Python function to make API calls:


```python
from ho import route_to_func

# Create a function from a URL template
search_google = route_to_func("https://www.google.com/search?q={search_term}")

# Use the function as if it were hand-written
results = search_google("python openapi")
results[:40] + '...' + results[-20:]
```




    '<!doctype html><html itemscope="" itemty...      </body></html>'



That's it! The library handles parameter extraction, HTTP requests, and response processing automatically.

Well. Not really "that's it". Of course, there's many more control parameters to extend this further. Let's have a look at a few.

## How It Works

This is what happened under the hood, when you do just a `func = route_to_func(url_template)`.

1. Parses your URL template
2. Generates an [OpenAPI Specification](https://www.openapis.org/) (formerly known as Swagger)
3. Creates a Python function with the correct signature based on this specification
4. Sets up all the necessary HTTP request handling

Of course, there's a much more direct route from a url template to a function. 
You can specify pretty much any aspect of a webservice API, using the OpenAPI Specification. 
We chose to go via the OpenAPI specification because it enables us to quickly connect to a 
[huge ecosystem of other tools](https://openapi.tools/) you'll then be able to use. 

The [OpenAPI Specification](https://swagger.io/specification/) is an [industry standard](https://theirstack.com/en/technology/openapi-specification) for describing HTTP APIs in a language-agnostic way. 
Today, most significant APIs publish such specifications, enabling automatic 
[code generation](https://openapi-generator.tech/docs/generators/) in various programming languages.

While traditional approaches often use static code generation, this library provides a dynamic runtime solution to create Python interfaces to HTTP services using OpenAPI specifications. 

Now, it's not always what you want. Once your API is stable, static code is usually a better idea. But in many cases, you don't want to have to generate static code, put it in your python path, import it, and all that jazz. 

This is when `ho` is the tool you want. 

## More Examples

### Path Parameters with Default Values


```python
# URL with path and query parameters including defaults
get_country = route_to_func(
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

This is to demo cases where the API needs authentication.

The example will work only if you have a GitHub token that you placed in an environmental variable called `GITHUB_TOKEN`.

(If you don't have one, go get one, it's free! We like free!)


```python
# API requiring authentication
import os 

github_api = route_to_func(
    "https://api.github.com/repos/{owner}/{repo}/issues",
    description="List issues for a repository",
    custom_headers={
        "Authorization": os.environ.get("GITHUB_TOKEN"),
        "Accept": "application/vnd.github.v3+json"
    }
)
```

Let's play with that:


```python
issues = github_api(owner="openai", repo="openai-python")

first_issue = issues[0] if issues else None
if first_issue:
    print(f"Issue fields: {list(first_issue)}")
    print(f"First issue title: {issues[0]['title']}")

```

    Issue fields: ['url', 'repository_url', 'labels_url', 'comments_url', 'events_url', 'html_url', 'id', 'node_id', 'number', 'title', 'user', 'labels', 'state', 'locked', 'assignee', 'assignees', 'milestone', 'comments', 'created_at', 'updated_at', 'closed_at', 'author_association', 'type', 'active_lock_reason', 'draft', 'pull_request', 'body', 'closed_by', 'reactions', 'timeline_url', 'performed_via_github_app', 'state_reason']
    First issue title: feat(api): return better error message on missing embedding


# More (non runnable) examples

The rest of these examples are not runnable, but just illustrative of the functionalities of `ho`.

### POST Requests with JSON Body


```python
# Creating resources with POST
create_item = route_to_func(
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
from ho import routes_to_funcs

# Load the OpenAPI spec
with open('api_spec.yaml', 'r') as f:
    spec = yaml.safe_load(f)

# Create functions for all endpoints
api_client = routes_to_funcs(spec, "https://api.example.com")

# Use the functions
users = api_client['get', '/users']()
user = api_client['get', '/users/{id}'](id=123)
```

Or convert them to a namespace for even easier access:


```python
from ho import routes_to_namespace

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

xml_api = route_to_func(
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

api = route_to_func(
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
