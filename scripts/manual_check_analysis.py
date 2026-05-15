"""End-to-end manual verification for the analysis module.

Run:  uv run python scripts/manual_check_analysis.py
Expected cost: < $0.30 USD
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis import (
    ClaudeAnalysisClient,
    ComparisonAnalysis,
    EmptyAbstractError,
    PaperAnalysis,
    PaperComparator,
    PaperExtractor,
    SchemaValidationError,
)
from src.search import SearchFilters, SemanticScholarClient

USER_TOPIC = "護理人員 COVID-19 期間的職業倦怠"
N_PAPERS = 3


def _separator(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _print_analysis(idx: int, title: str, analysis: PaperAnalysis) -> None:
    print(f"\n[{idx + 1}] {title[:70]}")

    rq = analysis.research_question
    rq_val = rq.value or "(not found)"
    print(f"  研究問題 ({rq.confidence}): {rq_val[:100]}")

    sd = analysis.study_design
    if sd.value:
        print(f"  研究設計: {sd.value.type or '?'}, n={sd.value.sample_size}, pop={sd.value.population}")
    else:
        print("  研究設計: (not found)")

    for i, finding in enumerate(analysis.key_findings[:2], 1):
        print(f"  發現 {i}: {finding.statement[:100]}")

    print(f"  引用情境:")
    for ctx in analysis.citation_contexts:
        print(f"    [{ctx.context_type}] {ctx.description[:80]}")

    # Check for not_found fields
    not_found = []
    for fname in ["research_question", "study_design"]:
        gf = getattr(analysis, fname)
        if gf.confidence == "not_found":
            not_found.append(fname)
    if not_found:
        print(f"  ⚠️  資訊不足欄位: {', '.join(not_found)}")


def _print_comparison(comparison: ComparisonAnalysis) -> None:
    print("\n共通主題:")
    for theme in comparison.common_themes:
        print(f"  • {theme}")

    print("\n研究 Gap:")
    for gap in comparison.research_gaps:
        print(f"  • {gap}")

    print(f"\n文獻整合建議:")
    print(f"  {comparison.suggested_synthesis[:200]}")

    if comparison.cross_relations:
        print(f"\n文獻關聯 ({len(comparison.cross_relations)} 條):")
        for rel in comparison.cross_relations:
            print(f"  [{rel.relation_type}] idx{rel.target_paper_index}: {rel.description[:80]}")


def main() -> None:
    t_start = time.monotonic()

    print(f"\n研究主題: {USER_TOPIC!r}")
    print(f"目標文獻數: {N_PAPERS}")

    # ── Step 1: Fetch papers ─────────────────────────────────────────────────
    _separator("Step 1: 從 Semantic Scholar 抓取文獻")
    s2 = SemanticScholarClient()
    print(f"Mode: {s2.auth_mode}")

    try:
        papers = s2.search(USER_TOPIC, limit=N_PAPERS, strategy="relevance")
    except Exception as exc:
        print(f"S2 search error: {exc}")
        sys.exit(1)

    papers = [p for p in papers if p.abstract]
    print(f"取得 {len(papers)} 篇有 abstract 的文獻")
    if not papers:
        print("No papers with abstract found. Exiting.")
        sys.exit(1)

    for i, p in enumerate(papers):
        print(f"  [{i}] {(p.title or '')[:70]}")

    # ── Step 2: Individual analysis ──────────────────────────────────────────
    _separator("Step 2: 個別文獻分析")
    client = ClaudeAnalysisClient()
    print(f"Model: {client.model}")
    extractor = PaperExtractor(client=client)

    analyses: list[PaperAnalysis] = []
    analyzed_papers = []
    total_input = 0
    total_output = 0
    total_cost = 0.0
    api_calls = 0

    for i, paper in enumerate(papers):
        print(f"\n  分析 [{i}]: {(paper.title or '')[:60]} ...")
        try:
            analysis, usage = extractor.analyze(paper, USER_TOPIC)
            analyses.append(analysis)
            analyzed_papers.append(paper)
            total_input += usage["input_tokens"]
            total_output += usage["output_tokens"]
            total_cost += usage["estimated_cost_usd"]
            api_calls += 1
            _print_analysis(i, paper.title or "", analysis)
        except EmptyAbstractError as e:
            print(f"  [SKIP] abstract 不足: {e}")
        except SchemaValidationError as e:
            print(f"  [SCHEMA ERR] {e}")
        except Exception as e:
            print(f"  [ERR] {type(e).__name__}: {e}")

    if len(analyses) < 2:
        print("\n不足 2 篇成功分析，跳過跨文獻比較。")
    else:
        # ── Step 3: Cross-paper comparison ───────────────────────────────────
        _separator("Step 3: 跨文獻關聯性分析")
        comparator = PaperComparator(client=client)
        try:
            comparison, usage = comparator.compare(analyzed_papers, analyses, USER_TOPIC)
            total_input += usage["input_tokens"]
            total_output += usage["output_tokens"]
            total_cost += usage["estimated_cost_usd"]
            api_calls += 1
            _print_comparison(comparison)
        except SchemaValidationError as e:
            print(f"[SCHEMA ERR] 跨文獻分析失敗: {e}")
        except Exception as e:
            print(f"[ERR] 跨文獻分析: {type(e).__name__}: {e}")

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.monotonic() - t_start
    _separator("Summary")
    print(f"  成功分析文獻: {len(analyses)}/{len(papers)}")
    print(f"  API 呼叫次數: {api_calls}")
    print(f"  總 input tokens:  {total_input:,}")
    print(f"  總 output tokens: {total_output:,}")
    print(f"  估算總成本:       ${total_cost:.4f} USD")
    print(f"  總耗時:           {elapsed:.1f}s")

    if total_cost > 0.30:
        print(f"\n  [!] 成本超過 $0.30 上限 (${total_cost:.4f})")
    else:
        print(f"\n  [OK] 成本在 $0.30 預算內")


if __name__ == "__main__":
    main()
