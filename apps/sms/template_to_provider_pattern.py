"""
SMS Template → Provider Pattern Converter.

Converts Django template variable syntax ({{ variable_name }}) to
MeliPayamak-style positional placeholders ({0}, {1}, {2}, ...).

Usage:
    from apps.sms.template_to_provider_pattern import convert_template_to_pattern

    result = convert_template_to_pattern(
        "«{{ company_name }}»\\nفاکتور {{ invoice_number }}\\nمبلغ: {{ invoice_amount }}"
    )
    result.pattern_text  # "«{0}»\\nفاکتور {1}\\nمبلغ: {2}"
    result.variable_map  # [("company_name", 0), ("invoice_number", 1), ("invoice_amount", 2)]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Matches {{ variable_name }} with optional spaces and optional filters
_DJANGO_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*?)(?:\s*\|[^}]*)?\s*\}\}")


@dataclass
class PatternConversionResult:
    """Result of converting a Django template to provider pattern format."""
    pattern_text: str
    variable_map: list[tuple[str, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def convert_template_to_pattern(
    template_text: str,
    variables_order: list[str] | str | None = None,
) -> PatternConversionResult:
    """
    Convert Django template variables to positional placeholders.

    Args:
        template_text: Django template text with {{ var }} syntax
        variables_order: Optional explicit variable order (comma-separated string or list).
                        If provided, numbering follows this order.
                        If None, uses first-appearance order.

    Returns:
        PatternConversionResult with pattern_text, variable_map, and warnings.

    Examples:
        >>> r = convert_template_to_pattern("{{ company_name }}\\nمبلغ: {{ amount }}")
        >>> r.pattern_text
        '{0}\\nمبلغ: {1}'
        >>> r.variable_map
        [('company_name', 0), ('amount', 1)]
    """
    if not template_text:
        return PatternConversionResult(pattern_text="", variable_map=[], warnings=[])

    # Parse variables_order if provided as string
    order_list: list[str] | None = None
    if variables_order:
        if isinstance(variables_order, str):
            order_list = [v.strip() for v in variables_order.replace(";", ",").split(",") if v.strip()]
        else:
            order_list = list(variables_order)

    # Find all variable occurrences in order
    found_vars: list[str] = []
    warnings: list[str] = []

    for match in _DJANGO_VAR_PATTERN.finditer(template_text):
        var_name = match.group(1).strip()
        if var_name not in found_vars:
            found_vars.append(var_name)
        # Check for filters (unsupported but safe)
        full_match = match.group(0)
        if "|" in full_match:
            warnings.append(f"متغیر '{var_name}' دارای فیلتر است و ممکن است در پترن Provider ساپورت نشود.")

    # Determine numbering
    if order_list:
        # Use explicit order for numbering
        var_to_index: dict[str, int] = {}
        for i, var in enumerate(order_list):
            var_to_index[var] = i
        # Add any found vars not in order_list at the end
        next_idx = len(order_list)
        for var in found_vars:
            if var not in var_to_index:
                var_to_index[var] = next_idx
                next_idx += 1
                warnings.append(f"متغیر '{var}' در ترتیب متغیرها تعریف نشده و به انتها اضافه شد.")
    else:
        # Use first-appearance order
        var_to_index = {var: i for i, var in enumerate(found_vars)}

    # Replace variables with positional placeholders
    def replace_var(match):
        var_name = match.group(1).strip()
        idx = var_to_index.get(var_name, 0)
        return "{" + str(idx) + "}"

    pattern_text = _DJANGO_VAR_PATTERN.sub(replace_var, template_text)

    # Build variable map (sorted by index)
    variable_map = sorted(var_to_index.items(), key=lambda x: x[1])

    return PatternConversionResult(
        pattern_text=pattern_text,
        variable_map=[(name, idx) for name, idx in variable_map],
        warnings=warnings,
    )


def format_variable_map_display(variable_map: list[tuple[str, int]]) -> str:
    """
    Format variable map for display in the owner panel.

    Returns multi-line string like:
        {0} = company_name
        {1} = invoice_number
    """
    lines = [f"{{{idx}}} = {name}" for name, idx in variable_map]
    return "\n".join(lines)
