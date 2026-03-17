"""
Compliance results display component.

Renders the structured compliance analysis output as:
- Summary metrics (counts of each compliance state)
- Expandable cards for each of the 5 questions
- Color-coded compliance states
- Downloadable JSON report
"""
import json
import streamlit as st
from typing import Dict, Any


# Visual mapping for compliance states
STATE_CONFIG = {
    "Fully Compliant": {"icon": "✅", "color": "green", "bg": "#d4edda"},
    "Partially Compliant": {"icon": "⚠️", "color": "orange", "bg": "#fff3cd"},
    "Non-Compliant": {"icon": "❌", "color": "red", "bg": "#f8d7da"},
}


def render_results(report: Dict[str, Any]):
    """Render the full compliance analysis report."""
    st.subheader(f"📊 Compliance Report: {report['contract_name']}")
    st.caption(
        f"Model: `{report['model_used']}` · "
        f"Analyzed: {report['analysis_timestamp']}"
    )

    # ── Summary Metrics ──
    _render_summary_metrics(report["results"])

    st.divider()

    # ── Detailed Results ──
    for i, result in enumerate(report["results"]):
        _render_single_result(i + 1, result)

    st.divider()

    # ── Download Button ──
    _render_download(report)


def _render_summary_metrics(results: list):
    """Show the count of each compliance state as big metrics."""
    states = [r["compliance_state"] for r in results]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "✅ Fully Compliant",
        states.count("Fully Compliant"),
        help="All criteria for the requirement are met",
    )
    col2.metric(
        "⚠️ Partially Compliant",
        states.count("Partially Compliant"),
        help="Some criteria are met, some are missing",
    )
    col3.metric(
        "❌ Non-Compliant",
        states.count("Non-Compliant"),
        help="None or almost none of the criteria are met",
    )

    # Average confidence
    avg_confidence = sum(r["confidence"] for r in results) / len(results)
    col4.metric(
        "📈 Avg Confidence",
        f"{avg_confidence:.0f}%",
        help="Average confidence across all 5 questions",
    )


def _render_single_result(question_num: int, result: Dict[str, Any]):
    """Render a single compliance question result as an expandable card."""
    state = result["compliance_state"]
    config = STATE_CONFIG.get(state, {"icon": "❓", "color": "gray"})

    header = (
        f"{config['icon']} **Q{question_num}: {result['compliance_question']}** — "
        f":{config['color']}[{state}] · {result['confidence']}% confidence"
    )

    with st.expander(header, expanded=False):
        # Compliance state badge
        st.markdown(
            f"### {config['icon']} {state} "
            f"<small style='color:gray'>({result['confidence']}% confidence)</small>",
            unsafe_allow_html=True,
        )

        # Rationale
        st.markdown("#### 💡 Rationale")
        st.info(result["rationale"])

        # Relevant quotes
        st.markdown("#### 📖 Relevant Quotes from Contract")
        if result["relevant_quotes"]:
            for j, quote in enumerate(result["relevant_quotes"], 1):
                st.markdown(f"**Quote {j}:**")
                st.markdown(f"> _{quote}_")
        else:
            st.warning("No relevant quotes were found for this requirement.")


def _render_download(report: Dict[str, Any]):
    """Render a download button for the full JSON report."""
    st.subheader("📥 Export Report")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📥 Download JSON Report",
            data=json.dumps(report, indent=2, ensure_ascii=False),
            file_name=f"compliance_report_{report['contract_name']}.json",
            mime="application/json",
            use_container_width=True,
        )

    with col2:
        # Also provide a simple text summary
        summary = _generate_text_summary(report)
        st.download_button(
            label="📄 Download Text Summary",
            data=summary,
            file_name=f"compliance_summary_{report['contract_name']}.txt",
            mime="text/plain",
            use_container_width=True,
        )


def _generate_text_summary(report: Dict[str, Any]) -> str:
    """Generate a plain-text summary of the compliance report."""
    lines = [
        f"CONTRACT COMPLIANCE REPORT",
        f"{'=' * 50}",
        f"Contract: {report['contract_name']}",
        f"Model:    {report['model_used']}",
        f"Date:     {report['analysis_timestamp']}",
        f"",
    ]

    for i, r in enumerate(report["results"], 1):
        lines.append(f"Q{i}: {r['compliance_question']}")
        lines.append(f"   State:      {r['compliance_state']}")
        lines.append(f"   Confidence: {r['confidence']}%")
        lines.append(f"   Rationale:  {r['rationale']}")
        lines.append(f"   Quotes:     {'; '.join(r['relevant_quotes'][:3])}")
        lines.append("")

    return "\n".join(lines)