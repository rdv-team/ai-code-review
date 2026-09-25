"""Public facade for task-local reference catalogs."""

from .service import (
    ReferenceCatalogError,
    build_reference_catalog,
    load_reference_catalog,
    resolve_reference_id,
    write_reference_catalog,
)

__all__ = [
    "ReferenceCatalogError",
    "build_reference_catalog",
    "load_reference_catalog",
    "resolve_reference_id",
    "write_reference_catalog",
]
