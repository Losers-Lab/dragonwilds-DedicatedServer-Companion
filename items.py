"""
Dragonwilds Master Item Catalog Module.

Loads 1,704 official game items extracted directly from Unreal Engine server pak files.
Provides fast search by item identifier, category, and display name.
"""

import os
import json

_catalog_cache = None


def get_master_items(category: str = None, search_query: str = None) -> list:
    """Returns official master items with optional category and keyword filtering."""
    global _catalog_cache
    if _catalog_cache is None:
        data_path = os.path.join(os.path.dirname(__file__), "data", "master_items.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                _catalog_cache = json.load(f)
        else:
            _catalog_cache = []

    results = _catalog_cache
    if category and category.lower() != "all":
        results = [it for it in results if it.get("category", "").lower() == category.lower()]

    if search_query:
        q = search_query.lower()
        results = [
            it for it in results
            if q in it.get("name", "").lower() or q in it.get("id", "").lower() or q in it.get("category", "").lower()
        ]

    return results
