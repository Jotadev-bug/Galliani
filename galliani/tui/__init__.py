"""Spec 017: the interactive terminal UI. A wiring layer like `galliani.cli` (Decision 0034).

`session`, `commands` and `entry` import nothing from Textual or Rich; only `app`, `widgets` and
`styles` do (R1). Importing this package never imports Textual.
"""
