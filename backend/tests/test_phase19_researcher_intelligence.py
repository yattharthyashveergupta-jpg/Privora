from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch
from docx import Document
import httpx
import pytest
from fastapi.testclient import TestClient


def create_docx(sections: list[tuple[str, str]]) -> bytes:
    doc = Document()
    for title, text in sections:
        doc.add_heading(title, level=2)
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# 1. Single-document factual questions
def test_single_document_factual_question(client: TestClient):
    """Verifies that a factual query targeting a single document retrieves relevant passages,
    cites evidence accurately, detects full support, and strips any contradictory disclaimer.
    """
    docx_bytes = create_docx([
        ("Payment Terms", "All invoices shall be paid within Net 30 days of receipt."),
        ("Liability Limitation", "Liability under this agreement is strictly capped at $250,000 USD."),
    ])
    res = client.post(
        "/api/documents",
        files={"file": ("contract_vendor.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res.status_code == 201

    mock_llm_answer = {
        "response": (
            "The payment terms in contract_vendor.docx are Net 30 days of receipt [1]. "
            "I couldn't find enough evidence in the indexed documents to answer that question."
        )
    }
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = mock_llm_answer

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
        chat_res = client.post(
            "/api/chat",
            json={"message": "What are the payment terms in contract_vendor.docx?"},
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        # Contradictory trailing disclaimer must be cleanly stripped
        assert "couldn't find enough evidence" not in data["answer"].lower()
        assert "Net 30 days" in data["answer"]
        assert "[1]" in data["answer"]

        # Support classification
        assert data["support_level"] == "fully_supported"
        assert data["insufficient_evidence"] is False
        assert len(data["citations"]) >= 1
        assert data["citations"][0]["filename"] == "contract_vendor.docx"
        assert "Payment Terms" in (data["citations"][0].get("section") or "")


# 2. Multi-document retrieval
def test_multi_document_retrieval(client: TestClient):
    """Verifies that queries spanning multiple documents retrieve balanced evidence from each document."""
    sla_bytes = create_docx([
        ("SLA Commitment", "Service uptime guarantee is 99.95% during standard business hours."),
    ])
    pricing_text = (
        b"Enterprise Pricing Schedule\n\n"
        b"Standard tier licensing costs $12,000 annually per compute cluster."
    )

    client.post(
        "/api/documents",
        files={"file": ("service_level_agreement.docx", sla_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    client.post(
        "/api/documents",
        files={"file": ("pricing_sheet.txt", pricing_text, "text/plain")},
    )

    mock_llm_answer = {
        "response": "The uptime guarantee is 99.95% [1] and the annual license cost is $12,000 [2]."
    }
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = mock_llm_answer

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
        chat_res = client.post(
            "/api/chat",
            json={"message": "What are the uptime guarantees and licensing costs across the documents?"},
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        filenames = [c["filename"] for c in data["citations"]]
        assert "service_level_agreement.docx" in filenames
        assert "pricing_sheet.txt" in filenames
        assert len(data["citations"]) >= 2
        assert data["insufficient_evidence"] is False


# 3. Cross-document comparisons
def test_cross_document_comparison(client: TestClient):
    """Verifies that comparative queries retrieve evidence from both compared documents with proper attribution."""
    alpha_bytes = create_docx([
        ("Terms", "Vendor Alpha requires payment within Net 30 days and caps liability at $500,000."),
    ])
    beta_bytes = create_docx([
        ("Terms", "Vendor Beta requires payment within Net 60 days and caps liability at $1,000,000."),
    ])

    client.post(
        "/api/documents",
        files={"file": ("vendor_alpha_contract.docx", alpha_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    client.post(
        "/api/documents",
        files={"file": ("vendor_beta_contract.docx", beta_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    mock_llm_answer = {
        "response": (
            "According to vendor_alpha_contract.docx [1], payment is Net 30 days. "
            "In contrast, vendor_beta_contract.docx [2] states payment is Net 60 days."
        )
    }
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = mock_llm_answer

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        chat_res = client.post(
            "/api/chat",
            json={"message": "Compare payment terms between vendor_alpha_contract and vendor_beta_contract."},
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        # Both documents must be in citations
        filenames = {c["filename"] for c in data["citations"]}
        assert "vendor_alpha_contract.docx" in filenames
        assert "vendor_beta_contract.docx" in filenames

        # Verify prompt had evidence from both
        sent_prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "vendor_alpha_contract.docx" in sent_prompt
        assert "vendor_beta_contract.docx" in sent_prompt
        assert data["support_level"] == "fully_supported"


# 4. Irrelevant document exclusion
def test_irrelevant_document_exclusion(client: TestClient):
    """Verifies that unrelated documents with zero or negligible relevance are completely excluded."""
    security_text = (
        b"Cybersecurity Infrastructure Protocol\n\n"
        b"Multi-factor authentication with hardware security keys is strictly enforced on all VPN endpoints."
    )
    culinary_text = (
        b"Executive Dining Menu\n\n"
        b"Tuesday chef special is pan-seared Chilean sea bass served with asparagus and roasted potatoes."
    )

    client.post(
        "/api/documents",
        files={"file": ("cybersecurity_protocol.txt", security_text, "text/plain")},
    )
    client.post(
        "/api/documents",
        files={"file": ("culinary_menu.txt", culinary_text, "text/plain")},
    )

    mock_llm_answer = {
        "response": "Hardware security keys are enforced on all VPN endpoints [1]."
    }
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = mock_llm_answer

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
        chat_res = client.post(
            "/api/chat",
            json={"message": "What authentication is enforced on VPN endpoints?"},
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        # Only the security protocol should be in citations; culinary menu must be excluded
        filenames = [c["filename"] for c in data["citations"]]
        assert "cybersecurity_protocol.txt" in filenames
        assert "culinary_menu.txt" not in filenames


# 5. Missing-information handling
def test_missing_information_partially_supported(client: TestClient):
    """Verifies that when evidence answers part of a question but lacks other details,
    the response is classified as partially supported and states what is missing without contradictory disclaimers.
    """
    nda_bytes = create_docx([
        ("Confidentiality Period", "Confidentiality obligations shall continue for a period of three (3) years."),
    ])
    client.post(
        "/api/documents",
        files={"file": ("nda_agreement.docx", nda_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    mock_llm_answer = {
        "response": (
            "The confidentiality obligations continue for three (3) years [1]. "
            "However, the document does not specify any monetary penalty for disclosure."
        )
    }
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = mock_llm_answer

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
        chat_res = client.post(
            "/api/chat",
            json={"message": "What is the confidentiality period and what is the penalty for breach?"},
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        assert data["support_level"] == "partially_supported"
        assert data["insufficient_evidence"] is False
        assert data["missing_information"] is not None
        assert "penalty" in data["missing_information"].lower()
        assert "couldn't find enough evidence" not in data["answer"].lower()


def test_missing_information_unsupported(client: TestClient):
    """Verifies that queries with no matching evidence return unsupported status and clear notification."""
    nda_bytes = create_docx([
        ("Confidentiality Period", "Confidentiality obligations shall continue for three years."),
    ])
    client.post(
        "/api/documents",
        files={"file": ("nda_agreement.docx", nda_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    chat_res = client.post(
        "/api/chat",
        json={"message": "What is the company stock ticker symbol on the New York Stock Exchange?"},
    )
    assert chat_res.status_code == 200
    data = chat_res.json()

    assert data["support_level"] == "unsupported"
    assert data["insufficient_evidence"] is True
    assert data["citations"] == []
    assert "couldn't find enough evidence" in data["answer"].lower()


# 6. Citation accuracy
def test_citation_accuracy(client: TestClient):
    """Verifies that citations point to the exact section, page, and excerpt containing the factual assertion."""
    bylaws_bytes = create_docx([
        ("Section 1: Name and Purpose", "The organization shall be known as the Global Privacy Foundation."),
        ("Section 5: Arbitration", "All member disputes shall be resolved through binding arbitration in Geneva."),
        ("Section 9: Dissolution", "Upon dissolution, remaining assets shall be donated to local non-profit enclaves."),
    ])
    client.post(
        "/api/documents",
        files={"file": ("organization_bylaws.docx", bylaws_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    mock_llm_answer = {
        "response": "Member disputes must be resolved through binding arbitration in Geneva [1]."
    }
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = mock_llm_answer

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
        chat_res = client.post(
            "/api/chat",
            json={"message": "Where are member disputes arbitrated under the bylaws?"},
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        assert len(data["citations"]) >= 1
        cit = data["citations"][0]
        assert cit["filename"] == "organization_bylaws.docx"
        assert "Section 5: Arbitration" in (cit.get("section") or "")
        assert "Geneva" in cit["excerpt"]
        assert data["support_level"] == "fully_supported"
