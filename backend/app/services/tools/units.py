"""Common measurement conversions using a table of SI factors."""

from typing import Any

from app.services.tools.base import Tool, ToolContext, ToolInputError, ToolResult
from app.services.tools.calculator import format_number

# fmt: off
# category -> unit -> factor to the category's base unit
_UNITS: dict[str, dict[str, float]] = {
    "length": {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "in": 0.0254, "ft": 0.3048,
        "yd": 0.9144, "mi": 1609.344, "nmi": 1852.0, "um": 1e-6, "nm": 1e-9,
    },
    "mass": {
        "mg": 1e-6, "g": 0.001, "kg": 1.0, "t": 1000.0, "oz": 0.028349523125, "lb": 0.45359237,
        "st": 6.35029318, "ug": 1e-9,
    },
    "volume": {
        "ml": 0.001, "cl": 0.01, "dl": 0.1, "l": 1.0, "m3": 1000.0, "cm3": 0.001, "tsp": 0.00492892159375,
        "tbsp": 0.01478676478125, "floz": 0.0295735295625, "cup": 0.2365882365, "pt": 0.473176473,
        "qt": 0.946352946, "gal": 3.785411784, "ukgal": 4.54609,
    },
    "area": {
        "mm2": 1e-6, "cm2": 1e-4, "m2": 1.0, "km2": 1e6, "ha": 1e4, "acre": 4046.8564224,
        "ft2": 0.09290304, "in2": 0.00064516, "mi2": 2589988.110336, "yd2": 0.83612736,
    },
    "time": {
        "ms": 0.001, "s": 1.0, "min": 60.0, "h": 3600.0, "day": 86400.0, "week": 604800.0,
        "month": 2629746.0, "year": 31556952.0,
    },
    "speed": {"m/s": 1.0, "km/h": 1 / 3.6, "mph": 0.44704, "knot": 0.514444444, "ft/s": 0.3048},
    "data": {
        "bit": 0.125, "b": 1.0, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
        "kib": 1024.0, "mib": 1024.0**2, "gib": 1024.0**3, "tib": 1024.0**4,
    },
    "energy": {"j": 1.0, "kj": 1000.0, "cal": 4.184, "kcal": 4184.0, "wh": 3600.0, "kwh": 3.6e6, "btu": 1055.05585262},
    "pressure": {"pa": 1.0, "kpa": 1000.0, "bar": 1e5, "atm": 101325.0, "psi": 6894.757293168, "mmhg": 133.322387415},
    "power": {"w": 1.0, "kw": 1000.0, "mw": 1e6, "hp": 745.69987158227022},
}
_TEMPERATURE = {"c", "f", "k"}

