"""Privora — Cross-Document Contradiction & Comparison Analysis Engine
Identifies factual conflicts, numerical discrepancies, and differing terms across distinct indexed documents.
Provides dual-source citations with exact page numbers, section titles, and spreadsheet cell coordinates.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any
import httpx

from app.config import get_ollama_base_url


CONTRADICTION_PATTERNS = [
    # (topic, regex_for_extracting_term, label)
    ("Payment Terms", r"(?:net\s*(\d{1,3})|within\s*(\d{1,3})\s*(?:business\s*|calendar\s*)?days|due\s+on\s+receipt)", "Payment Terms"),
    ("Retention Period", r"retain(?:ed)?\s+for\s+(?:exactly\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+years?", "Retention Schedule"),
    ("Liability Cap", r"liability\s+(?:shall\s+not\s+exceed|capped\s+at|limited\s+to)\s+\$?([0-9,]+(?:\.[0-9]{2})?)", "Liability Limitation"),
    ("SLA Commitment", r"(?:uptime|availability|sla)\s*(?:of|at|guarantee)?\s*([0-9]{2}(?:\.[0-9]{1,3})?)\s*%", "Service Level Agreement"),
    ("Notice Period", r"(\d{1,3})\s+days?\s*(?:prior\s*)?(?:written\s*)?notice", "Termination / Notice Period"),
    ("Interest Rate", r"interest\s*(?:rate|fee)?\s*(?:of)?\s*([0-9]+(?:\.[0-9]+)?)\s*%", "Interest / Late Fee Rate"),
]


def extract_key_metrics(text: str) -> dict[str, str]:
    """Deterministically extracts key terms and metrics from text for heuristic comparison."""
    findings = {}
    lower = text.lower()
    for topic, pattern, label in CONTRADICTION_PATTERNS:
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            findings[topic] = match.group(0).strip()
    return findings


def detect_cross_document_contradictions(
    conn: sqlite3.Connection,
    organization_id: str,
    workspace_id: str,
    topic: str | None = None,
    target_doc_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Scans indexed documents in the workspace for conflicting assertions and numerical discrepancies."""
    # 1. Fetch documents
    query = (
        "SELECT id, filename, content_type FROM documents "
        "WHERE organization_id = ? AND workspace_id = ?"
    )
    params: list[Any] = [organization_id, workspace_id]
    if target_doc_ids:
        placeholders = ",".join("?" for _ in target_doc_ids)
        query += f" AND id IN ({placeholders})"
        params.extend(target_doc_ids)
    query += " ORDER BY created_at ASC"

    docs = conn.execute(query, params).fetchall()
    if len(docs) < 2:
        return {
            "status": "insufficient_documents",
            "message": "Cross-document analysis requires at least two distinct indexed documents in the workspace.",
            "documents_analyzed": [d["filename"] for d in docs],
            "findings_count": 0,
            "findings": [],
        }

    # 2. Fetch all passages with section/page coordinates
    passages_query = (
        "SELECT p.id, p.document_id, p.page, p.section, p.text, d.filename "
        "FROM passages p JOIN documents d ON d.id = p.document_id "
        "WHERE d.organization_id = ? AND d.workspace_id = ?"
    )
    p_params: list[Any] = [organization_id, workspace_id]
    if target_doc_ids:
        placeholders = ",".join("?" for _ in target_doc_ids)
        passages_query += f" AND d.id IN ({placeholders})"
        p_params.extend(target_doc_ids)

    passages = conn.execute(passages_query, p_params).fetchall()

    # 3. Deterministic heuristic extraction per document
    doc_metrics: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for p in passages:
        doc_id = p["document_id"]
        if doc_id not in doc_metrics:
            doc_metrics[doc_id] = {}
        metrics = extract_key_metrics(p["text"])
        for m_topic, m_val in metrics.items():
            if topic and topic.lower() not in m_topic.lower():
                continue
            if m_topic not in doc_metrics[doc_id]:
                doc_metrics[doc_id][m_topic] = []
            doc_metrics[doc_id][m_topic].append({
                "value": m_val,
                "passage_id": p["id"],
                "filename": p["filename"],
                "page": p["page"],
                "section": p["section"],
                "excerpt": p["text"][:300].strip(),
            })

    findings: list[dict[str, Any]] = []
    seen_pairs: set[str] = set()

    doc_ids_list = list(doc_metrics.keys())
    for i in range(len(doc_ids_list)):
        for j in range(i + 1, len(doc_ids_list)):
            id_a = doc_ids_list[i]
            id_b = doc_ids_list[j]
            metrics_a = doc_metrics[id_a]
            metrics_b = doc_metrics[id_b]

            # Find shared topics with differing extracted values
            common_topics = set(metrics_a.keys()) & set(metrics_b.keys())
            for t in common_topics:
                instances_a = metrics_a[t]
                instances_b = metrics_b[t]
                for inst_a in instances_a:
                    for inst_b in instances_b:
                        val_a = inst_a["value"].lower()
                        val_b = inst_b["value"].lower()
                        if val_a != val_b:
                            pair_key = f"{t}_{inst_a['filename']}_{inst_b['filename']}_{val_a}_{val_b}"
                            if pair_key in seen_pairs:
                                continue
                            seen_pairs.add(pair_key)

                            severity = "high" if t in ("Payment Terms", "Liability Cap", "Retention Period") else "medium"
                            findings.append({
                                "id": f"disc_{len(findings)+1}",
                                "type": "discrepancy",
                                "severity": severity,
                                "classification": "potential_discrepancy",
                                "topic": t,
                                "title": f"Conflicting {t} between {inst_a['filename']} and {inst_b['filename']}",
                                "description": (
                                    f"{inst_a['filename']} specifies '{inst_a['value']}', whereas "
                                    f"{inst_b['filename']} records '{inst_b['value']}'."
                                ),
                                "source_a": {
                                    "document_id": id_a,
                                    "filename": inst_a["filename"],
                                    "location": (
                                        f"Page {inst_a['page']}" if inst_a["page"]
                                        else inst_a["section"] or "Document Section"
                                    ),
                                    "excerpt": inst_a["excerpt"],
                                    "claimed_value": inst_a["value"],
                                },
                                "source_b": {
                                    "document_id": id_b,
                                    "filename": inst_b["filename"],
                                    "location": (
                                        f"Page {inst_b['page']}" if inst_b["page"]
                                        else inst_b["section"] or "Document Section"
                                    ),
                                    "excerpt": inst_b["excerpt"],
                                    "claimed_value": inst_b["value"],
                                },
                                "status": "unresolved_discrepancy",
                            })

    return {
        "status": "completed",
        "documents_analyzed": [d["filename"] for d in docs],
        "findings_count": len(findings),
        "findings": findings,
    }


