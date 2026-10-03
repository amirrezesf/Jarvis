"""
Per-student context.

Bundles the identity information the listener needs: name variants for
the trigger detector, and user_name + field for the LLM identity block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field  as dc_field

from jarvis import config


def generate_name_variants(user_name: str) -> list[str]:
    """Derive matching variants from a full name.

    Deliberately excludes first-name-only variants: other students may
    share the first name, and precision matters more than recall.
    """
    name = user_name.strip()
    if not name:
        return []

    variants: list[str] = [name]

    parts = re.split(r"\s+", name)
    if len(parts) >= 2:
        last = parts[-1].strip()
        if last and last != name:
            variants.append(last)

        first_token = parts[0]
        if "\u200c" in first_token:
            expanded = " ".join(
                p.replace("\u200c", " ") for p in parts
            )
            expanded = re.sub(r"\s+", " ", expanded).strip()
            if expanded != name:
                variants.append(expanded)

    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


@dataclass
class StudentContext:
    user_name: str
    field: str = ""
    name_variants: list[str] = dc_field(default_factory=list)

    @classmethod
    def from_user(cls, user: dict) -> "StudentContext":
        """Build from a structure.json user entry (SkyroomBot path)."""
        name = str(user.get("user_name", "")).strip()
        field_name = str(user.get("field", "")).strip()

        explicit = user.get("name_variants")
        if isinstance(explicit, list) and explicit:
            variants = [str(v).strip() for v in explicit if str(v).strip()]
        else:
            variants = generate_name_variants(name)

        return cls(user_name=name, field=field_name, name_variants=variants)

    @classmethod
    def from_config(cls) -> "StudentContext":
        """Fallback for standalone Jarvis: reads config.NAME_VARIANTS."""
        variants = list(config.NAME_VARIANTS)
        name = next(
            (v for v in variants if " " in v or "\u200c" in v),
            variants[0] if variants else "",
        )
        return cls(user_name=name, field="", name_variants=variants)