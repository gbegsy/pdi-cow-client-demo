"""Comment mentions for human review, never inferred causes or KPI inputs."""
import re
from collections import Counter

THEMES = {
    "Time, workload and staffing": r"\b(time pressure|rushed|rushing|workload|understaffed|short.staffed|fatigue|tired|deadline|staffing)\b",
    "Procedures and information": r"\b(procedure\w*|instruction\w*|unclear|ambiguous|confusing|outdated|out.of.date|drawing\w*|work pack)\b",
    "Equipment and workplace access": r"\b(equipment|tool\w*|access|layout|lighting|noise|congest\w*|ergonomic\w*)\b",
    "Communication and handover": r"\b(communicat\w*|handover\w*|briefing\w*|language|radio|coordination)\b",
    "Supervision and support": r"\b(supervis\w*|support\w*|leadership|resourc\w*)\b",
    "Competence and familiarity": r"\b(competenc\w*|training|unfamiliar\w*|inexperienced|experience|knowledge|understanding)\b",
    "Adaptations and what helped": r"\b(adapt\w*|workaround\w*|work around|helped|worked well|made easier|useful|improvis\w*)\b",
}
PLACEHOLDERS = {"", "yes", "no", "na", "n/a", "none", "nil", "not applicable", "no comment", "no comments", "not recorded", "-", "test"}
# HSG48's three interacting aspects. Topic mappings are application suggestions,
# not an HSE classification algorithm; overlap is intentional.
DOMAINS = {
    "Time, workload and staffing": ["Job", "Organisation"],
    "Procedures and information": ["Job"],
    "Equipment and workplace access": ["Job"],
    "Communication and handover": ["Organisation"],
    "Supervision and support": ["Organisation"],
    "Competence and familiarity": ["Individual"],
    "Adaptations and what helped": [],
}
GUIDANCE_URL = "https://www.hse.gov.uk/pubns/priced/hsg48.pdf"


def comment_records(audits):
    """Only entered narrative is matched; question wording never supplies evidence."""
    out = []
    for audit in audits:
        meta = audit.get("metadata") or {}
        if meta.get("uat_sample") or meta.get("demo") or audit.get("audit_id", "").startswith("DEMO-"):
            continue
        sources = [(r.get("item", ""), r.get("question", ""), r.get("response", ""), r.get("comments_evidence", "")) for r in audit.get("responses", [])]
        sources += [(key, label, "Narrative", meta.get(key, "")) for key, label in [
            ("auditor_notes", "Auditor notes"), ("opportunities_for_improvement", "Opportunities for improvement"),
            ("positive_observations", "Positive observations"), ("actions_agreed", "Actions agreed")]]
        for ref, prompt, result, value in sources:
            text = value.strip() if isinstance(value, str) else ""
            if text.lower().strip(" .!") in PLACEHOLDERS:
                continue
            matches = {name: sorted({m.group(0) for m in re.finditer(pattern, text, re.I)}, key=str.casefold) for name, pattern in THEMES.items()}
            matches = {k: v for k, v in matches.items() if v}
            domains = sorted({domain for theme in matches for domain in DOMAINS[theme]})
            out.append({
                "Audit ID": audit.get("audit_id", ""), "Date": audit.get("audit_date", ""),
                "Site / Team": audit.get("site", ""), "Form": audit.get("form_name", ""),
                "Source reference": ref, "Question / field": prompt, "Recorded answer": result,
                "Original comment": text, "Potential themes": "; ".join(matches) or "Unclassified - review comment",
                "Suggested HSG48 aspects": "; ".join(domains) or "Unclassified - context review required",
                "Matched wording": "; ".join(f'{k}: {", ".join(v)}' for k, v in matches.items()),
                "Review status": "Not reviewed", "_themes": list(matches), "_domains": domains})
    return out


def render(audits, period):
    import streamlit as st
    import pandas as pd
    st.subheader("Human Factors · What audit comments reveal")
    st.caption("FICTIONAL DEMONSTRATION · Example observations illustrate what submitted audit comments could reveal. They are not actual findings.")
    st.caption("Uses recorded comments, discussion answers and leadership notes in the selected reporting view. No additional questions or KPI scoring changes.")
    st.markdown("**HSG48 framework:** Job (task, workload, equipment, environment and procedures); Individual (competence, skills and familiarity); Organisation (resources, work patterns, communication and leadership). These aspects interact.")
    st.markdown("[HSE HSG48 - Reducing error and influencing behaviour](" + GUIDANCE_URL + ")")
    st.info("Potential themes are wording matches for human review, not confirmed contributing factors or root causes. A mention may describe a difficulty, something helpful, a suggestion, or the absence of a problem. Read the original account before interpreting it.")
    st.caption("HSG48 supplies the framework, not the automated wording rules. Suggested mappings can overlap and need review. No slips, lapses, mistakes, violations, attitudes or personal blame are inferred.")
    rows = comment_records(audits)
    if not rows:
        st.info("Insufficient narrative evidence. No substantive comments are recorded in this selection. Yes/No answers and question wording are not used to invent HF themes.")
        return
    counts = Counter(theme for row in rows for theme in row["_themes"])
    domain_counts = Counter(domain for row in rows for domain in row["_domains"])
    a, b = st.columns(2)
    a.metric("Recorded comment entries", len(rows))
    b.metric("Entries without a suggested theme", sum(not r["_themes"] for r in rows))
    if domain_counts:
        st.dataframe(pd.DataFrame([{"HSG48 aspect - suggested": k, "Comment entries mentioning related topics": v} for k, v in domain_counts.most_common()]), hide_index=True, use_container_width=True)
    if counts:
        st.dataframe(pd.DataFrame([{"Potential theme": k, "Comment entries mentioning theme": v} for k, v in counts.most_common()]), hide_index=True, use_container_width=True)
        st.caption("Entries may mention several themes. Counts are comments, not people, incidents or verified HF findings.")
    else:
        st.caption("Comments are available but no potential themes matched. Review the original accounts below.")
    st.markdown("**Source comments for review**")
    frame = pd.DataFrame([{k: v for k, v in row.items() if not k.startswith("_")} for row in rows])
    f1,f2=st.columns(2)
    aspect=f1.selectbox("HSG48 aspect",["All","Job","Individual","Organisation"],key="hf-aspect")
    theme=f2.selectbox("Comment theme",["All"]+list(THEMES),key="hf-theme")
    if aspect!="All": frame=frame[frame["Suggested HSG48 aspects"].str.contains(aspect,regex=False)]
    if theme!="All": frame=frame[frame["Potential themes"].str.contains(theme,regex=False)]
    st.caption(f"{len(frame)} source comments shown. Counts above describe the full reporting selection; filters below narrow the source list.")
    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.download_button("Download comment review CSV", frame.to_csv(index=False).encode("utf-8"), file_name="CoW_HF_Comment_Review_" + period + ".csv", mime="text/csv", key="hf-comment-download")
    st.caption("All suggestions are unreviewed. This section does not save approvals or alter audit records. Suggested improvements and actions are not proof that a condition occurred.")