def compare_two_documents(
    conn: sqlite3.Connection,
    doc_id_a: str,
    doc_id_b: str,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Performs a direct clause and topic alignment comparison between two distinct documents."""
    if organization_id:
        doc_a = conn.execute("SELECT * FROM documents WHERE id = ? AND organization_id = ?", (doc_id_a, organization_id)).fetchone()
        doc_b = conn.execute("SELECT * FROM documents WHERE id = ? AND organization_id = ?", (doc_id_b, organization_id)).fetchone()
    else:
        doc_a = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id_a,)).fetchone()
        doc_b = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id_b,)).fetchone()

    if not doc_a or not doc_b:
        raise ValueError("One or both specified documents do not exist or access is unauthorized.")

    passages_a = conn.execute(
        "SELECT id, page, section, text FROM passages WHERE document_id = ? ORDER BY id ASC",
        (doc_id_a,),
    ).fetchall()
    passages_b = conn.execute(
        "SELECT id, page, section, text FROM passages WHERE document_id = ? ORDER BY id ASC",
        (doc_id_b,),
    ).fetchall()

    metrics_a = {}
    for p in passages_a:
        for t, val in extract_key_metrics(p["text"]).items():
            if t not in metrics_a:
                metrics_a[t] = {
                    "value": val,
                    "location": f"Page {p['page']}" if p["page"] else p["section"] or "Document Body",
                    "excerpt": p["text"][:250].strip(),
                }

    metrics_b = {}
    for p in passages_b:
        for t, val in extract_key_metrics(p["text"]).items():
            if t not in metrics_b:
                metrics_b[t] = {
                    "value": val,
                    "location": f"Page {p['page']}" if p["page"] else p["section"] or "Document Body",
                    "excerpt": p["text"][:250].strip(),
                }

    aligned_topics = []
    all_topics = set(metrics_a.keys()) | set(metrics_b.keys())
    for t in sorted(all_topics):
        in_a = metrics_a.get(t)
        in_b = metrics_b.get(t)
        if in_a and in_b:
            is_match = in_a["value"].lower() == in_b["value"].lower()
            aligned_topics.append({
                "topic": t,
                "status": "aligned" if is_match else "conflicting",
                "doc_a": in_a,
                "doc_b": in_b,
            })
        elif in_a:
            aligned_topics.append({
                "topic": t,
                "status": "only_in_document_a",
                "doc_a": in_a,
                "doc_b": None,
            })
        else:
            aligned_topics.append({
                "topic": t,
                "status": "only_in_document_b",
                "doc_a": None,
                "doc_b": in_b,
            })

    return {
        "status": "completed",
        "document_a": {"id": doc_id_a, "filename": doc_a["filename"], "passages": len(passages_a)},
        "document_b": {"id": doc_id_b, "filename": doc_b["filename"], "passages": len(passages_b)},
        "aligned_topics": aligned_topics,
        "conflict_count": sum(1 for item in aligned_topics if item["status"] == "conflicting"),
    }
