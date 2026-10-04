"""Provider adapters (spec 003 R5, Decision 0012).

Modules here may import provider SDKs or the legacy `app` provider stack. Core `galliani/*.py` modules
must never import this package; they only see `galliani.adapters.ProviderAdapter`.
"""
