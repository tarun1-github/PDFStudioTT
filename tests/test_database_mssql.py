"""Live MSSQL connectivity, schema, and table tests (never mocked)."""
import uuid
import pytest
from sqlalchemy import inspect, text

from backend.database.connection import check_database_health, get_engine
from backend.database.models import PdfJob, Role, User
from backend.database.session import get_session_factory


def test_mssql_live_connectivity_and_schema():
    health = check_database_health()
    assert health["connected"] is True, f"MSSQL connection failed: {health.get('error')}"
    assert health["database"] == "CPDB"
    assert health["schema_exists"] is True, "Schema 'pdfstudio' does not exist in CPDB."


def test_mssql_required_tables_exist():
    engine = get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names(schema="pdfstudio"))
    expected = {
        "users",
        "roles",
        "user_roles",
        "pdf_jobs",
        "uploaded_files",
        "generated_documents",
        "shared_documents",
        "audit_logs",
        "application_settings",
    }
    missing = expected - tables
    assert not missing, f"Missing tables in pdfstudio schema: {sorted(missing)}"


def test_mssql_insert_read_and_job_update():
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        for role_name in ("Engineer", "Team Lead", "Admin"):
            role = db.query(Role).filter(Role.name == role_name).first()
            assert role is not None, f"Expected seeded role '{role_name}' missing."

        active_user = db.query(User).filter(User.is_active == True).first()  # noqa: E712
        created_temp_user = None
        if active_user is None:
            probe = uuid.uuid4().hex[:8]
            created_temp_user = User(
                username=f"probe_{probe}",
                display_name="Isolated Probe User",
                email=f"probe_{probe}@pdfstudio.local",
                storage_folder=f"probe_{probe}",
                auth_provider="test_probe",
                is_active=True,
            )
            db.add(created_temp_user)
            db.commit()
            db.refresh(created_temp_user)
            owner = created_temp_user
        else:
            owner = active_user

        job_uuid = uuid.uuid4().hex
        job = PdfJob(
            job_uuid=job_uuid,
            user_id=owner.id,
            job_type="unit_probe",
            status="QUEUED",
            progress_pct=0,
            payload_json="{}",
        )
        db.add(job)
        db.commit()

        try:
            fetched = db.query(PdfJob).filter(PdfJob.job_uuid == job_uuid).first()
            assert fetched is not None
            fetched.status = "COMPLETED"
            fetched.progress_pct = 100
            db.commit()
        finally:
            cleanup_job = db.query(PdfJob).filter(PdfJob.job_uuid == job_uuid).first()
            if cleanup_job is not None:
                db.delete(cleanup_job)
            if created_temp_user is not None:
                db.delete(created_temp_user)
            db.commit()
