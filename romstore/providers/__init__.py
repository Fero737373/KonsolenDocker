"""Catalog adapters at the boundary to legal homebrew sources."""

from .homebrew_hub import HomebrewHubProvider
from .libretro import LibretroContentProvider

__all__ = ["HomebrewHubProvider", "LibretroContentProvider"]
