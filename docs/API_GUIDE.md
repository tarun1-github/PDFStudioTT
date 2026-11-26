# API Guide

- **Health**: `GET /health`, `GET /health/db`, `GET /health/dependencies`, `GET /health/operations`
- **Auth**: `GET /api/auth/session`, `GET /api/auth/login-url`, `POST /api/auth/logout`
- **Files & PDF Tools**: `/api/files/*`, `/api/pdf/image-to-pdf`, `/api/pdf/document-to-pdf`, `/api/pdf/analyze-sequence`, `/api/pdf/compile`, `/api/pdf/learning-book`, `/api/pdf/learning-book/preview-cover`, `/api/pdf/optimize`, `/api/pdf/manage`
- **Governance & Library**: `/api/governance/categories`, `/api/governance/documents`, `/api/governance/documents/{doc_key}/versions`, `/api/governance/documents/{doc_key}/transition`, `/api/governance/documents/{doc_key}/compare`, `/api/governance/analytics`
- **Admin**: `/api/admin/users`, `/api/admin/audit-logs`, `/api/admin/settings`
