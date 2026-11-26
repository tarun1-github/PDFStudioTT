# Windows Infrastructure Team Handover Checklist

## Required From Windows Infrastructure Team
- [ ] Import SQL Server Root CA `.cer` into `Cert:\LocalMachine\Root` on `10.106.44.24`.
- [ ] Install **NSSM** and create least-privilege service account `SVC_PDFStudio`.
- [ ] Set NTFS ACLs: `SVC_PDFStudio` Modify on `E:\Projects\PDFStudio\data\`, Read/Execute on `E:\Projects\PDFStudio\app\`, and restrict `.env` to `Administrators` + `SVC_PDFStudio`.
- [ ] Register `PDFStudio-API`, `PDFStudio-Worker`, and `PDFStudio-Dashboard` with automatic restart and log rotation (`E:\Projects\PDFStudio\data\logs\`).

## Evidence Application Owner Must Collect
- `Get-Service PDFStudio*` showing all 3 services `Running`.
- `scripts/validate_production_readiness.ps1` reporting `[PASS]` for CA cert and NSSM services.
- Updated [WINDOWS_SERVICE_VALIDATION.md](WINDOWS_SERVICE_VALIDATION.md).
