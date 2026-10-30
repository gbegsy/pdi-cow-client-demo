"""Question-level BAR scoring shared by the three assurance forms."""

from datetime import date

BAR_LEVELS = {"BAR 1", "BAR 2", "BAR 3"}


def score_responses(responses):
    """Return the review result; narrative prompts and N/A are excluded."""
    if any(r.get("response") not in {"Yes", "No", "N/A", "Comment"} for r in responses):
        return None
    if any(r.get("bar_rating") not in BAR_LEVELS for r in responses if r.get("response") != "Comment"):
        return None
    applicable = [r for r in responses if r.get("response") in {"Yes", "No"}]
    if not applicable:
        return None
    failed = {r["bar_rating"] for r in applicable if r["response"] == "No"}
    if "BAR 1" in failed:
        return "Non-conformance, BAR 1 question failed"
    if "BAR 2" in failed:
        return "Non-conformance, BAR 2 question failed"
    if "BAR 3" in failed:
        return "Compliant, improvement required"
    return "Compliant"


def validate_responses(responses, require_evidence=True):
    """Return submission errors without changing any question's preset BAR."""
    errors = []
    for r in responses:
        if r.get("response") == "Comment":
            continue
        ref = r.get("item") or r.get("question", "Question")
        answer = r.get("response")
        if r.get("bar_rating") not in BAR_LEVELS:
            errors.append(f"{ref}: approved BAR is missing")
        if answer not in {"Yes", "No", "N/A"}:
            errors.append(f"{ref}: select Yes, No or N/A")
            continue
        if require_evidence and answer in {"Yes", "No"} and not str(r.get("comments_evidence") or "").strip():
            errors.append(f"{ref}: record evidence")
        if answer == "No":
            for field, label in (("smart_action", "SMART action"), ("action_owner", "action owner"), ("action_due_date", "due date")):
                if not str(r.get(field) or "").strip():
                    errors.append(f"{ref}: enter {label}")
            due = str(r.get("action_due_date") or "").strip()
            if due:
                try:
                    date.fromisoformat(due)
                except ValueError:
                    errors.append(f"{ref}: use YYYY-MM-DD for the due date")
            if r.get("bar_rating") == "BAR 1" and not str(r.get("immediate_action") or "").strip():
                errors.append(f"{ref}: record how work was made safe or the current exposure was addressed")
    return errors

