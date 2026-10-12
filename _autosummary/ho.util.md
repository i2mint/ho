# ho.util

Utils for HO

### Functions

| [`extract_placeholders`](#ho.util.extract_placeholders)(url_template)   | Extract all placeholders from a URL template, including their inline defaults.   |
|---------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|

### Classes

| [`SimpleMappingNamespace`](#ho.util.SimpleMappingNamespace)   | A simple mapping namespace that allows attribute access and dictionary-like access.   |
|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------|

### *class* ho.util.SimpleMappingNamespace

Bases: [`SimpleNamespace`](https://docs.python.org/3/library/types.html#types.SimpleNamespace), [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

A simple mapping namespace that allows attribute access and dictionary-like access.

```pycon
>>> s = SimpleMappingNamespace(a=1, b=2)
>>> list(s)
['a', 'b']
>>> s.a
1
>>> s['b']
2
```

### ho.util.extract_placeholders(url_template)

Extract all placeholders from a URL template, including their inline defaults.

### Parameters

### Returns

### Example

---
```pycon
>>> extract_placeholders("https://example.com/{category:books}/items?page={page:1}&limit={limit:10}")
{'category': 'books', 'page': '1', 'limit': '10'}
```
