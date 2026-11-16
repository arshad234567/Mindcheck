"""Custom template filters used across MindCheck templates."""

from django import template

register = template.Library()


@register.filter
def tier_class(tier):
    """'moderate' -> 'tier-moderate' (colour classes are defined in static/css/style.css)."""
    return f"tier-{tier}" if tier else "tier-none"


TOOL_ICONS = {"phq-9": "bi-cloud-drizzle", "gad-7": "bi-wind", "who-5": "bi-sun"}


@register.filter
def tool_icon(slug):
    """Bootstrap Icons class shown on each questionnaire card (display only)."""
    return TOOL_ICONS.get(slug, "bi-clipboard2-pulse")


@register.filter
def percent_of(value, maximum):
    """Score as a whole-number percentage of the maximum, for progress bars."""
    try:
        value, maximum = float(value), float(maximum)
    except (TypeError, ValueError):
        return 0
    if maximum <= 0:
        return 0
    return max(0, min(100, round(value * 100 / maximum)))


@register.filter
def field_number(bound_field):
    """Question number stored on a dynamic ScreeningForm field."""
    return getattr(bound_field.field, "number", "")


@register.simple_tag
def query_with(querystring, **kwargs):
    """Rebuild a GET query string with extra values, used by pagination links."""
    parts = [querystring] if querystring else []
    parts += [f"{k}={v}" for k, v in kwargs.items()]
    return "?" + "&".join(parts)
