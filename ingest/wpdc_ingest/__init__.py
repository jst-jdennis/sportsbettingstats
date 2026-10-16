"""Wagering Policy Data Center ingestion layer.

Design (see docs/design/03-ingestion-and-review.md):

- One module per source under ``wpdc_ingest.sources``.
- Every module implements the :class:`wpdc_ingest.core.source.Source` protocol:
  ``discover`` -> ``fetch`` -> ``parse`` -> ``normalize``.
- ``parse`` is a pure function tested against fixture documents. It raises
  :class:`LayoutChanged` rather than guessing when a document does not match
  the layout it was written for.
- Every fetched document is hashed and stored under ``archive/raw`` before
  parsing, and a Wayback capture is requested.
- Rows are written with ``status: pending_review``. Review happens in the
  pull request; the merge bot sets ``reviewed_by`` and flips to ``verified``.
"""
__all__ = ["__version__"]
__version__ = "0.1.0"
