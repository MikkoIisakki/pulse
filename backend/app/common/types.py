"""Shared domain types used across module boundaries.

Only primitive building blocks belong here. Domain-specific types live
in their own modules (e.g. storage/models.py, signals/models.py).
"""

from typing import NewType

AssetSymbol = NewType("AssetSymbol", str)
