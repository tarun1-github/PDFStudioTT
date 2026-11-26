# Document Governance, Version Control & Knowledge Library

## Version Control
- Every governed document has a stable `doc_key` UUID and immutable `DocumentVersion` revisions (`1.0`, `1.1`, `2.0`).
- SHA-256 checksums detect identical uploads (`409 Conflict` unless explicitly overridden).
- Older versions remain downloadable and can be restored as a new `DRAFT` revision.

## Approval Workflow
States: `DRAFT` -> `SUBMITTED` -> `UNDER_REVIEW` -> `APPROVED` -> `PUBLISHED` (or `CHANGES_REQUESTED`, `REJECTED`, `ARCHIVED`).
- Self-approval and self-publication are blocked (`403 Forbidden`).
- `Team Lead` or `Admin` role is required for review transitions.
- Published versions are immutable; new revisions start in `DRAFT` and follow approval.

## Comparison, Analytics & Archival
- `/api/governance/documents/{doc_key}/compare` diffs extracted text, page counts, image counts, and metadata without modifying source PDFs.
- `/api/governance/analytics` tracks views, downloads, pending approvals, and upcoming review dates.
- Archiving preserves files and records `archive_reason`, `archived_by_user_id`, and `archived_at`.
