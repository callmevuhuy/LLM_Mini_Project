"""Unified intent router for order flow, knowledge RAG, mixed queries, and handoff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .rag import normalize_text

# shortcut: Regex heuristic routing suffices for demo intents; upgrade to fine-tuned classifier or two-pass LLM function calling if user intents grow beyond commerce queries.


KNOWLEDGE_PATTERNS = [
    r"\bbao hanh\b", r"\bdoi tra\b", r"\bhoan tien\b", r"\bdieu kien\b", r"\bquy dinh\b", r"\bchinh sach\b",
    r"\bchat lieu\b", r"\bchat vai\b", r"\bvai\s+gi\b", r"\bhuong dan\b", r"\bve sinh\b", r"\bkhu mui\b",
    r"\bpha ca phe\b", r"\bpha phin\b", r"\bngap\b", r"\bnuoc\b", r"\bchong nuoc\b", r"\bdong kiem\b",
    r"\bmac thu\b", r"\bthu do\b", r"\bbang size\b", r"\bchon size\b", r"\btu van size\b",
    r"\bbao thieu\b", r"\bthieu hang\b", r"\bmay ngay\b", r"\bbao lau\b", r"\bxuat xu\b",
    r"\bgiu nong\b", r"\bgiu lanh\b", r"\bmay tieng\b", r"\bstaff\b", r"\bchiet khau\b", r"\bma giam gia\b", r"\bnoi bo\b",
    r"\bsop\b", r"\bwms\b", r"\bcamera kho\b", r"\blay lai tien\b", r"\btra lai\b", r"\bdoi hang\b",
    r"\bsua mien phi\b", r"\bsneaker\b", r"\bgiay\b", r"\bgiao gap\b", r"\bmay gio\b", r"\bhen gio\b"
]

ORDER_ACTION_PATTERNS = [
    r"\bchot\s+\d", r"\bchot\b", r"\bdat mua\b", r"\bdat hang\b", r"\bmua\s+\d", r"\blay\s+\d",
    r"\bthem vao don\b", r"\bthem vao gio\b", r"\bsua don\b", r"\bdoi don\b", r"\bcap nhat don\b",
    r"\bdat\s+\d", r"\btoi muon dat\b", r"\bminh muon dat\b", r"\bmuon dat\b"
]

ORDER_READ_PATTERNS = [
    r"\bgia\s+bao\s+nhieu\b", r"\bgia\s+the\s+nao\b", r"\bgia\s+sao\b",
    r"(?<!giam\s)\bgia\b", r"\bcon hang\b", r"\bton kho\b", r"\bco hang\b",
    r"\bcon size\b", r"\bhet hang\b"
]

HANDOFF_PATTERNS = [
    r"\bnhan vien\b", r"\bgap nguoi\b", r"\bho tro truc tiep\b", r"\bkhieu nai\b", r"\btong dai\b"
]

SAFETY_PATTERNS = [
    r"\bbo qua moi chinh sach\b", r"\bbo qua chinh sach\b", r"\bbo qua huong dan\b",
    r"\btiet lo api key\b", r"\btiet lo secret\b", r"\bxoa moi don hang\b", r"\bhack\b", r"\bbypass\b"
]


@dataclass
class RouteDecision:
    primary_route: str  # "order_action" | "knowledge_query" | "mixed" | "handoff" | "safety_adversarial"
    knowledge_query: str | None = None
    order_query: str | None = None
    intent: str | None = None
    requires_clarification: bool = False


def route_message(text: str) -> RouteDecision:
    """Analyze query and classify into order, knowledge, mixed, or safety flow."""
    norm = normalize_text(text)

    # 1. Safety check
    if any(re.search(p, norm) for p in SAFETY_PATTERNS):
        has_order = any(re.search(p, norm) for p in ORDER_ACTION_PATTERNS)
        if has_order:
            return RouteDecision(primary_route="safety_adversarial", order_query=text, intent="create_order")
        return RouteDecision(primary_route="safety_adversarial", intent="unknown_or_handoff")

    # 2. Handoff check (only if not asking a policy question like internal staff discount)
    is_internal_query = any(k in norm for k in ["chiet khau", "ma giam gia", "noi bo", "luong", "sop", "camera kho"])
    if any(re.search(p, norm) for p in HANDOFF_PATTERNS) and not is_internal_query:
        return RouteDecision(primary_route="handoff", intent="unknown_or_handoff")

    has_knowledge = any(re.search(p, norm) for p in KNOWLEDGE_PATTERNS)
    has_order_action = any(re.search(p, norm) for p in ORDER_ACTION_PATTERNS)
    has_order_read = any(re.search(p, norm) for p in ORDER_READ_PATTERNS)

    # 3. Mixed query: both knowledge asking and order action/read
    if has_knowledge and (has_order_action or has_order_read):
        parts = re.split(r"[,;]|\bva\b|\bnhung\b|\brồi\b|\broi\b", text, flags=re.I)
        k_parts = []
        o_parts = []
        for part in parts:
            p_norm = normalize_text(part)
            if any(re.search(p, p_norm) for p in KNOWLEDGE_PATTERNS):
                k_parts.append(part.strip())
            if any(re.search(p, p_norm) for p in ORDER_ACTION_PATTERNS) or any(re.search(p, p_norm) for p in ORDER_READ_PATTERNS):
                o_parts.append(part.strip())

        k_query = " ".join(k_parts) if k_parts else text
        o_query = " ".join(o_parts) if o_parts else text
        return RouteDecision(
            primary_route="mixed",
            knowledge_query=k_query,
            order_query=o_query,
            intent="create_order" if has_order_action else "check_stock"
        )

    # 4. Pure Knowledge query
    if has_knowledge:
        return RouteDecision(
            primary_route="knowledge_query",
            knowledge_query=text,
            intent="knowledge_query"
        )

    # 5. Pure Order action or Operational read
    if has_order_action:
        return RouteDecision(
            primary_route="order_action",
            order_query=text,
            intent="create_order"
        )

    if has_order_read:
        intent = "check_price" if "gia" in norm else "check_stock"
        return RouteDecision(
            primary_route="order_action",
            order_query=text,
            intent=intent
        )

    # 6. Ambiguous / Handoff
    return RouteDecision(
        primary_route="handoff",
        intent="unknown_or_handoff",
        requires_clarification=True
    )
