"""Evaluation script for RAG retrieval, permissions, grounded citations, and routing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag import RAGIndex, generate_grounded_answer, normalize_text, DEFAULT_BUNDLE_PATH
from src.router import route_message


def run_evaluation(bundle_path=DEFAULT_BUNDLE_PATH, cases_path=ROOT / "artifacts" / "evaluation_cases.jsonl", split=None):
    cases = [json.loads(line) for line in Path(cases_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if split:
        cases = [c for c in cases if c.get("split") == split]

    index = RAGIndex.load(bundle_path)
    all_chunk_ids = {c.chunk_id for c in index.chunks}

    retrieval_hits_at_3 = 0
    retrieval_recalls_at_5: list[float] = []
    reciprocal_ranks: list[float] = []
    retrieval_eligible_count = 0

    safe_abstention_correct = 0
    safe_abstention_total = 0

    access_denied_correct = 0
    access_denied_total = 0

    mixed_correct = 0
    mixed_total = 0

    citation_resolved_count = 0
    citation_total_count = 0

    claim_supported_count = 0
    total_evaluated_cases = len(cases)

    case_results = []

    for case in cases:
        cid = case["id"]
        query = case["query"]
        role = case["role"]
        expected_chunks = set(case.get("expected_chunk_ids", []))
        expected_status = case.get("expected_status")
        expected_route = case.get("expected_route")

        # 1. Routing
        decision = route_message(query)
        actual_route = decision.primary_route

        # 2. Retrieval & Generation
        k_query = decision.knowledge_query or query
        retrieved = index.retrieve(k_query, user_role=role, top_k=5)
        retrieved_chunk_ids = [c.chunk_id for c, _ in retrieved]

        # Calculate retrieval metrics if query has expected chunks
        if expected_chunks:
            retrieval_eligible_count += 1
            # Hit@3
            top3 = set(retrieved_chunk_ids[:3])
            hit = 1 if (expected_chunks & top3) else 0
            retrieval_hits_at_3 += hit

            # Recall@5
            top5 = set(retrieved_chunk_ids[:5])
            recall = len(expected_chunks & top5) / len(expected_chunks)
            retrieval_recalls_at_5.append(recall)

            # MRR
            rr = 0.0
            for rank, r_id in enumerate(retrieved_chunk_ids, 1):
                if r_id in expected_chunks:
                    rr = 1.0 / rank
                    break
            reciprocal_ranks.append(rr)

        answer_obj = generate_grounded_answer(k_query, retrieved, user_role=role)
        actual_status = answer_obj["status"]

        # 3. Citation resolution check
        for cit in answer_obj.get("citations", []):
            citation_total_count += 1
            if cit.get("chunk_id") in all_chunk_ids:
                citation_resolved_count += 1

        # 4. Check category specific goals
        category = case["category"]
        if category == "no_evidence":
            safe_abstention_total += 1
            if actual_status == "insufficient_evidence":
                safe_abstention_correct += 1

        if category == "access_denied":
            access_denied_total += 1
            if actual_status == "access_denied":
                access_denied_correct += 1

        if category == "mixed":
            mixed_total += 1
            if actual_route == "mixed" and answer_obj.get("citations"):
                mixed_correct += 1

        # 5. Claim support check (basic check if key facts in answer)
        facts = case.get("expected_facts", [])
        ans_text = answer_obj.get("answer", "")
        ans_norm = normalize_text(ans_text)
        if facts and all(normalize_text(fact) in ans_norm for fact in facts):
            claim_supported_count += 1
        elif not facts:
            claim_supported_count += 1

        case_results.append({
            "id": cid,
            "category": category,
            "route_match": (actual_route == expected_route),
            "status_match": (actual_status == expected_status),
            "actual_route": actual_route,
            "actual_status": actual_status,
            "citations": [c["chunk_id"] for c in answer_obj.get("citations", [])],
            "answer_preview": ans_text[:120] + "..." if len(ans_text) > 120 else ans_text
        })

    # Summary metrics
    hit_at_3_rate = (retrieval_hits_at_3 / retrieval_eligible_count) if retrieval_eligible_count else 1.0
    mean_recall_at_5 = (sum(retrieval_recalls_at_5) / len(retrieval_recalls_at_5)) if retrieval_recalls_at_5 else 1.0
    mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 1.0
    citation_resolve_rate = (citation_resolved_count / citation_total_count) if citation_total_count else 1.0
    abstention_rate = (safe_abstention_correct / safe_abstention_total) if safe_abstention_total else 1.0
    access_denied_rate = (access_denied_correct / access_denied_total) if access_denied_total else 1.0
    mixed_accuracy = (mixed_correct / mixed_total) if mixed_total else 1.0
    claim_support_rate = claim_supported_count / total_evaluated_cases

    report = {
        "split": split or "all",
        "total_cases": total_evaluated_cases,
        "retrieval_cases_count": retrieval_eligible_count,
        "metrics": {
            "Hit@3": round(hit_at_3_rate * 100, 2),
            "Recall@5": round(mean_recall_at_5 * 100, 2),
            "MRR": round(mrr, 4),
            "Citation_Resolve_Rate": round(citation_resolve_rate * 100, 2),
            "Claim_Support_Rate": round(claim_support_rate * 100, 2),
            "Safe_Abstention_Rate": round(abstention_rate * 100, 2),
            "Access_Denied_Rate": round(access_denied_rate * 100, 2),
            "Mixed_Route_Accuracy": round(mixed_accuracy * 100, 2),
        },
        "case_results": case_results,
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test", "all"], default="all")
    args = parser.parse_args()

    split_arg = None if args.split == "all" else args.split
    result = run_evaluation(split=split_arg)
    print(f"\n=================== RAG EVALUATION REPORT ({args.split.upper()}) ===================")
    print(f"Total Cases: {result['total_cases']}")
    for k, v in result["metrics"].items():
        print(f" - {k}: {v}{'%' if 'Rate' in k or 'Accuracy' in k or 'Hit' in k or 'Recall' in k else ''}")
    print("==================================================================\n")
