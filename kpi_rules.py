"""Demo client Control of Work KPI conformance and status boundaries."""

import calendar
from datetime import date


def reporting_weeks(year, month):
    """Monday weeks intersecting the reporting month, including its opening week."""
    first=date(year,month,1)
    first=date.fromordinal(first.toordinal()-first.weekday())
    last=date(year,month,calendar.monthrange(year,month)[1])
    return [date.fromordinal(day) for day in range(first.toordinal(),last.toordinal()+1,7)]


def weekly_coverage(audits, year, month, target, eligible=lambda audit: True):
    mondays=reporting_weeks(year,month)
    end=date(year,month,calendar.monthrange(year,month)[1])
    counts={monday:0 for monday in mondays}
    for audit in audits:
        if not eligible(audit): continue
        try: day=date.fromisoformat(str(audit.get("audit_date",""))[:10])
        except ValueError: continue
        if not mondays[0]<=day<=end: continue
        monday=date.fromordinal(day.toordinal()-day.weekday())
        counts[monday]+=1
    return sum(count>=target for count in counts.values()),len(mondays)


def presentation_visit_status(ooe_pct, medic_pct, conformance):
    """KPI 4 written leadership-presentation bands; worst assessed measure wins."""
    if any(v is not None and v<50 for v in (ooe_pct,medic_pct)) or (conformance is not None and conformance<70): return "Red"
    if any(v is None for v in (ooe_pct,medic_pct,conformance)): return "Not enough data"
    return "Green" if ooe_pct>=100 and medic_pct>=100 and conformance>=90 else "Amber"


def audit_conformance(audits, *, rounded=True):
    """Whole-audit conformance; request unrounded values for RAG decisions."""
    outcomes = []
    for audit in audits:
        answers = [str(r.get("response", "")).lower() for r in audit.get("responses", [])]
        applicable = [answer for answer in answers if answer in {"yes", "no"}]
        if applicable:
            outcomes.append("no" not in applicable)
    if not outcomes:
        return None
    percentage = 100 * sum(outcomes) / len(outcomes)
    return round(percentage) if rounded else percentage


def completion_percentage(completed, planned):
    """Calculate delivery without rounding across a RAG boundary."""
    return 100 * completed / planned if planned else None


def reporting_period_rows(rows, date_key, start, end):
    """Include dated records only through the selected reporting period."""
    selected = []
    for row in rows:
        try:
            day = date.fromisoformat(str(row.get(date_key, ""))[:10])
        except ValueError:
            continue
        if start <= day <= end:
            selected.append(row)
    return selected


def format_percentage(value):
    """Compact display; the unrounded value remains the decision input."""
    return "—" if value is None else f"{value:.2f}".rstrip("0").rstrip(".") + "%"


def checklist_conformance(audits):
    """Yes / (Yes + No) for applicable scored checklist questions.

    The illustrative demo criteria explicitly fails an entire permit for one No in
    KPIs 1/2. It does not apply that rule to KPI 3/4 monitoring percentages.
    """
    answers=[str(row.get("response", "")).lower()
             for audit in audits for row in audit.get("responses", [])
             if str(row.get("response", "")).lower() in {"yes", "no"}]
    return None if not answers else round(100 * answers.count("yes") / len(answers))


def permit_auditor_role(audit, role_map):
    """Prefer the submitted role; use person mappings only for legacy audits."""
    return (audit.get("metadata") or {}).get("auditor_role") or role_map.get(audit.get("auditor"), "Unconfirmed")


def permit_sample_category(audit):
    """Only an explicit routine/non-routine choice proves the KPI sample category.

    Older forms treated New WCC as the opposite of Routine. A new certificate
    can also be routine, so those historic records require source verification.
    """
    metadata = audit.get("metadata") or {}
    category = metadata.get("permit_sample_category")
    if category in {"Routine", "Non-routine"}:
        return category
    if metadata.get("routine") and not metadata.get("new_wcc"):
        return "Routine"
    return "Unclassified"


def tbt_auditor_role(audit, role_map):
    """Resolve the TBT visitor role per audit, with legacy mapping as fallback."""
    return (audit.get("metadata") or {}).get("auditor_role") or role_map.get(audit.get("auditor"), "Unconfirmed")


