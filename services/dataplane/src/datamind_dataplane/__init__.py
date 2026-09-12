"""Internal DataMind capability MCP service."""

__all__ = ["DataPlaneServiceFactory", "DataPlaneServices"]


def __getattr__(name: str):
    # Keep lightweight modules such as ``authorization`` importable without
    # requiring the optional DataMind vendor wheel.  The service classes are
    # loaded only when explicitly requested.
    if name in __all__:
        from .services import DataPlaneServiceFactory, DataPlaneServices
        return {"DataPlaneServiceFactory": DataPlaneServiceFactory,
                "DataPlaneServices": DataPlaneServices}[name]
    raise AttributeError(name)
