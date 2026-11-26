# MSSQL Load Test Results (`CPDB.pdfstudio` on `10.106.44.20:1433`)

Executed via `.\.venv\Scripts\python.exe -m pytest tests\test_mssql_load.py -v -s` using isolated `load_<run_id>_<i>` test users and automatic record cleanup.

| Concurrent Users | Submit P50 / P95 / P99 | Exec P50 / P95 / P99 | Throughput | SQL Pool (`checked_out` after) | CPU | RSS Delta | Disk Free |
|---|---|---|---|---|---|---|---|
| 3 users | `0.035s` / `0.035s` / `0.035s` | `0.062s` / `0.063s` / `0.063s` | `46.12 jobs/s` | `10` (`0`) | `67.3%` | `-0.6 MB` | `14.3 GB` |
| 8 users | `0.049s` / `0.052s` / `0.052s` | `0.046s` / `0.060s` / `0.060s` | `55.58 jobs/s` | `10` (`0`) | `72.0%` | `-0.1 MB` | `14.3 GB` |
| 15 users | `0.080s` / `0.087s` / `0.088s` | `0.051s` / `0.055s` / `0.055s` | `58.99 jobs/s` | `10` (`0`) | `67.8%` | `-2.2 MB` | `14.3 GB` |
| 20 users | `0.080s` / `0.088s` / `0.095s` | `0.044s` / `0.050s` / `0.057s` | `63.46 jobs/s` | `10` (`0`) | `78.0%` | `+3.0 MB` | `14.3 GB` |

## Key Findings
- **Zero duplicate job claims** across 4 concurrent claiming workers using SQL Server `WITH (UPDLOCK, READPAST, ROWLOCK)`.
- **Retry & failed-job handling** verified and all temporary test records cleaned up.
