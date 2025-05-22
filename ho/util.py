"""Utils for HO"""

from typing import Mapping
from types import SimpleNamespace


class SimpleMappingNamespace(SimpleNamespace, Mapping):
    """
    A simple mapping namespace that allows attribute access and dictionary-like access.

    >>> s = SimpleMappingNamespace(a=1, b=2)
    >>> list(s)
    ['a', 'b']
    >>> s.a
    1
    >>> s['b']
    2
    """

    def __getitem__(self, key):
        # This allows dictionary-style access (obj['key'])
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __len__(self):
        # This defines the length (number of attributes)
        return len(self.__dict__)

    def __iter__(self):
        # This allows iteration over keys (attribute names)
        return iter(self.__dict__)


def extract_placeholders(url_template: str):
    """
    Extract all placeholders from a URL template, including their inline defaults.

    Parameters:
    -----------
    url_template : str
        URL template with placeholders

    Returns:
    --------
    dict
        A dictionary mapping parameter names to their default values (if specified)

    Example:
    --------
    >>> extract_placeholders("https://example.com/{category:books}/items?page={page:1}&limit={limit:10}")
    {'category': 'books', 'page': '1', 'limit': '10'}
    """
    import re
    from urllib.parse import urlparse

    placeholders = {}

    # Find all placeholder patterns {name} or {name:default}
    placeholder_pattern = re.compile(r"\{([^{}]+)\}")

    # Parse the URL to process both path and query
    parsed_url = urlparse(url_template)
    full_path = (
        parsed_url.path + "?" + parsed_url.query
        if parsed_url.query
        else parsed_url.path
    )

    # Extract all placeholders
    for match in placeholder_pattern.finditer(full_path):
        param_content = match.group(1)
        if ":" in param_content:
            param_name, default_value = param_content.split(":", 1)
            placeholders[param_name] = default_value
        else:
            placeholders[param_content] = None

    return placeholders
