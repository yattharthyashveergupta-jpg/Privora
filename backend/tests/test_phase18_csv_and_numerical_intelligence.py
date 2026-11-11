from __future__ import annotations

import io
import openpyxl
import pytest
from fastapi.testclient import TestClient


def create_synthetic_xlsx_data() -> bytes:
    """Create a workbook with known values for exact calculation verification."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Revenue"
    ws.append(["Region", "Units Sold", "Unit Price", "Gross Revenue"])
    ws.append(["North", 100, 25.5, 2550.0])
    ws.append(["South", 200, 30.0, 6000.0])
    ws.append(["East", 150, 20.0, 3000.0])
    ws.append(["West", 50, 40.0, 2000.0])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def create_synthetic_csv_comma() -> bytes:
    csv_text = (
        "Employee,Base Salary,Bonus,Performance Score\n"
        "Alice,95000,12000,4.8\n"
        "Bob,82000,8500,4.2\n"
        "Charlie,110000,15000,4.9\n"
        "Dana,78000,6000,3.9\n"
    )
    return csv_text.encode("utf-8")


def create_synthetic_csv_semicolon() -> bytes:
    csv_text = (
        "Server;Cores;RAM_GB;Storage_TB\n"
        "App-Node-01;16;64;2.5\n"
        "App-Node-02;32;128;5.0\n"
        "DB-Node-01;64;256;10.0\n"
    )
    return csv_text.encode("utf-8")


def test_csv_upload_and_coordinate_chunking(client: TestClient):
    """Verify CSV ingestion extracts rows with repeated headers and assigns coordinate citations."""
    csv_bytes = create_synthetic_csv_comma()
    upload_res = client.post(
        "/api/documents",
        files={"file": ("salaries.csv", csv_bytes, "text/csv")},
    )
    assert upload_res.status_code == 201
    data = upload_res.json()
    doc_id = data["id"]
    assert data["filename"] == "salaries.csv"
    assert data["status"] == "indexed"

    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    assert len(passages) >= 1

    # Verify sections mention CSV rows
    sections = [p["section"] for p in passages if p.get("section")]
    assert any("CSV: Rows" in s for s in sections)

    # Verify deterministic summary passage or row text
    all_text = " ".join(p["text"] for p in passages)
    assert "Alice" in all_text
    assert "95000" in all_text or "95,000" in all_text
    assert "Employee" in all_text


def test_csv_semicolon_delimiter_sniffing(client: TestClient):
    """Verify CSV parser correctly identifies semicolon delimiter and chunks records."""
    csv_bytes = create_synthetic_csv_semicolon()
    upload_res = client.post(
        "/api/documents",
        files={"file": ("infrastructure.csv", csv_bytes, "text/csv")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    all_text = " ".join(p["text"] for p in passages)
    assert "App-Node-01" in all_text
    assert "DB-Node-01" in all_text


def test_tabular_analytics_xlsx_deterministic_calculations(client: TestClient):
    """Verify GET /api/documents/{id}/analytics computes exact sums, means, and min/max with cell coordinates."""
    xlsx_bytes = create_synthetic_xlsx_data()
    upload_res = client.post(
        "/api/documents",
        files={"file": ("revenue_report.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    analytics_res = client.get(f"/api/documents/{doc_id}/analytics")
    assert analytics_res.status_code == 200
    data = analytics_res.json()

    assert data["format"] == "xlsx"
    assert data["total_sheets"] == 1
    sheet = data["sheets"][0]
    assert sheet["sheet_name"] == "Revenue"
    assert sheet["total_rows"] == 4
    assert sheet["total_columns"] == 4

    # Check numeric columns
    num_cols = {col["column"]: col for col in sheet["numeric_columns"]}
    assert "Units Sold" in num_cols
    assert "Gross Revenue" in num_cols

    units = num_cols["Units Sold"]
    assert units["count"] == 4
    # Exact sum: 100 + 200 + 150 + 50 = 500
    assert units["total"] == 500.0
    # Mean: 500 / 4 = 125
    assert units["mean"] == 125.0
    assert units["min"] == 50.0
    assert units["max"] == 200.0
    assert units["cell_range"] == "B2:B5"

    rev = num_cols["Gross Revenue"]
    # Exact sum: 2550 + 6000 + 3000 + 2000 = 13550
    assert rev["total"] == 13550.0
    assert rev["cell_range"] == "D2:D5"


def test_tabular_analytics_csv_deterministic_calculations(client: TestClient):
    """Verify GET /api/documents/{id}/analytics computes exact metrics for CSV uploads."""
    csv_bytes = create_synthetic_csv_comma()
    upload_res = client.post(
        "/api/documents",
        files={"file": ("payroll.csv", csv_bytes, "text/csv")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    analytics_res = client.get(f"/api/documents/{doc_id}/analytics")
    assert analytics_res.status_code == 200
    data = analytics_res.json()

    assert data["format"] == "csv"
    assert data["total_sheets"] == 1
    sheet = data["sheets"][0]
    num_cols = {col["column"]: col for col in sheet["numeric_columns"]}

    assert "Base Salary" in num_cols
    sal = num_cols["Base Salary"]
    assert sal["count"] == 4
    # 95000 + 82000 + 110000 + 78000 = 365000
    assert sal["total"] == 365000.0
    assert sal["mean"] == 91250.0
    assert sal["min"] == 78000.0
    assert sal["max"] == 110000.0
    assert "Rows 2-5" in sal["cell_range"]


def test_tabular_analytics_non_tabular_file_rejected(client: TestClient):
    """Verify requesting tabular analytics on a plain text or PDF document returns 400."""
    txt_bytes = b"This is a legal memorandum regarding contract compliance. Section 1 is binding."
    upload_res = client.post(
        "/api/documents",
        files={"file": ("memo.txt", txt_bytes, "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    analytics_res = client.get(f"/api/documents/{doc_id}/analytics")
    assert analytics_res.status_code == 400
    assert "spreadsheet" in analytics_res.json()["detail"].lower()


def test_admin_rbac_document_deletion_and_isolation(client: TestClient, monkeypatch):
    """Verify organization admin can manage documents and non-admins are role-restricted."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")

    # 1. Register admin user
    reg_admin = client.post("/api/auth/register", json={
        "email": "orgadmin@enterprisecorp.com",
        "password": "Password123!",
        "full_name": "Org Administrator",
        "organization_name": "Enterprise Corp",
    }).json()
    admin_token = reg_admin["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Upload document as admin
    upload_res = client.post(
        "/api/documents",
        headers=admin_headers,
        files={"file": ("admin_policy.txt", b"Enterprise security policy 2026", "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 3. Admin deletes the document
    del_res = client.delete(f"/api/documents/{doc_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 4. Verify document is gone
    check_res = client.get(f"/api/documents/{doc_id}/passages", headers=admin_headers)
    assert check_res.status_code == 404

