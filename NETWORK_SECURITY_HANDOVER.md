# Network / IT Security Team Handover Checklist

## Required From Network / IT Security Team
- [ ] Written approval and creation of Windows Firewall inbound rule allowing **TCP `8501`** (Streamlit Dashboard) from approved corporate subnets only.
- [ ] Confirm **TCP `8000`** (FastAPI internal backend) remains blocked externally (`127.0.0.1` loopback only).
- [ ] Confirm TLS/HTTPS reverse-proxy or certificate policy for client access to port `8501` if required by corporate standard.

## Evidence Application Owner Must Collect
- `scripts/validate_production_readiness.ps1` reporting `[PASS]` for TCP `8501` firewall rule and `[PASS]` for port `8000` non-exposure.
- Change ticket / approval reference recorded in [PRODUCTION_DEPENDENCY_TRACKER.md](PRODUCTION_DEPENDENCY_TRACKER.md).