_ALIASES = {
    # length
    "millimeter": "mm", "millimetre": "mm", "centimeter": "cm", "centimetre": "cm", "meter": "m", "metre": "m",
    "kilometer": "km", "kilometre": "km", "inch": "in", "inches": "in", '"': "in", "foot": "ft", "feet": "ft",
    "'": "ft", "yard": "yd", "mile": "mi", "nautical mile": "nmi", "micrometer": "um", "µm": "um", "nanometer": "nm",
    # mass
    "milligram": "mg", "gram": "g", "kilogram": "kg", "kilo": "kg", "kgs": "kg", "tonne": "t", "metric ton": "t",
    "ounce": "oz", "pound": "lb", "lbs": "lb", "stone": "st", "microgram": "ug", "µg": "ug",
    # volume
    "milliliter": "ml", "millilitre": "ml", "liter": "l", "litre": "l", "cubic meter": "m3", "m³": "m3",
    "cc": "cm3", "teaspoon": "tsp", "tablespoon": "tbsp", "fluid ounce": "floz", "fl oz": "floz", "cups": "cup",
    "pint": "pt", "quart": "qt", "gallon": "gal", "us gallon": "gal", "imperial gallon": "ukgal",
    # area
    "m²": "m2", "km²": "km2", "sq m": "m2", "square meter": "m2", "square metre": "m2", "square kilometer": "km2",
    "hectare": "ha", "acres": "acre", "sq ft": "ft2", "square foot": "ft2", "square feet": "ft2", "sq mi": "mi2",
    "square mile": "mi2",
    # time
    "millisecond": "ms", "sec": "s", "second": "s", "minute": "min", "mins": "min", "hour": "h", "hr": "h",
    "hrs": "h", "days": "day", "d": "day", "weeks": "week", "months": "month", "years": "year", "yr": "year",
    # speed
    "kph": "km/h", "kmh": "km/h", "kmph": "km/h", "mps": "m/s", "miles per hour": "mph", "knots": "knot", "kn": "knot",
    # data
    "bits": "bit", "byte": "b", "bytes": "b", "kilobyte": "kb", "megabyte": "mb", "gigabyte": "gb", "terabyte": "tb",
    # energy / pressure / power
    "joule": "j", "kilojoule": "kj", "calorie": "cal", "kilocalorie": "kcal", "kilowatt hour": "kwh",
    "pascal": "pa", "kilopascal": "kpa", "atmosphere": "atm", "watt": "w", "kilowatt": "kw", "horsepower": "hp",
    # temperature
    "celsius": "c", "°c": "c", "degc": "c", "fahrenheit": "f", "°f": "f", "degf": "f", "kelvin": "k",
}

# fmt: on


def normalise_unit(unit: str) -> str:
    key = unit.strip().lower().replace("degrees ", "").replace("degree ", "")
    if key in _ALIASES:
        return _ALIASES[key]
    if key.endswith("s") and key[:-1] in _ALIASES:
        return _ALIASES[key[:-1]]
    if key.endswith("es") and key[:-2] in _ALIASES:
        return _ALIASES[key[:-2]]
    return key


def _category(unit: str) -> str | None:
    if unit in _TEMPERATURE:
        return "temperature"
    for category, units in _UNITS.items():
        if unit in units:
            return category
    return None


def _convert_temperature(value: float, src: str, dst: str) -> float:
    celsius = {"c": value, "f": (value - 32) * 5 / 9, "k": value - 273.15}[src]
    return {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15}[dst]


def convert(value: float, from_unit: str, to_unit: str) -> float:
    src, dst = normalise_unit(from_unit), normalise_unit(to_unit)
    src_cat, dst_cat = _category(src), _category(dst)
    if src_cat is None:
        raise ToolInputError(f"unknown unit '{from_unit}'")
    if dst_cat is None:
        raise ToolInputError(f"unknown unit '{to_unit}'")
    if src_cat != dst_cat:
        raise ToolInputError(f"cannot convert {src_cat} ({from_unit}) to {dst_cat} ({to_unit})")
    if src_cat == "temperature":
        return _convert_temperature(value, src, dst)
    return value * _UNITS[src_cat][src] / _UNITS[dst_cat][dst]


async def _handle(args: dict[str, Any], _ctx: ToolContext) -> ToolResult:
    try:
        value = float(args["value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolInputError("'value' must be a number") from exc
    from_unit, to_unit = str(args.get("from_unit", "")), str(args.get("to_unit", ""))
    result = format_number(round(convert(value, from_unit, to_unit), 10))
    text = f"{format_number(value)} {from_unit} = {result} {to_unit}"
    return ToolResult(content=text, summary=text)


unit_convert_tool = Tool(
    name="unit_convert",
    label="Unit conversion",
    description=(
        "Convert a value between common measurement units: length, mass, volume, area, time, speed, "
        "digital storage, energy, pressure, power and temperature (C/F/K)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "from_unit": {"type": "string", "description": "e.g. 'km', 'lb', '°F', 'mph'"},
            "to_unit": {"type": "string"},
        },
        "required": ["value", "from_unit", "to_unit"],
    },
    handler=_handle,
    timeout_seconds=2.0,
)
