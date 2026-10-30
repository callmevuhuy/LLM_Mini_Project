"""Script to build, validate, and activate the RAG index bundle.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from src.rag import build_index_bundle, DEFAULT_CORPUS_DIR, DEFAULT_MANIFEST_PATH, DEFAULT_BUNDLE_PATH


def run_indexing(corpus_dir=DEFAULT_CORPUS_DIR, manifest_path=DEFAULT_MANIFEST_PATH, output_bundle=DEFAULT_BUNDLE_PATH, version="1.0"):
    print(f"Building RAG index bundle from {corpus_dir} (v{version})...")
    index = build_index_bundle(corpus_dir=corpus_dir, manifest_path=manifest_path, version=version)
    index.save(output_bundle)

    # Also write artifacts/index_manifest.json
    manifest_out = Path(__file__).resolve().parents[1] / "artifacts" / "index_manifest.json"
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "active_version": version,
        "bundle_file": Path(output_bundle).name,
        "manifest": index.manifest_meta,
        "sample_chunk_ids": [c.chunk_id for c in index.chunks[:5]],
        "total_chunks": len(index.chunks),
    }
    manifest_out.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Index successfully built! Total documents: {index.manifest_meta['total_documents']}, Total chunks: {len(index.chunks)}")
    print(f"Saved bundle to: {output_bundle}")
    print(f"Saved active manifest to: {manifest_out}")
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--output", default=str(DEFAULT_BUNDLE_PATH))
    args = parser.parse_args()
    run_indexing(corpus_dir=args.corpus, manifest_path=args.manifest, output_bundle=args.output, version=args.version)
