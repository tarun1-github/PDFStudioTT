# Pilot Test Results – PDF Studio

## 1. Full Regression Suite (`.\.venv\Scripts\python.exe -m pytest tests -v -s`)
- **Total tests**: 21
- **Passed**: 21
- **Failed**: 0
- **Skipped**: 0
- **Execution duration**: 53.84s

## 2. Multi-User Load Test Results (Isolated Test Storage & SQLite)
| Concurrent Users | Total Elapsed | Avg Upload Time | Avg PDF Gen Time | RSS Memory Delta | Failed Requests |
|---|---|---|---|---|---|
| 3 users | 0.24s | 0.109s | 0.103s | +1.4 MB | 0 |
| 8 users | 0.47s | 0.205s | 0.146s | +2.9 MB | 0 |
| 15 users | 0.98s | 0.394s | 0.198s | +1.5 MB | 0 |
| 20 users | 1.26s | 0.562s | 0.175s | +1.2 MB | 0 |

### Proposed Pilot Targets (For Approval)
- **API Upload P95**: < 2.0s (for files <= 20 MB)
- **Image-to-PDF P95**: < 3.0s
- **Office-to-PDF (LibreOffice) P95**: < 15.0s
- **Error Rate**: 0% on valid inputs

## 3. UAT & Live MSSQL Evidence
- `test_uat_roles_workflows_admin_and_monitoring`: **PASSED** (Engineer, Team Lead, Admin RBAC, all PDF workflows, audit logs, settings, `/health/operations`).
- `test_mssql_live_connectivity_and_schema`, `test_mssql_required_tables_exist`, `test_mssql_insert_read_and_job_update`: **PASSED** (3/3 live against `10.106.44.20:1433` `CPDB.pdfstudio`).
- `test_office_documents_to_pdf_via_libreoffice`: **PASSED** (`DOCX`, `XLSX`, `PPTX`, `HTML`).
