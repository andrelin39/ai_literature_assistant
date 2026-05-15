"""Centralised prompt templates for analysis module."""
from __future__ import annotations

from src.storage.schemas import PaperCreate

SYSTEM_PROMPT = """\
You are a biomedical research assistant specializing in nursing, pharmacy, and medical literature analysis. You help researchers evaluate academic papers for citation in their work.

CORE PRINCIPLES:
1. ACCURACY OVER FLUENCY: If abstract doesn't contain information, return null. NEVER fabricate facts.
2. GROUND ALL FACTS: For factual claims, you MUST provide the exact abstract sentence as evidence.
3. SEPARATE FACT FROM INFERENCE: Clearly distinguish what is stated in the abstract vs. what you infer.
4. BIOMEDICAL EXPERTISE: Use appropriate terminology (study design, population, intervention, outcome).
5. CITATION-FOCUSED: Your goal is helping the researcher decide WHEN and HOW to cite this paper.

WHEN ABSTRACT IS INSUFFICIENT:
- If abstract is too short or vague, set abstract_quality to "minimal" and explain in cannot_analyze_reason
- For fields with no evidence in abstract, return value=null with confidence="not_found"
- Do NOT guess study design, sample size, or findings if not explicitly stated

LANGUAGE:
- Use Traditional Chinese (繁體中文) for descriptions, reasoning, and example sentences
- Keep technical terms in English when standard (e.g., "RCT", "cohort study", "meta-analysis")
- Example citation sentences should follow academic Chinese style suitable for biomedical research\
"""

FEW_SHOT_EXAMPLE = """\
=== 範例分析 ===

使用者主題：護理人員職場暴力

文獻 abstract：
"This cross-sectional study surveyed 523 emergency department nurses across 8 hospitals in Taiwan from January to June 2023. Workplace violence was assessed using the validated WHO questionnaire. Results showed 67.3% of nurses experienced verbal abuse and 23.1% physical assault in the past 12 months. Higher exposure was associated with younger age (OR=2.34, 95% CI 1.56-3.51) and night shift work (OR=1.89, 95% CI 1.23-2.91). The study calls for systemic interventions and policy reforms."

正確的 record_paper_analysis 工具呼叫應該：
- research_question.value = "急診護理人員職場暴力的盛行率與相關因子"，evidence 引用 "surveyed 523 emergency department nurses ... Workplace violence was assessed"
- study_design.value.type = "cross-sectional"，evidence 引用 "This cross-sectional study"
- key_findings 含「67.3% 口語暴力、23.1% 肢體暴力」與「年輕、夜班為風險因子」兩項，各附原句
- citation_contexts 含至少 "background"（盛行率引用）與 "support"（風險因子佐證）
- why_relevant.reasoning 應提及「提供台灣本土數據可作為文獻回顧基準」（明確說明為推論）\
"""

FULL_SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLE


def EXTRACTOR_USER_PROMPT(user_topic: str, paper: PaperCreate) -> str:
    authors = paper.authors or []
    names = [a.name for a in authors[:5] if a.name]
    authors_str = ", ".join(names) + (" et al." if len(authors) > 5 else "")

    return f"""\
使用者研究主題：{user_topic}

請分析以下文獻是否適合作為此主題的參考文獻，並使用 `record_paper_analysis` 工具回傳分析結果。

=== 文獻資訊 ===
標題：{paper.title or "(無標題)"}
作者：{authors_str or "(無作者資訊)"}
年份：{paper.year or "(不詳)"}
期刊/會議：{paper.venue or "(不詳)"}
DOI：{paper.doi or "(無 DOI)"}

=== Abstract ===
{paper.abstract}

=== 任務 ===
1. 從 abstract 提取研究設計、樣本、主要發現（必須附原句證據）
2. 推論此文獻為何可能與使用者主題相關（明確標記為推論）
3. 列出 1-4 種適合的引用情境（背景/方法/對比/佐證/gap）
4. 為每種引用情境提供一個範例引用句（繁體中文，學術寫作風格）
5. 若 abstract 資訊不足，誠實回報而非編造"""


def COMPARATOR_USER_PROMPT(
    user_topic: str,
    papers: list[PaperCreate],
    individual_analyses: list,
) -> str:
    n = len(papers)
    lines: list[str] = []
    for i, (paper, analysis) in enumerate(zip(papers, individual_analyses)):
        findings = "; ".join(
            f.statement[:100] for f in (analysis.key_findings or [])[:2]
        )
        lines.append(f"[{i}] {paper.title or '(無標題)'}")
        lines.append(f"    主要發現：{findings or '(無)'}")
        lines.append("")
    numbered_papers = "\n".join(lines)

    return f"""\
使用者研究主題：{user_topic}

以下是 {n} 篇文獻的個別分析結果，請使用 `record_comparison_analysis` 工具進行跨文獻整合分析。

=== 各文獻摘要 ===
{numbered_papers}
=== 任務 ===
1. 識別這批文獻的 1-5 個共通主題
2. 識別觀點或方法對立之處（若有）
3. 從這批文獻識別 1-3 個研究 gap（後續研究方向）
4. 給出在文獻回顧中組合這幾篇文獻的建議（如何串接論述）
5. 標註文獻之間的具體關聯（cross_relations，用 index 指涉）

特別注意：所有結論必須基於提供的文獻內容，不要引入外部知識。"""
