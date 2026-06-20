from urllib.parse import parse_qsl, urlencode

from django import template

register = template.Library()


@register.filter
def qs_without_page(qs):
    """Return a urlencoded querystring from `qs` with the `page` key removed."""
    pairs = parse_qsl(qs or "", keep_blank_values=True)
    return urlencode([(k, v) for k, v in pairs if k != "page"])
