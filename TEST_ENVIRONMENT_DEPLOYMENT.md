# Test Environment Deployment – PDF Studio

## Selected Ports & Bindings
- **Streamlit Frontend**: `0.0.0.0:8502` -> Accessible at `http://10.106.44.24:8502`
- **FastAPI Backend**: `127.0.0.1:8010` -> Loopback-only (`http://127.0.0.1:8010`)
- **Background Worker**: `backend.worker.runner` (`MAX_CONCURRENT_JOBS=3`)
- **Unrelated Services Preserved**: Existing process `PID 14840` on port `8000` was left untouched; ports `8000` and `8001` were avoided.

## Database & Storage
- **Database**: `10.106.44.20:1433`, `CPDB`, schema `pdfstudio` (Authorized Test Mode TLS: `DB_ENCRYPT=yes`, `DB_TRUST_SERVER_CERTIFICATE=yes`).
- **Storage**: `E:\Projects\PDFStudio\data` (`users/`, `shared/`, `temp/`, `templates/`, `logs/`).

## Network & Firewall Status
- **FastAPI (`8010`)**: Loopback-only (`127.0.0.1`).
- **Streamlit (`8502`)**: Proposed IT-approved Windows Firewall rule (pending IT approval if external LAN clients are blocked):
  ```powershell
  New-NetFirewallRule -DisplayName "PDF Studio Test Dashboard (TCP 8502)" -Direction Inbound -Protocol TCP -LocalPort 8502 -Action Allow
  ```
