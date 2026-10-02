from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        number = Decimal(str(value or 0))
        digits = 0 if number == number.to_integral_value() else 2
        return format(number, f",.{digits}f").replace(",", " ").replace(".", ",") + " ₸"
    except (InvalidOperation, ValueError):
        return "—"