def rag_status(completion, conformance):
    if ((completion is not None and completion < 70) or
            (conformance is not None and conformance < 70)):
        return "Red"
    if completion is None or conformance is None:
        return "Not enough data"
    return "Green" if completion >= 100 and conformance >= 90 else "Amber"


def checklist_nonconformance(audits):
    """No / (Yes + No) for applicable scored checklist questions."""
    answers=[str(row.get("response", "")).lower()
             for audit in audits for row in audit.get("responses", [])
             if str(row.get("response", "")).lower() in {"yes", "no"}]
    return None if not answers else round(100 * answers.count("no") / len(answers))


def leadership_status(visits, conformance, coverage, quarter_complete):
    if conformance is not None and conformance < 70:
        return "Red"
    if quarter_complete and visits <= 1:
        return "Red"
    if visits >= 3 and conformance is not None and conformance >= 90 and coverage == "Reasonable":
        return "Green"
    if visits == 2 or (conformance is not None and 70 <= conformance < 90) or coverage == "Imbalanced":
        return "Amber"
    if visits >= 3:
        return "Needs review"
    return "In progress" if not quarter_complete else "Needs review"


def leadership_kpi_breakdown(audits, role_map, nui_sites):
    """Count one identified Remote Site team engagement per eligible checklist record."""
    allowed={"Operations Director","Deputy Operations Director","Asset Superintendent","Ops Support Manager"}
    result={"eligible":[],"outside_nui":[],"role_unconfirmed":[],"other_role":[],"uat_excluded":[]}
    for audit in audits:
        metadata=audit.get("metadata") or {}
        if metadata.get("uat_sample") is True and metadata.get("kpi3_uat_scenario") is False:
            result["uat_excluded"].append(audit)
            continue
        context=metadata.get("engagement_context")
        identified_team=bool((metadata.get("nui_team") or "").strip())
        offsite=context in {"Intervention Team", "Office Engagement", "Quayside Engagement"} and identified_team
        if audit.get("site") not in nui_sites and not offsite:
            result["outside_nui"].append(audit)
            continue
        role=metadata.get("leadership_role") or role_map.get(audit.get("auditor"))
        if role in allowed:result["eligible"].append(audit)
        elif not role:result["role_unconfirmed"].append(audit)
        else:result["other_role"].append(audit)
    return result


def site_visit_status(ooe_pct, medic_pct, conformance, oim_visits, oim_missed_two,
                      oim_missed_rolling, coverage, findings, justification):
    if ((conformance is not None and conformance < 70) or
            findings in {"Significant / repeat", "Controls ineffective"}):
        return "Red"
    if oim_missed_two or oim_missed_rolling:
        return "Red"
    if ((ooe_pct is not None and ooe_pct < 50) or
            (medic_pct is not None and medic_pct < 50)):
        return "Red"
    if ooe_pct is None or medic_pct is None:
        return "Not enough data"
    missed_target = ooe_pct < 100 or medic_pct < 100 or oim_visits < 1
    if missed_target and justification != "Suitable":
        return "Needs review" if justification == "Not assessed" else "Red"
    if conformance is None:
        return "Not enough data"
    if ooe_pct >= 100 and medic_pct >= 100 and oim_visits >= 1 and conformance >= 90:
        if coverage == "Reasonable" and findings == "None":
            return "Green"
        return "Needs review" if coverage == "Not assessed" or findings == "Not assessed" else "Amber"
    if (50 <= ooe_pct < 100 or 50 <= medic_pct < 100 or
            70 <= conformance < 90 or coverage in {"Limited", "Reasonable · late", "Limited · late"} or
            findings in {"Isolated minor", "Recurring minor"}):
        return "Amber"
    return "Amber"



def average_audit_conformance(audits):
    """Equal-weight mean of individual Yes/(Yes+No) audit percentages."""
    scores=[]
    for audit in audits:
        answers=[str(r.get("response", "")).strip().lower() for r in audit.get("responses", [])]
        yes=answers.count("yes"); no=answers.count("no")
        if yes+no:scores.append(100*yes/(yes+no))
    return sum(scores)/len(scores) if scores else None

