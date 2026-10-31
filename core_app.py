import streamlit as st
import pandas as pd
import sqlite3, json, uuid, calendar, os, html
from pathlib import Path

try:
    import psycopg
except ImportError:
    psycopg = None
from datetime import date, datetime
from scoring import score_responses, validate_responses
from kpi_rules import reporting_weeks, presentation_visit_status, audit_conformance, checklist_conformance, permit_auditor_role, permit_sample_category, tbt_auditor_role, rag_status, leadership_status, leadership_kpi_breakdown, checklist_nonconformance, site_visit_status, weekly_coverage, completion_percentage, reporting_period_rows, format_percentage

BASE = Path(__file__).parent
DATA = json.loads((BASE / "questions.json").read_text(encoding="utf-8"))
import tempfile
if st.session_state.get("_client_demo_scenario") != "conformance-75-83-hf-v4":
    st.session_state["client_demo_dir"] = tempfile.mkdtemp(prefix="pdi-cow-client-demo-")
    st.session_state["_client_demo_scenario"] = "conformance-75-83-hf-v4"
DB = Path(st.session_state["client_demo_dir"]) / "demo.db"
# Standalone demo: never read deployment secrets or external database settings.
DATABASE_URL = ""

class DatabaseConnection:
    """Small compatibility layer for SQLite and PostgreSQL."""

    def __init__(self):
        if DATABASE_URL:
            if psycopg is None:
                raise RuntimeError("PostgreSQL support is not installed.")
            self.connection = psycopg.connect(DATABASE_URL)
            self.postgres = True
        else:
            self.connection = sqlite3.connect(DB)
            self.postgres = False

    def execute(self, query, params=()):
        if self.postgres:
            if query == "INSERT OR REPLACE INTO roles VALUES(?,?,?)":
                query = (
                    "INSERT INTO roles(mapping_type,person_name,role_name) "
                    "VALUES(%s,%s,%s) ON CONFLICT(mapping_type,person_name) "
                    "DO UPDATE SET role_name=EXCLUDED.role_name"
                )
            elif query.startswith("INSERT OR REPLACE INTO kpi5 VALUES("):
                query = query.replace("INSERT OR REPLACE INTO kpi5", "INSERT INTO kpi5")
                query = query.replace("?", "%s")
                query += (
                    " ON CONFLICT(record_id) DO UPDATE SET "
                    "submitted_at=EXCLUDED.submitted_at, reporting_month=EXCLUDED.reporting_month, "
                    "site=EXCLUDED.site, current_count=EXCLUDED.current_count, "
                    "previous_count=EXCLUDED.previous_count, hipo=EXCLUDED.hipo, "
                    "injury=EXCLUDED.injury, loc=EXCLUDED.loc, major_loc=EXCLUDED.major_loc, "
                    "repeat_theme=EXCLUDED.repeat_theme, recurring_failure=EXCLUDED.recurring_failure, "
                    "significant_increase=EXCLUDED.significant_increase, comments=EXCLUDED.comments, "
                    "demo=EXCLUDED.demo"
                )
            else:
                query = query.replace("?", "%s")
        return self.connection.execute(query, params)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


st.set_page_config(page_title="PDi Demo - Control of Work Assurance", page_icon="🔒", layout="wide")
st.markdown("""
<style>
.block-container{max-width:1450px;min-width:0;box-sizing:border-box;padding-top:1.5rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#f7f9fb,#edf2f6);border-right:1px solid #d8e1e7}
[data-testid="stSidebar"] div[role="radiogroup"] label{background:#fff;border:1px solid #d7e1e8;border-radius:9px;padding:8px 10px;margin:2px 0}
.oa-banner{background:#000;color:#fff;min-height:118px;display:flex;align-items:center;justify-content:center;gap:26px;text-align:center;margin-bottom:8px}.oa-logo{width:145px;height:auto;background:#fff;border-radius:6px;padding:9px 12px}.brand-row{display:flex;align-items:center;gap:18px}.brand-logo{width:155px;height:auto;background:#fff;border-radius:6px;padding:8px 11px;transform:translateY(4px)}
.oa-title{font-size:23px;font-weight:800;line-height:1.35;padding:20px}.oa-sub{font-size:20px;margin-top:8px}
.purpose{border:1px solid #222;padding:9px 11px;font-size:13px;line-height:1.4;margin-bottom:8px;background:#fff}
.blackbar{background:#000;color:#fff;font-weight:800;padding:7px 10px;margin-top:8px}.section-title{font-size:18px;font-weight:800;margin:20px 0 8px}.qrow{padding:9px 0 5px;font-size:15px;line-height:1.45}.bar{display:inline-block;border-radius:3px;padding:2px 6px;margin-left:7px;font-size:10px;font-weight:700;letter-spacing:.2px;color:#fff;background:#242424}
.dash{background:#102f4b;color:#fff;margin:0 0 14px;padding:20px 26px 22px;border-radius:10px}.dash .eyebrow{font-size:11px;font-weight:800;letter-spacing:1.5px;color:#acd4ee}.dash h1{font-size:29px;margin:13px 0 7px}.dash p{margin:0;color:#d5e4ef;font-size:14px}.selection{border-left:4px solid #1479c9;background:#e8f5fc;padding:10px 12px;margin:10px 0 14px;color:#16364b;font-size:13px}.section-head{font-size:20px;font-weight:800;color:#102b40;margin:18px 0 10px}
.kpi{background:#fff;border:1px solid #d9e2ea;border-left:5px solid #9aabb8;border-radius:10px;padding:16px;min-height:335px;display:flex;flex-direction:column;box-shadow:0 3px 15px #102a4312;overflow-wrap:anywhere}.kpi.green{border-left-color:#16865b}.kpi.amber{border-left-color:#bd7600}.kpi.red{border-left-color:#bd3d43}.kpi.review{border-left-color:#69879b}.kt{font-size:11px;font-weight:800;letter-spacing:.7px;color:#65798c}.kv{font-size:28px;font-weight:800;color:#102b40;margin:12px 0 7px;line-height:1.05}.kd{font-size:12px;color:#506677;line-height:1.5;margin-top:10px}.ks{font-size:15px;font-weight:700;color:#102b40;line-height:1.32;margin-top:6px;min-height:42px}.badge{display:inline-block;border-radius:999px;padding:4px 9px;font-size:10px;font-weight:800;letter-spacing:.2px;background:#edf1f4;color:#455a68}.badge.green{background:#e4f6ec;color:#16865b}.badge.amber{background:#fff1d2;color:#9b6200}.badge.red{background:#fde7e7;color:#a02c34}.badge.review{background:#e7eef4;color:#395d77}
.metric-pair{display:grid;gap:9px;margin:11px 0 10px}.metric-line{border-top:1px solid #e5ebf0;padding-top:7px}.metric-line span{display:block;font-size:10px;font-weight:800;letter-spacing:.6px;color:#65798c;text-transform:uppercase;line-height:1.3}.metric-line strong{display:block;font-size:19px;color:#102b40;line-height:1.2;margin-top:3px;overflow-wrap:anywhere}.rag-reason{font-size:12px;line-height:1.4;color:#334c5d;margin-top:9px}.kpi .badge{align-self:flex-start}.kpi .kd{border-top:1px solid #e5ebf0;padding-top:8px;margin-top:auto}
.summary{display:grid;grid-template-columns:minmax(240px,1.4fr) repeat(4,minmax(0,1fr));gap:12px;margin:0 0 13px}.summary-main,.summary-stat{border-radius:10px;padding:16px;border:1px solid #d9e2ea;box-shadow:0 3px 15px #102a4312;min-width:0}.summary-main{background:#102f4b;color:#fff;border-color:#102f4b}.summary-main .summary-label{color:#acd4ee}.summary-label{display:block;color:#65798c;font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;line-height:1.35}.summary-value{display:block;font-size:29px;font-weight:800;line-height:1.1;margin:11px 0 7px;color:#162b43}.summary-main .summary-value{color:#fff}.summary-sub{display:block;color:#65798c;font-size:12px;line-height:1.45}.summary-main .summary-sub{color:#d5e4ef}.summary-stat{background:#fff}.uat-note{border-left:4px solid #bd7600;background:#fff3d8;color:#5e4b23;padding:10px 12px;font-size:12px;line-height:1.45;margin:0 0 13px;border-radius:6px}
@media(max-width:1400px){
  .block-container{width:100%;max-width:100%;padding-left:1.25rem;padding-right:1.25rem}
  [data-testid="stHorizontalBlock"]{width:100%;min-width:0;flex-wrap:wrap}
  [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 245px;min-width:0;max-width:100%}
  .dash{padding:18px 22px}
}
@media(max-width:1120px){
  .summary{grid-template-columns:repeat(2,minmax(0,1fr))}.summary-main{grid-column:span 2}
}
@media(max-width:650px){
  .block-container{padding-left:1rem;padding-right:1rem}
  .kpi{min-height:0}
  [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex-basis:100%}
  .brand-row{flex-wrap:wrap;gap:9px}.brand-logo{max-width:145px}
  .dash{padding:17px}.dash h1{font-size:clamp(23px,6vw,29px);margin:13px 0 8px}
  .selection{overflow-wrap:anywhere}
  .summary{grid-template-columns:1fr}.summary-main{grid-column:auto}
}

/* Equal-height KPI cards keep all five tolerance controls on the same baseline. */
[data-testid="stHorizontalBlock"]:has(.kpi){align-items:stretch}
[data-testid="stColumn"]:has(.kpi){display:flex;flex-direction:column}
[data-testid="stColumn"]:has(.kpi) [data-testid="stVerticalBlock"]{flex:1}
[data-testid="stElementContainer"]:has(.kpi){flex:1;display:flex}
[data-testid="stElementContainer"]:has(.kpi) [data-testid="stMarkdown"],
[data-testid="stElementContainer"]:has(.kpi) [data-testid="stMarkdownContainer"]{width:100%;height:100%}
.kpi{height:100%;box-sizing:border-box;min-height:420px}
.kpi .ks{min-height:44px}
.kpi .metric-line span{min-height:27px}
.kpi .metric-line strong{min-height:46px}
.kpi .rag-reason{min-height:48px}
@media(max-width:650px){
 .kpi{height:auto;min-height:0}
 .kpi .metric-line span,.kpi .metric-line strong,.kpi .rag-reason{min-height:0}
}


/* Prominent dashboard review navigation. */
[role="tablist"]{
 gap:8px;padding:10px;background:#edf3f8;border:1px solid #cbd9e5;
 border-radius:12px;flex-wrap:wrap;height:auto
}
[role="tab"]{
 background:#fff;border:1px solid #b8cbdc;border-radius:8px;
 padding:11px 16px;min-height:48px;height:auto;color:#15394f;font-weight:700
}
[role="tab"] p{
 font-size:15px;font-weight:700
}
[role="tab"]:hover{
 background:#dcebf5;border-color:#2c719c;color:#102f4b
}
[role="tab"][aria-selected="true"]{
 background:#102f4b;border-color:#102f4b;color:#fff;
 box-shadow:0 2px 5px #102f4b25
}
[role="tab"]:focus-visible{
 outline:3px solid #1684c1;outline-offset:3px
}
[data-baseweb="tab-highlight"],
[data-baseweb="tab-border"]{display:none}


/* Full RAG border on every KPI tile. */
.kpi{border:6px solid #69879b}
.kpi.green{border-color:#16865b}
.kpi.amber{border-color:#bd7600}
.kpi.red{border-color:#bd3d43}
.kpi.review{border-color:#69879b}


/* Fixed internal rows keep every KPI card and status badge aligned. */
.kpi{
 height:540px!important;min-height:540px;display:grid;
 grid-template-rows:14px 60px 192px 24px 56px minmax(72px,1fr);
 gap:8px;padding:16px;box-sizing:border-box;align-content:stretch
}
.kpi .kt,.kpi .ks,.kpi .metric-pair,.kpi .rag-reason,.kpi .kd{margin:0}
.kpi .ks{min-height:0}
.kpi .metric-pair{display:grid;grid-template-rows:112px 72px;gap:8px}
.kpi .metric-line{min-height:0}
.kpi .metric-line span{min-height:28px}
.kpi .metric-line strong{min-height:0;font-size:18px;line-height:1.25}
.kpi .badge{align-self:start;justify-self:start}
.kpi .rag-reason{min-height:0}
.kpi .kd{padding-top:8px;align-self:stretch;overflow-wrap:anywhere}
@media(max-width:650px){
 .kpi{height:auto!important;min-height:0;display:flex;gap:10px}
 .kpi .ks,.kpi .metric-line span{min-height:0}
 .kpi .metric-pair{display:grid;grid-template-rows:auto auto;gap:10px}
}


/* Single-view navigation: visible labels, large targets, no hidden offscreen tabs. */
[data-testid="stRadio"] div[role="radiogroup"]{gap:8px}
[data-testid="stRadio"] div[role="radiogroup"] label{border:1px solid #b8cbdc;background:white;border-radius:8px;padding:10px 14px;min-height:44px}
[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){background:#dcebf5;border:2px solid #15394f;font-weight:700}
 /* Quiet, consistent application surfaces and keyboard focus. */
[data-testid="stAppViewContainer"]{background:#f7f9fc}
[data-testid="stMainBlockContainer"]{max-width:1480px}
.dash{padding:18px 24px;margin-bottom:12px}
.dash h1{font-size:27px;margin:10px 0 6px}
.dash p{font-size:14px}
.oa-banner{background:#102f4b;border-radius:10px;min-height:92px}
.purpose{border:1px solid #d7e2eb;border-left:4px solid #497b9f;border-radius:7px;background:#fff;padding:12px 14px}
.blackbar{background:#15394f;border-radius:6px;padding:9px 12px}
.section-title{color:#15394f;border-bottom:1px solid #d7e2eb;padding-bottom:7px}
.qrow{line-height:1.55}
[data-testid="stMetric"]{background:#fff;border:1px solid #dce5ee;border-radius:9px;padding:14px 16px}
[data-testid="stMetricValue"]{font-size:30px;font-weight:650;color:#15394f}
[data-testid="stExpander"]{border-color:#d3dfe9;border-radius:9px;background:#fff}
[data-testid="stExpander"] summary{font-weight:600}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button{border-radius:8px;min-height:42px;font-weight:600}
[data-testid="stButton"] button[kind="primary"]{background:#15394f;border-color:#15394f;color:white}
button:focus-visible,input:focus-visible,textarea:focus-visible,[role="combobox"]:focus-visible{outline:3px solid #1684c1;outline-offset:2px}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:#e3eef7;border-color:#7fa6c3}
[data-testid="stSidebar"] h3{color:#15394f}
.selection{border-radius:7px}
.kpi{background:#fff}
@media(max-width:650px){.dash{padding:16px}.dash h1{font-size:24px}[data-testid="stMetric"]{padding:12px}}

</style>
""", unsafe_allow_html=True)

SITE_GROUPS = {
    "Site Alpha": (1,1),
    "Site Bravo": (1,1),
    "Site Charlie": (1,1),
    "North Remote Sites": (2,1),
    "Site Delta": (1,1),
    "Site Echo": (1,1),
    "South Remote Sites": (2,1),
}
ASSET_GROUPS = list(SITE_GROUPS)
AS_ASSURANCE_GROUPS = ["Site Charlie", "Site Bravo", "North Mobile Team", "North Support Team", "Site Alpha", "Site Echo", "South Mobile Team", "South Support Team", "Site Delta"]

def schema_target():
    # Session-scoped bootstrap marker; never cache audit data or credentials.
    import hashlib
    identity = hashlib.sha256(DATABASE_URL.encode()).hexdigest() if DATABASE_URL else str(DB.resolve())
    inode = DB.stat().st_ino if not DATABASE_URL and DB.exists() else None
    revision = (Path(__file__).stat().st_mtime_ns, Path(__file__).stat().st_size)
    return identity, inode, revision

_SCHEMA_READY = st.session_state.get("_cow_schema_ready") == schema_target()


def db():
    global _SCHEMA_READY
    c=DatabaseConnection()
    if not _SCHEMA_READY:
        c.execute("CREATE TABLE IF NOT EXISTS kpi_recovery_actions(action_id TEXT PRIMARY KEY,reporting_period TEXT,scope TEXT,kpi TEXT,owner_name TEXT,owner_id TEXT,action_text TEXT,due_date TEXT,status TEXT,verification_note TEXT,history TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS people(person_id TEXT PRIMARY KEY,display_name TEXT UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS audits(audit_id TEXT PRIMARY KEY,submitted_at TEXT,form_name TEXT,audit_date TEXT,site TEXT,auditor TEXT,reference TEXT,metadata TEXT,responses TEXT,summary TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS roles(mapping_type TEXT,person_name TEXT,role_name TEXT,PRIMARY KEY(mapping_type,person_name))")
        c.execute("CREATE TABLE IF NOT EXISTS kpi5(record_id TEXT PRIMARY KEY,submitted_at TEXT,reporting_month TEXT,site TEXT,current_count INTEGER,previous_count INTEGER,hipo INTEGER,injury INTEGER,loc INTEGER,major_loc INTEGER,repeat_theme TEXT,recurring_failure TEXT,significant_increase TEXT,comments TEXT,demo INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS kpi4_visits(visit_id TEXT PRIMARY KEY,visit_date TEXT,role TEXT,site TEXT,team TEXT,source_reference TEXT UNIQUE,recorded_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS governance(period TEXT,site TEXT,kpi2_alignment TEXT,kpi2_ind_conf INTEGER,kpi2_ind_find INTEGER,kpi2_self_find INTEGER,kpi3_coverage TEXT,kpi4_justification TEXT,kpi4_oim_coverage TEXT,kpi4_findings TEXT,kpi4_oim_consecutive INTEGER,kpi4_oim_12m INTEGER,PRIMARY KEY(period,site))")
        c.commit()
        # Synthetic dataset migrations are explicit maintenance tasks, never app startup.
        _SCHEMA_READY = True
        st.session_state["_cow_schema_ready"] = schema_target()
    return c

def save_audit(form,meta,responses,summary=""):
    aid="OA-"+datetime.now().strftime("%Y%m%d")+"-"+uuid.uuid4().hex[:6].upper()
    summary = summary or score_responses(responses) or "Incomplete"
    c=db(); c.execute("INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,datetime.now().isoformat(timespec="seconds"),form,meta.get("audit_date",""),meta.get("site",""),meta.get("auditor",""),meta.get("reference",""),json.dumps(meta),json.dumps(responses),summary)); c.commit(); c.close(); return aid

def audits():
    c=db(); rows=c.execute("SELECT * FROM audits ORDER BY submitted_at").fetchall(); c.close(); out=[]
    for r in rows:
        out.append(dict(zip(["audit_id","submitted_at","form_name","audit_date","site","auditor","reference","metadata","responses","summary"],r)))
    for a in out:
        try:a["metadata"]=json.loads(a["metadata"] or "{}")
        except:a["metadata"]={}
        try:a["responses"]=json.loads(a["responses"] or "[]")
        except:a["responses"]=[]
        a["summary"]=(a["summary"] or "").replace("Non-Compliant","Non-conformance")
    return out

def role_maps():
    c=db(); rows=c.execute("SELECT mapping_type,person_name,role_name FROM roles").fetchall(); c.close()
    result={kind:{} for kind in ("permit","tbt","lead")}
    for kind,name,role in rows:
        if kind in result:result[kind][name]=role
    return result

def set_role(kind,name,role):
    c=db(); c.execute("INSERT OR REPLACE INTO roles VALUES(?,?,?)",(kind,name,role)); c.commit(); c.close()

def visit_register_visits():
    c=db(); rows=c.execute("SELECT visit_id,visit_date,role,site,team,source_reference FROM kpi4_visits ORDER BY visit_date").fetchall(); c.close()
    return [dict(zip(("visit_id","visit_date","role","site","team","source_reference"),row)) for row in rows]

DEMO_BRAND = "PDi | VERIFY"

def banner(title,sub=""):
    s=f'<div class="oa-sub">{sub}</div>' if sub else ""
    st.markdown(f'<div class="oa-banner"><strong style="font-size:25px;padding:20px">PDi | VERIFY</strong><div class="oa-title">{title}{s}</div></div>',unsafe_allow_html=True)

def purpose(text): st.markdown(f'<div class="purpose"><b>PURPOSE:</b> {text}</div>',unsafe_allow_html=True)

def bar_review(evidence_required=True):
    with st.expander("How to identify critical and operational controls"):
        st.markdown("Use the approved WCC, task risk assessment and applicable client procedures to identify the controls required for this task. Critical controls prevent or mitigate a credible major accident or serious harm; examples may include specified isolations, containment and gas-testing requirements. Operational controls include task-specific measures from COSHH, manual handling and other assessments. These examples are guidance, not a substitute for the approved task documents. If the designation is unclear, seek AA/Site Controller clarification before treating a control as verified.")
        st.markdown("**BAR 1 — Critical control verification:** A question directly checks that a required control preventing a credible major accident, serious injury or significant process safety event is present and effective, or that work was stopped and made safe when it was lost. A No requires immediate action to make work safe.")
        st.markdown("**BAR 2 — Operational control:** A question checks how work is planned, understood, supervised or carried out. A No requires correction and tracking.")
        st.markdown("**BAR 3 — Management and learning:** A question checks oversight, records, lessons or improvement follow-up rather than a live worksite control. A No requires an improvement action.")
        st.caption("Illustrative demo classification; agree with each client before operational use. The BAR is preset for each question; do not grade the individual finding. A partial or undemonstrated answer is No. "+("Record evidence for Yes and No; an N/A reason is optional. " if evidence_required else "A No requires a recorded SMART action. ")+"Escalate any separate serious concern on its own merits.")

def person_input(container, label, key):
    return container.text_input(label,key=key,placeholder="Enter full name")


def response_key(prefix, si, qi, state):
    kind="permit" if prefix=="ptw" else "lead" if prefix=="lead" else "tbt"
    return f"{prefix}-{si}-{qi}-v{state.get(kind+'_generation',0)}"


def question_applies(prefix, section_index, state):
    if prefix == "ptw":
        if section_index == 2: return state.get("permit-category") == "Routine"
        if section_index == 1: return bool(state.get("permit-new"))
    return True


def questions(prefix,sections,show_evidence=True):
    out=[]
    for si,(section,qs) in enumerate(sections):
        if not question_applies(prefix, si, st.session_state): continue
        st.markdown(f'<div class="section-title">{section}</div>',unsafe_allow_html=True)
        for qi,item in enumerate(qs):
            letter,q,bar=item[:3]
            expected=item[3] if len(item)>3 else ""
            bar_class=bar.lower().replace(" ","")
            st.markdown(f'<div class="qrow"><b>{"5"+chr(97+qi) if prefix=="tbt37" and str(section).startswith("5.") else letter}</b> {q}<span class="bar {bar_class}">{bar}</span></div>',unsafe_allow_html=True)
            if expected and show_evidence: st.caption("Evidence expected: "+expected)
            if show_evidence:
                c1,c2=st.columns([1,2])
                ans=c1.radio("Response",["Yes","No","N/A"],index=None,horizontal=True,key=response_key(prefix,si,qi,st.session_state),label_visibility="collapsed")
                evidence=c2.text_input("Evidence / N/A reason",key=f"evidence-{prefix}-{si}-{qi}",placeholder="Evidence for Yes/No; optional reason for N/A",label_visibility="collapsed")
            else:
                ans=st.radio("Response",["Yes","No","N/A"],index=None,horizontal=True,key=response_key(prefix,si,qi,st.session_state),label_visibility="collapsed")
                evidence=""
            act=owner=due=immediate=""
            if ans=="No":
                act=st.text_input("SMART action",key=f"act-{prefix}-{si}-{qi}")
                c3,c4=st.columns(2)
                owner=person_input(c3,"Action owner",key=f"owner-{prefix}-{si}-{qi}")
                due=c4.date_input("Action due date",value=None,format="DD/MM/YYYY",key=f"due-{prefix}-{si}-{qi}")
                if bar=="BAR 1": immediate=st.text_input("Immediate safety action / current exposure",key=f"immediate-{prefix}-{si}-{qi}")
            out.append({"section":section,"item":letter,"bar_rating":bar,"question":q,"response":None if ans=="Select" else ans,"comments_evidence":evidence,"smart_action":act,"action_owner":owner,"action_due_date":str(due) if due else "","immediate_action":immediate})
    return out

def question_values(prefix, sections, state):
    """Collect the current widget values when Submit is clicked."""
    rows=[]
    for si,(section,qs) in enumerate(sections):
        if not question_applies(prefix, si, state): continue
        for qi,item in enumerate(qs):
            letter,q,bar=item[:3]
            suffix=f"{prefix}-{si}-{qi}"
            answer=state.get(response_key(prefix,si,qi,state),"Select")
            rows.append({"section":section,"item":letter,"bar_rating":bar,"question":q,
                         "response":None if answer=="Select" else answer,
                         "comments_evidence":state.get(f"evidence-{suffix}",""),
                         "smart_action":state.get(f"act-{suffix}","") if answer=="No" else "",
                         "action_owner":state.get(f"owner-{suffix}","") if answer=="No" else "",
                         "action_due_date":str(state.get(f"due-{suffix}")) if answer=="No" and state.get(f"due-{suffix}") else "",
                         "immediate_action":state.get(f"immediate-{suffix}","") if answer=="No" else ""})
    return rows

def submit_assurance(kind):
    """Run before Streamlit redraws the page, so a saved form resets once."""
    s=st.session_state
    if kind=="permit":
        site=(s.get("permit-site") or "").strip(); auditor=(s.get("permit-auditor") or "").strip()
        nw=s.get("permit-new",False); category=s.get("permit-category")
        role=s.get("permit-role","Site Controller")
        meta={"site":site,"team":s.get("permit-team",""),"audit_date":str(s.get("permit-date",date.today())),
              "auditor":auditor,"site_controller":s.get("permit-controller",""),"reference":s.get("permit-ref",""),
              "wcc_description":s.get("permit-description",""),"new_wcc":nw,"routine":category=="Routine",
              "permit_sample_category":category,"assurance_group":s.get("permit-assurance-group") if role=="Asset Superintendent" else "",
              "auditor_role":role}
        rows=question_values("ptw",DATA["ptw"],s)
        error=("Complete SITE / INSTALLATION and AUDITOR." if site in ("", "Select...") or not auditor else
               "Select Routine or Non-routine for the KPI permit sample." if not category else
               "Select the independent assurance group." if role=="Asset Superintendent" and s.get("permit-assurance-group") in (None,"Select...") else "")
        form="Control of Work: Permit Quality"
        prefixes=("permit-","ptw-","evidence-ptw-","act-ptw-","owner-ptw-","due-ptw-","immediate-ptw-")
    elif kind=="tbt":
        site=(s.get("tbt-site") or "").strip(); auditor=(s.get("tbt-auditor") or "").strip(); activity=s.get("tbt-activity")
        role=s.get("tbt-role","Select role...")
        meta={"site":site,"team":s.get("tbt-team",""),"audit_date":str(s.get("tbt-date",date.today())),
              "auditor":auditor,"site_controller":s.get("tbt-controller",""),"reference":s.get("tbt-ref",""),
              "description":s.get("tbt-description",""),"activity_type":activity,
              "permit_sample_category":activity if activity in ("Routine","Non-routine") else "Not applicable",
              "new_wcc":bool(s.get("tbt-new-wcc")) if activity!="POP" else False,
              "auditor_role":role}
        rows=question_values("tbt12",DATA["tbt"][:2],s)
        rows+=question_values("pop",DATA["pop"],s) if activity=="POP" else question_values("tbt37",DATA["tbt"][2:],s)
        error=("Complete SITE / INSTALLATION, AUDITOR and TYPE." if site in ("", "Select...") or not auditor or not activity else
               "Select the auditor role for KPI reporting." if role=="Select role..." else
               "Select Routine or Non-routine for the sampled permit." if activity not in ("POP","Routine") and not s.get("tbt-permit-category") else "")
        form="Control of Work: Toolbox Talk, Permit Compliance & Operating Procedures"
        prefixes=("tbt-","tbt12-","tbt37-","pop-","evidence-tbt12-","evidence-tbt37-","evidence-pop-",
                  "act-tbt12-","act-tbt37-","act-pop-","owner-tbt12-","owner-tbt37-","owner-pop-",
                  "due-tbt12-","due-tbt37-","due-pop-","immediate-tbt12-","immediate-tbt37-","immediate-pop-")
    elif kind=="lead":
        site=(s.get("lead-site") or "").strip(); leader=(s.get("lead-representative") or "").strip()
        role=s.get("lead-role","Select role...")
        start=s.get("lead-period-start",date.today().replace(day=1)); end=s.get("lead-period-end",date.today())
        meta={"site":site,"audit_date":str(s.get("lead-date",date.today())),"auditor":leader,
              "site_controller":s.get("lead-controller",""),"reference":"","leadership_role":role,
              "engagement_context":s.get("lead-context"),"nui_team":s.get("lead-nui-team","").strip(),
              "learning_review_period_start":str(start),"learning_review_period_end":str(end),
              "opportunities_for_improvement":s.get("lead-improvement",""),"auditor_notes":s.get("lead-notes","")}
        rows=question_values("lead",DATA["lead"],s)
        for ref,prompt in DATA["lead_narrative"]:
            rows.append({"section":"Conversation prompts","item":ref,"question":prompt,
                         "response":"Comment","comments_evidence":s.get(f"lead-narrative-{ref}","")})
        error=("Complete Location / Team and Leadership Representative." if site in ("", "Select...") or not leader else
               "Select the leadership role for KPI reporting." if role=="Select role..." else
               "Identify the Remote Site team for this offsite engagement." if s.get("lead-context") in ("Intervention Team","Office Engagement","Quayside Engagement") and not meta["nui_team"] else
               "The learning review period start must be on or before its end." if start>end else "")
        form="Control of Work Leadership Engagement Checklist"
        prefixes=("lead-","evidence-lead-","act-lead-","owner-lead-","due-lead-","immediate-lead-")
    else:
        raise ValueError("Unknown assurance form")

    meta["question_version"]="2026-10-28-section13-restored"
    meta["name_entry_mode"]="free_text_trial"
    if not error:
        errors=validate_responses(rows,require_evidence=(kind=="lead"))
        if errors:error="Complete the question records: "+"; ".join(errors[:8])+(f"; and {len(errors)-8} more" if len(errors)>8 else "")
    if error:
        s["audit_notice"]=(kind,"error",error)
        return
    try:
        aid=save_audit(form,meta,rows)
    except Exception:
        s["audit_notice"]=(kind,"error","The audit could not be saved. Your answers are still on this form; please try again.")
        return
    result_text=score_responses(rows)
    for key in list(s.keys()):
        if key.startswith(prefixes):del s[key]
    s[kind+"_generation"]=s.get(kind+"_generation",0)+1
    s["audit_notice"]=(kind,"success",f"Submitted: {aid} · {result_text}. Form cleared for the next audit.")

def show_audit_notice(kind):
    notice=st.session_state.get("audit_notice")
    if notice and notice[0]==kind:
        st.session_state.pop("audit_notice")
        (st.success if notice[1]=="success" else st.error)(notice[2])
        if notice[1]=="success":st.toast(notice[2])

def result(a):
    return score_responses(a["responses"])

def audit_conf(rows):
    return audit_conformance(rows)

def q_conf(rows):
    return checklist_conformance(rows, rounded=False)

def auditor_bar_failures(rows, person):
    """Failed checks for one recorded auditor within the supplied selection."""
    failures=[]
    for audit in rows:
        if audit.get("auditor") != person: continue
        for response in audit.get("responses",[]):
            if str(response.get("response","")).strip().lower() != "no": continue
            failures.append({"BAR":response.get("bar_rating") or "Unrated",
                "Audit ID":audit.get("audit_id",""),"Date":audit.get("audit_date",""),
                "Site / Hub":audit.get("site",""),"Form":audit.get("form_name",""),
                "Question ref":response.get("item",""),"Failed question":response.get("question",""),
                "Evidence":response.get("comments_evidence",""),
                "Immediate safety action":response.get("immediate_action",""),
                "SMART action":response.get("smart_action",""),"Owner":response.get("action_owner",""),
                "Due date":response.get("action_due_date","")})
    order={"BAR 1":1,"BAR 2":2,"BAR 3":3}
    return sorted(failures,key=lambda row:(order.get(row["BAR"],4),row["Date"],row["Audit ID"],row["Question ref"]))

def checklist_compliance_basis(rows):
    answers=[str(item.get("response", "")).strip().lower()
             for audit in rows for item in audit.get("responses", [])]
    yes=answers.count("yes"); no=answers.count("no")
    if not yes+no:
        return "No applicable Yes/No answers · N/A excluded"
    return f"{yes} Yes / {yes+no} applicable answers ({no} No) · N/A excluded"

def checklist_nonconformance_basis(rows):
    answers=[str(item.get("response", "")).strip().lower()
             for audit in rows for item in audit.get("responses", [])]
    yes=answers.count("yes"); no=answers.count("no")
    if not yes+no:
        return "No applicable Yes/No answers · N/A excluded"
    return f"{no} No / {yes+no} applicable answers · N/A excluded"

def nonconformance_narrative(rows):
    """Plain-language CoW summary from recorded failed checks."""
    findings=[]; failed_audits=0; bars={}; counts={}
    themes={"Permit and authorisation":("permit","authoris","wcc","certificate"),
            "Hazard and risk assessment":("hazard","risk","tra","assessment"),
            "Control implementation":("control","isolation","gas test","barrier"),
            "Toolbox Talk and understanding":("toolbox","tbt","understand","personnel"),
            "Procedures and documents":("procedure","pop","document","current approved"),
            "Supervision and monitoring":("supervis","monitor","site controller","inspection")}
    for audit in rows:
        failed=[r for r in audit.get("responses",[]) if str(r.get("response","")).strip().lower()=="no"]
        if failed: failed_audits+=1
        for row in failed:
            question=str(row.get("question","")).strip()
            findings.append(question)
            bar=row.get("bar_rating") or "Unrated"; bars[bar]=bars.get(bar,0)+1
            theme=next((name for name,words in themes.items() if any(word in question.lower() for word in words)),"Other CoW checks")
            counts[theme]=counts.get(theme,0)+1
    if not findings:
        return "**What audits found:** No failed questions in this selection.\n\n**Next step:** Continue planned assurance and check that important work activities are covered. This result describes the audit sample."
    bar_text=", ".join(f"{name}: {count}" for name,count in sorted(bars.items()))
    areas=", ".join(f"{name} ({count})" for name,count in sorted(counts.items(),key=lambda item:item[1],reverse=True)[:3])
    repeated=sum(count>1 for count in __import__("collections").Counter(findings).values())
    repeat_note=f"{repeated} question(s) failed more than once." if repeated else "No question has failed more than once in this selection."
    if bars.get("BAR 1"):
        next_step="Confirm work was made safe and the required critical controls were restored. Assign an owner and due date, then verify the correction."
    else:
        next_step="Use Findings & Actions to confirm an owner and due date for each gap. Check the correction through a follow-up audit."
    return (f"**What audits found:** {len(findings)} failed question(s) across {failed_audits} audit(s). {bar_text}.\n\n"
            f"**CoW checks needing attention:** {areas}. {repeat_note}\n\n"
            f"**Next step:** {next_step}")

def permit_type(a):
    return permit_sample_category(a)

def weeks(y,m): return len(reporting_weeks(y,m))
def rag(plan,conf):
    return rag_status(plan,conf)
def css(s): return {"Green":"green","Amber":"amber","Red":"red","Needs review":"review"}.get(s,"")

def card(name,title,value,status,detail):
    badge=status.upper() if status!="Not enough data" else "NOT ASSESSED"
    st.markdown(f'<div class="kpi {css(status)}"><div class="kt">{name}</div><div class="ks">{title}</div><div class="kv">{value}</div><span class="badge {css(status)}">{badge}</span><div class="kd">{detail}</div></div>',unsafe_allow_html=True)

def dual_card(name,title,completion,compliance,status,detail):
    badge=status.upper() if status!="Not enough data" else "NOT ASSESSED"
    st.markdown(f'<div class="kpi {css(status)}"><div class="kt">{name}</div><div class="ks">{title}</div><div class="kv">{completion}</div><span class="badge {css(status)}">{badge}</span><div class="kd">{detail}<br>Whole-audit conformance {compliance}</div></div>',unsafe_allow_html=True)

def measure_card(name,title,delivery_label,delivery,performance_label,performance,status,reason,foot=""):
    badge=status.upper() if status!="Not enough data" else "NOT ASSESSED"
    esc=lambda value: html.escape(str(value))
    st.markdown(
        f'<div class="kpi {css(status)}"><div class="kt">{esc(name)}</div><div class="ks">{esc(title)}</div>'
        f'<div class="metric-pair"><div class="metric-line"><span>{esc(delivery_label)}</span><strong>{esc(delivery)}</strong></div>'
        f'<div class="metric-line"><span>{esc(performance_label)}</span><strong>{esc(performance)}</strong></div></div>'
        f'<span class="badge {css(status)}">{esc(badge)}</span><div class="rag-reason">{esc(reason)}</div>'
        f'<div class="kd">{esc(foot)}</div></div>',unsafe_allow_html=True)


def intervention(status):
    return {
        "Green": "No intervention required.",
        "Amber": "Site Leadership intervention required to identify improvements and address emerging trends.",
        "Red": "Immediate management intervention required; improvement actions to be implemented within one month.",
    }.get(status, "")

def safe_date(x):
    try:return datetime.strptime(str(x),"%Y-%m-%d").date()
    except:return None

def governance(period,site):
    c=db(); r=c.execute("SELECT * FROM governance WHERE period=? AND site=?",(period,site)).fetchone(); c.close()
    keys=["period","site","kpi2_alignment","kpi2_ind_conf","kpi2_ind_find","kpi2_self_find","kpi3_coverage","kpi4_justification","kpi4_oim_coverage","kpi4_findings","kpi4_oim_consecutive","kpi4_oim_12m"]
    return dict(zip(keys,r)) if r else {"period":period,"site":site,"kpi2_alignment":"Not assessed","kpi2_ind_conf":None,"kpi2_ind_find":0,"kpi2_self_find":0,"kpi3_coverage":"Not assessed","kpi4_justification":"Not assessed","kpi4_oim_coverage":"Not assessed","kpi4_findings":"Not assessed","kpi4_oim_consecutive":0,"kpi4_oim_12m":0}

def save_governance(values):
    c=db()
    c.execute("DELETE FROM governance WHERE period=? AND site=?",(values["period"],values["site"]))
    c.execute("INSERT INTO governance VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",tuple(values[k] for k in ["period","site","kpi2_alignment","kpi2_ind_conf","kpi2_ind_find","kpi2_self_find","kpi3_coverage","kpi4_justification","kpi4_oim_coverage","kpi4_findings","kpi4_oim_consecutive","kpi4_oim_12m"]))
    c.commit(); c.close()

def seed_demo():
    c=db(); c.execute("DELETE FROM audits WHERE audit_id LIKE 'DEMO-%'"); c.execute("DELETE FROM roles WHERE person_name LIKE 'Demo %'"); c.execute("DELETE FROM kpi5 WHERE demo=1")
    d=str(date.today()); now=datetime.now().isoformat(timespec="seconds")
    def add(aid,form,site,aud,meta,resp,summary=""):
        m={"site":site,"audit_date":d,"auditor":aud,"reference":aid,"demo":True,**meta}; c.execute("INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,now,form,d,site,aud,aid,json.dumps(m),json.dumps(resp),summary))
    yes=[{"question":"Control verified","response":"Yes","smart_action":""}]; no=[{"question":"Control not fully evidenced","response":"No","smart_action":"Review and close identified assurance gap."}]
    add("DEMO-PQ1","Control of Work: Permit Quality","Site Alpha","Demo Site Controller",{"routine":True,"new_wcc":False},yes)
    add("DEMO-PQ2","Control of Work: Permit Quality","Site Alpha","Demo Site Controller",{"routine":False,"new_wcc":True},no)
    add("DEMO-PQ3","Control of Work: Permit Quality","Site Charlie","Demo Asset Superintendent",{"routine":True,"new_wcc":False},yes)
    add("DEMO-TBT1","Control of Work: Toolbox Talk, Permit Compliance & Operating Procedures","North Remote Sites","Demo Operations Supervisor",{"activity_type":"Routine"},no)
    add("DEMO-TBT2","Control of Work: Toolbox Talk, Permit Compliance & Operating Procedures","South Remote Sites","Demo HSE Adviser",{"activity_type":"Routine"},yes)
    add("DEMO-TBT3","Control of Work: Toolbox Talk, Permit Compliance & Operating Procedures","Site Echo","Demo Site Manager",{"activity_type":"Routine"},yes)
    add("DEMO-LEAD1","Control of Work Leadership Engagement Checklist","North Remote Sites","Demo Operations Director",{},yes,"Meets CoW Standard")
    add("DEMO-LEAD2","Control of Work Leadership Engagement Checklist","South Remote Sites","Demo Operations Director",{},yes,"Meets CoW Standard")
    for x in [("permit","Demo Site Controller","Site Controller"),("permit","Demo Asset Superintendent","Asset Superintendent"),("tbt","Demo Operations Supervisor","Operations Supervisor"),("tbt","Demo HSE Adviser","HSE Adviser"),("tbt","Demo Site Manager","Site Manager"),("lead","Demo Operations Director","Operations Director")]:c.execute("INSERT OR REPLACE INTO roles VALUES(?,?,?)",x)
    c.execute("INSERT OR REPLACE INTO kpi5 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",("DEMO-KPI5",now,d[:7],"All",1,0,0,0,1,0,"Yes","No","No","Synthetic trial value",1)); c.commit(); c.close()

def recovery_actions(period, scope, kpi_filter=None):
    st.subheader("Leadership recovery actions")
    c=db(); saved=c.execute("SELECT action_id,kpi,owner_name,owner_id,action_text,due_date,status,verification_note,history FROM kpi_recovery_actions WHERE reporting_period=? AND scope=? ORDER BY due_date",(period,scope)).fetchall(); c.close()
    keys=("action_id","kpi","owner_name","owner_id","action_text","due_date","status","verification_note","history")
    records=[dict(zip(keys,row)) for row in saved if kpi_filter is None or row[1]==kpi_filter]
    if records:
        display=[]
        for row in records:
            overdue=bool(safe_date(row["due_date"]) and safe_date(row["due_date"])<date.today() and row["status"]!="Closed")
            display.append({"Action ID":row["action_id"],"KPI":row["kpi"],"Owner":row["owner_name"],"Action":row["action_text"],"Due":row["due_date"],"Status":row["status"],"Overdue":"Yes" if overdue else "No","Closure evidence":row["verification_note"],"Linked finding / target":(json.loads(row["history"] or "[]") or [{}])[-1].get("source_reference","Unlinked")})
        st.dataframe(pd.DataFrame(display),use_container_width=True,hide_index=True)
    else: st.caption("No leadership recovery actions recorded for this reporting period and scope.")
    with st.expander("Record or update a leadership recovery action"):
        selected=st.selectbox("Recovery action",["New action"]+[r["action_id"] for r in records],key=f"recovery-select-{period}-{scope}-{kpi_filter}")
        record=next((r for r in records if r["action_id"]==selected),{})
        token=f"{period}-{scope}-{selected}-{kpi_filter}"
        with st.form("recovery-form-"+token):
            kpi=st.selectbox("Recovery KPI",[kpi_filter] if kpi_filter else ["KPI 1","KPI 2","KPI 3","KPI 4","KPI 5"],index=0 if kpi_filter else int(record.get("kpi","KPI 1")[-1])-1)
            last_change=(json.loads(record.get("history") or "[]") or [{}])[-1]
            source_reference=st.text_input("Finding / missed target reference",value=last_change.get("source_reference",""),help="Enter an audit ID and question, an obligation ID, an incident ID, or the site/role/week and target missed.").strip()
            owner=st.text_input("Accountable action owner",value=record.get("owner_name",""),placeholder="Enter full name").strip()
            owner_id=record.get("owner_id","") if owner==record.get("owner_name") else ""
            action=st.text_area("Recovery action required",value=record.get("action_text",""))
            due=st.date_input("Recovery action due date",value=safe_date(record.get("due_date","")))
            states=["Open","In progress","Closed"]
            status=st.selectbox("Recovery action status",states,index=states.index(record.get("status","Open")))
            verification=st.text_area("Progress or closure evidence",value=record.get("verification_note",""))
            save=st.form_submit_button("Save recovery action")
        if save:
            if not owner or not action.strip() or not due or not source_reference: st.error("Enter a source finding/target reference, owner, action and due date.")
            elif status=="Closed" and not verification.strip(): st.error("Record closure evidence before closing the action.")
            else:
                now=datetime.now().isoformat(timespec="seconds")
                history=json.loads(record.get("history") or "[]")
                history.append({"at":now,"kpi":kpi,"owner_id":owner_id,"action":action.strip(),"due":str(due),"status":status,"note":verification.strip(),"source_reference":source_reference})
                c=db()
                if record:
                    c.execute("UPDATE kpi_recovery_actions SET kpi=?,owner_name=?,owner_id=?,action_text=?,due_date=?,status=?,verification_note=?,history=? WHERE action_id=?",(kpi,owner,owner_id,action.strip(),str(due),status,verification.strip(),json.dumps(history),record["action_id"]))
                else:
                    c.execute("INSERT INTO kpi_recovery_actions VALUES(?,?,?,?,?,?,?,?,?,?,?)",("REC-"+uuid.uuid4().hex[:8].upper(),period,scope,kpi,owner,owner_id,action.strip(),str(due),status,verification.strip(),json.dumps(history)))
                c.commit(); c.close(); st.rerun()
    st.caption("Recovery actions are entered explicitly; KPI colours do not create actions automatically. Closure evidence is recorded here and requires the responsible leadership review.")


def dashboard():
    st.markdown(f'<div class="dash"><div class="brand-row"><strong style="font-size:25px">PDi | VERIFY</strong><div class="eyebrow">PDi DEMO | OPERATIONAL ASSURANCE</div></div><h1>Control of Work KPI Dashboard</h1><p>Client demonstration · fictional assurance data</p></div>',unsafe_allow_html=True)
    global DB, DATABASE_URL, _SCHEMA_READY
    demo_mode=True
    all_a=[a for a in audits() if not a["audit_id"].startswith("DEMO-") and not a["metadata"].get("demo") and not a["metadata"].get("uat_sample")]
    with st.container(border=True):
        c1,c2,c3=st.columns([1,1,1.3])
        current_month=date.today().replace(day=1)
        known_months={safe_date(a["audit_date"]).replace(day=1) for a in all_a if safe_date(a["audit_date"])}|{current_month}
        cursor=current_month
        for _ in range(24):
            known_months.add(cursor)
            cursor=date(cursor.year-1,12,1) if cursor.month==1 else date(cursor.year,cursor.month-1,1)
        ordered_months=sorted(known_months,reverse=True)
        initial_month=date(2026,9,1) if demo_mode else current_month
        md=c1.selectbox("REPORTING MONTH",ordered_months,index=ordered_months.index(initial_month),format_func=lambda d:d.strftime("%B %Y"))
        asset=c2.selectbox("ASSET",["All","North","South"])
        asset_sites={"North":{"Site Alpha","Site Bravo","Site Charlie","North Remote Sites"},"South":{"Site Delta","Site Echo","South Remote Sites"}}
        y,m=md.year,md.month; period=md.strftime("%Y-%m"); month=[a for a in all_a if safe_date(a["audit_date"]) and reporting_weeks(y,m)[0]<=safe_date(a["audit_date"])<=date(y,m,calendar.monthrange(y,m)[1])]
        sites=sorted(set(ASSET_GROUPS)|{a["site"] for a in month if a["site"]})
        if asset!="All": sites=[x for x in sites if x in asset_sites[asset]]
        site=c3.selectbox("SITE / HUB",["All assets and teams"]+sites,key=f"site-filter-{asset}")
    if asset!="All":
        all_a=[a for a in all_a if a["site"] in asset_sites[asset]]
        month=[a for a in month if a["site"] in asset_sites[asset]]
    site="All" if site=="All assets and teams" else site
    st.markdown(f'<div class="selection">{md.strftime("%B %Y")} &nbsp;·&nbsp; {html.escape("All assets and teams" if site=="All" else site)} &nbsp;·&nbsp; Monthly review</div>',unsafe_allow_html=True)
    selected_groups={g:v for g,v in SITE_GROUPS.items() if asset=="All" or g in asset_sites[asset]}
    headline_area=st.empty()
    headline_area.caption("Loading KPI evidence…")
    view=month if site=="All" else [a for a in month if a["site"]==site]
    permit=[a for a in view if a["form_name"]=="Control of Work: Permit Quality"]; tbt=[a for a in view if "Toolbox Talk" in a["form_name"]]; lead=[a for a in view if "Leadership Engagement" in a["form_name"]]
    q=(m-1)//3+1; qstart=date(y,(q-1)*3+1,1); qe=(q-1)*3+3; qend=date(y,qe,calendar.monthrange(y,qe)[1]); report_end=date(y,m,calendar.monthrange(y,m)[1])
    quarter_lead=[a for a in all_a if "Leadership Engagement" in a["form_name"] and safe_date(a["audit_date"]) and qstart<=safe_date(a["audit_date"])<=report_end and (site=="All" or a["site"]==site)]
    quarter_tbt=[a for a in all_a if "Toolbox Talk" in a["form_name"] and safe_date(a["audit_date"]) and qstart<=safe_date(a["audit_date"])<=report_end and (site=="All" or a["site"]==site)]
    maps=role_maps(); pmap,tmap,lmap=maps["permit"],maps["tbt"],maps["lead"]
    with st.sidebar.expander("KPI role configuration"):
        specs=[("permit",[a for a in permit if not a["metadata"].get("auditor_role")],["Site Controller","Asset Superintendent","Other"],pmap),("tbt",[a for a in quarter_tbt if not a["metadata"].get("auditor_role")],["Operations Supervisor","HSE Adviser","Site Manager","Other"],tmap),("lead",quarter_lead,["Operations Director","Deputy Operations Director","Asset Superintendent","Ops Support Manager","Other"],lmap)]
        for kind,rows,opts,current_map in specs:
            for n in sorted({a["auditor"] for a in rows if a["auditor"]}):
                cur=current_map.get(n,"Other"); val=st.selectbox(n,opts,index=opts.index(cur) if cur in opts else len(opts)-1,key=f"r-{kind}-{n}")
                if val!=cur:
                    set_role(kind,n,val)
                    current_map[n]=val
        st.caption("Verify mappings for historic records. New Permit Quality and TBT/Permit/POP submissions store the selected auditor role with each audit.")
    gov=governance(period,site); w=weeks(y,m)
    with st.sidebar.expander("KPI source and coverage checks"):
        st.caption("Confirm these qualitative checks against Permit Register, Visit Register and the site audit plan before using the RAG results for formal reporting.")
        a,b,c=st.columns(3)
        k2_options=["Not assessed","Aligned and nine-group rotation confirmed","Synthetic UAT alignment (unverified)","Significant gap / coverage shortfall"]
        alignment=a.selectbox("KPI 2 · Independent comparison and rotation",k2_options,index=k2_options.index(gov["kpi2_alignment"]) if gov["kpi2_alignment"] in k2_options else 0,key=f"gov-kpi2-{period}-{site}")
        coverage3=b.selectbox("KPI 3 · Remote Site team coverage (Visit Register checked)",["Not assessed","Reasonable","Imbalanced"],index=["Not assessed","Reasonable","Imbalanced"].index(gov["kpi3_coverage"]) if gov["kpi3_coverage"] in ["Not assessed","Reasonable","Imbalanced"] else 0,key=f"gov-kpi3-{period}-{site}")
        oim_options=["Not assessed","Reasonable","Limited","Reasonable · late","Limited · late"]
        coverage4=c.selectbox("KPI 4 · Site Manager Remote Site coverage and visit timing (Visit Register checked)",oim_options,index=oim_options.index(gov["kpi4_oim_coverage"]) if gov["kpi4_oim_coverage"] in oim_options else 0,key=f"gov-kpi4cov-{period}-{site}")
        c.caption("Select a late option if the Site Manager visit occurred outside its planned quarter. Only visits through the selected month are counted.")
        a,b,c=st.columns(3)
        a.caption("A missed visit target requires a Suitable justification. Not required is valid only when every visit target is met.")
        justification=a.selectbox("KPI 4 · Missed visit justification",["Not assessed","Not required","Suitable","Missing / unsuitable"],index=["Not assessed","Not required","Suitable","Missing / unsuitable"].index(gov["kpi4_justification"]) if gov["kpi4_justification"] in ["Not assessed","Not required","Suitable","Missing / unsuitable"] else 0,key=f"gov-kpi4just-{period}-{site}")
        findings=b.selectbox("KPI 4 · Findings",["Not assessed","None","Isolated minor","Recurring minor","Significant / repeat","Controls ineffective"],index=["Not assessed","None","Isolated minor","Recurring minor","Significant / repeat","Controls ineffective"].index(gov["kpi4_findings"]) if gov["kpi4_findings"] in ["Not assessed","None","Isolated minor","Recurring minor","Significant / repeat","Controls ineffective"] else 0,key=f"gov-kpi4find-{period}-{site}")
        missed_two=c.checkbox("Site Manager missed two consecutive quarters",value=bool(gov["kpi4_oim_consecutive"]),key=f"gov-oim2-{period}-{site}")
        missed_rolling=st.checkbox("Site Manager missed more than two quarters in rolling 12 months",value=bool(gov["kpi4_oim_12m"]),key=f"gov-oim12-{period}-{site}")
        if st.button("Save KPI source checks",key=f"gov-save-{period}-{site}"):
            gov.update(kpi2_alignment=alignment,kpi3_coverage=coverage3,kpi4_oim_coverage=coverage4,kpi4_justification=justification,kpi4_findings=findings,kpi4_oim_consecutive=int(missed_two),kpi4_oim_12m=int(missed_rolling))
            save_governance(gov); st.success("KPI checks saved.")
    with st.sidebar.expander("KPI 4 · Visit Register Remote Site visit evidence"):
        st.caption("Record one Visit Register visit per actual offshore visit. TBT/Permit/POP audits are monitoring evidence; several audits may belong to one visit. Use the Visit Register reference to prevent duplicates.")
        with st.form("visit_register_visit_entry",clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            vdate=c1.date_input("Visit date",date.today(),key="visit_register-date")
            vrole=c2.selectbox("Visitor role",["Operations Supervisor","HSE Adviser","Site Manager"],key="visit_register-role")
            vsite=c3.selectbox("Remote Site group",["North Remote Sites","South Remote Sites"],key="visit_register-site")
            c1,c2=st.columns(2)
            vteam=c1.text_input("Remote Site team / installation",key="visit_register-team")
            vref=c2.text_input("Visit Register visit reference",key="visit_register-reference")
            add_visit=st.form_submit_button("Record verified visit")
        if add_visit:
            if not vref.strip() or not vteam.strip():st.error("Enter the Remote Site team and Visit Register visit reference.")
            else:
                c=db(); duplicate=c.execute("SELECT visit_id FROM kpi4_visits WHERE source_reference=?",(vref.strip(),)).fetchone()
                if duplicate:st.error("This Visit Register reference has already been recorded.")
                else:
                    c.execute("INSERT INTO kpi4_visits VALUES(?,?,?,?,?,?,?)",("VIS-"+uuid.uuid4().hex[:8].upper(),str(vdate),vrole,vsite,vteam.strip(),vref.strip(),datetime.now().isoformat(timespec="seconds")))
                    c.commit(); st.success("Visit Register visit recorded.")
                c.close()
        visit_rows=visit_register_visits()
        shown_visits=[v for v in visit_rows if safe_date(v["visit_date"]) and safe_date(v["visit_date"]).year==y and safe_date(v["visit_date"]).month==m and (site=="All" or v["site"]==site)]
        if shown_visits:
            st.dataframe(pd.DataFrame(shown_visits),use_container_width=True,hide_index=True)
            remove_id=st.selectbox("Correct a visit record",["Select..."]+[v["visit_id"] for v in shown_visits],key=f"visit-remove-{period}-{site}")
            if st.button("Remove selected visit",key=f"visit-remove-button-{period}-{site}") and remove_id!="Select...":
                c=db(); c.execute("DELETE FROM kpi4_visits WHERE visit_id=?",(remove_id,)); c.commit(); c.close(); st.rerun()
    sc=[a for a in permit if a["site"] in SITE_GROUPS and permit_auditor_role(a,pmap)=="Site Controller"]
    asc=[a for a in permit if a["site"] in SITE_GROUPS and permit_auditor_role(a,pmap)=="Asset Superintendent"]
    sc_samples=[a for a in sc if permit_type(a)!="Unclassified"]
    as_samples=[a for a in asc if permit_type(a)!="Unclassified"]
    routine_weekly,nonroutine_weekly=(tuple(map(sum,zip(*selected_groups.values()))) if site=="All" else SITE_GROUPS.get(site,(0,0)))
    k1routine_plan,k1nonroutine_plan=routine_weekly*w,nonroutine_weekly*w
    k1routine=sum(permit_type(a)=="Routine" for a in sc); k1nonroutine=sum(permit_type(a)=="Non-routine" for a in sc)
    k1plan=k1routine_plan+k1nonroutine_plan or None; k1done=k1routine+k1nonroutine; k1p=completion_percentage(k1done,k1plan) if k1done else None; k1c=audit_conformance(sc_samples,rounded=False); k1s=rag(k1p,k1c) if sc_samples else "Not enough data"
    k1_scored=[a for a in sc_samples if any(str(r.get("response","")).lower() in {"yes","no"} for r in a["responses"])]
    k1_passed=sum(not any(str(r.get("response","")).lower()=="no" for r in a["responses"]) for a in k1_scored)
    if k1s=="Green" and (k1routine<k1routine_plan or k1nonroutine<k1nonroutine_plan):k1s="Needs review"
    weekly_samples=[]
    for group,(routine_target,new_target) in selected_groups.items():
        if site not in ("All",group):continue
        for classification,target in (("Routine",routine_target),("Non-routine",new_target)):
            weekly_samples.append(weekly_coverage(sc_samples,y,m,target,lambda a,g=group,t=classification:a["site"]==g and permit_type(a)==t))
    k1weekly=sum(met for met,_ in weekly_samples); k1weekly_plan=sum(planned for _,planned in weekly_samples)
    if k1s=="Green" and k1weekly<k1weekly_plan:k1s="Needs review"
    k2plan=w if site=="All" else None; k2done=len(as_samples); k2p=completion_percentage(k2done,k2plan) if k2done else None; k2c=audit_conformance(as_samples,rounded=False); k2s=rag(k2p,k2c) if as_samples else "Not enough data"; k2groups={a["metadata"].get("assurance_group") for a in as_samples if a["metadata"].get("assurance_group") in AS_ASSURANCE_GROUPS}; k2cov=len(k2groups)
    k2weekly,k2weekly_plan=weekly_coverage(as_samples,y,m,1)
    k2_alignment_ok=(gov["kpi2_alignment"]=="Aligned and nine-group rotation confirmed" or (gov["kpi2_alignment"]=="Synthetic UAT alignment (unverified)" and period=="2026-09" and all(a["metadata"].get("uat_sample") for a in as_samples+sc_samples)))
    if k2s=="Green" and (not k2_alignment_ok or k2weekly<k2weekly_plan):k2s="Needs review"
    k3_breakdown=leadership_kpi_breakdown(quarter_lead,lmap,{"North Remote Sites","South Remote Sites"})
    qlead=k3_breakdown["eligible"]; k3n=len(qlead); k3c=audit_conformance(qlead,rounded=False); complete=(m==qe and date.today()>qend)
    k3scored=[a for a in qlead if any(str(r.get("response","")).lower() in {"yes","no"} for r in a["responses"])]
    k3passed=sum(not any(str(r.get("response","")).lower()=="no" for r in a["responses"]) for a in k3scored)
    k3failed=len(k3scored)-k3passed
    k3s=leadership_status(k3n,k3c,gov["kpi3_coverage"],complete) if site=="All" else "Not enough data"
    k3month=[a for a in qlead if safe_date(a["audit_date"]).month==m]
    k3_month_rows=[]
    for k3_m in range(qstart.month,qe+1):
        label=date(y,k3_m,1).strftime("%B %Y")
        if k3_m>m:
            k3_month_rows.append({"Month":label,"Leadership CoW Engagements Remote Site completed per month":"—","Completed in Quarter":"—","Control of Work Conformance":"—","No. of Teams Engaged with":"—"})
            continue
        monthly=[a for a in qlead if safe_date(a["audit_date"]).month==k3_m]
        cumulative=sum(safe_date(a["audit_date"]).month<=k3_m for a in qlead)
        teams={a["metadata"].get("nui_team","").strip() for a in monthly if a["metadata"].get("nui_team","").strip()}
        monthly_conf=audit_conformance(monthly,rounded=False)
        k3_month_rows.append({"Month":label,"Leadership CoW Engagements Remote Site completed per month":len(monthly),"Completed in Quarter":f"{cumulative}/3","Control of Work Conformance":format_percentage(monthly_conf) if monthly_conf is not None else "—","No. of Teams Engaged with":len(teams)})
    nui_sites={"North Remote Sites","South Remote Sites"}
    visit_roles={"Operations Supervisor","HSE Adviser","Site Manager"}
    mapped=[a for a in tbt if a["site"] in nui_sites and tbt_auditor_role(a,tmap) in visit_roles]  # Only Remote Site monitoring contributes.
    month_visits=[v for v in visit_rows if safe_date(v["visit_date"]) and safe_date(v["visit_date"]).year==y and safe_date(v["visit_date"]).month==m and (site=="All" or v["site"]==site)]
    quarter_visits=[v for v in reporting_period_rows(visit_rows,"visit_date",qstart,report_end) if site=="All" or v["site"]==site]
    counts={r:sum(v["role"]==r for v in month_visits) for r in visit_roles}
    k4scored=[a for a in mapped if any(str(r.get("response","")).lower() in {"yes","no"} for r in a["responses"])]
    k4passed=sum(not any(str(r.get("response","")).lower()=="no" for r in a["responses"]) for a in k4scored)
    k4raw=100*k4passed/len(k4scored) if k4scored else None
    k4c=round(k4raw,1) if k4raw is not None else None
    visit_week_rows=mapped  # Weekly coverage from submitted monitoring audits
    ooweek,oo_plan=weekly_coverage(visit_week_rows,y,m,1,lambda a:tbt_auditor_role(a,tmap)=="Operations Supervisor")
    medweek,med_plan=weekly_coverage(visit_week_rows,y,m,1,lambda a:tbt_auditor_role(a,tmap)=="HSE Adviser")
    oo=completion_percentage(ooweek,oo_plan); med=completion_percentage(medweek,med_plan)
    oim_quarter=sum(tbt_auditor_role(a,tmap)=="Site Manager" for a in quarter_tbt)
    k4s=presentation_visit_status(oo if mapped else None,med if mapped else None,k4raw) if site=="All" else "Not enough data"
    c=db(); k5rows=c.execute("SELECT * FROM kpi5 WHERE reporting_month=? AND site=? AND demo=0 ORDER BY submitted_at",(period,"All")).fetchall(); c.close(); k5rows=[r for r in k5rows if "SYNTHETIC UAT" not in (r[13] or "").upper()]; k5=k5rows[-1] if k5rows else None
    k5_synthetic=bool(k5 and "SYNTHETIC UAT" in (k5[13] or "").upper())
    if not k5:k5s="Not enough data"; k5v="—"; k5detail="Enter company-wide Incident Register summary"
    else:
        current,prev,hipo,inj,loc,major,repeat,recurring,sig=k5[4],k5[5],k5[6],k5[7],k5[8],k5[9],k5[10],k5[11],k5[12]
        k5s="Red" if sig=="Yes" or hipo>=2 or inj>=2 or major>=1 or recurring=="Yes" else ("Amber" if current>prev or hipo==1 or inj==1 or loc>=1 or repeat=="Yes" else "Green")
        if not (k5[13] or "").strip() and k5s!="Red":k5s="Needs review"
        k5v=str(current); k5detail=f"Previous {prev} · HiPO {hipo} · MTC+ {inj} · LOC {loc}"+("<br>Incident Register source note missing; result needs validation." if not (k5[13] or "").strip() else "")
    from monthly_report import build as build_monthly_report
    report_groups={g:v for g,v in selected_groups.items() if site=="All" or g==site}
    report_source=all_a if site=="All" else [a for a in all_a if a["site"]==site]
    monthly_report=build_monthly_report(report_source,y,m,report_groups,maps,gov["kpi3_coverage"])
    if k5 and not (k5[13] or "").strip(): monthly_report["issues"].append("KPI 5 Incident Register source note missing; result needs validation. Any Red incident trigger remains visible.")
    if demo_mode: monthly_report["issues"].insert(0,"DEMO ONLY: this report contains generated mock audits, incidents, visits and actions from the isolated KPI-check dataset. It is not an operational assurance report.")
    # illustrative demo criteria: verified visits and qualitative safeguards govern KPI 4.
    verified=[dict(audit_date=v["visit_date"],role=v["role"]) for v in visit_rows]
    verified_oo,verified_plan=weekly_coverage(verified,y,m,1,lambda v:v["role"]=="Operations Supervisor")
    verified_med,_=weekly_coverage(verified,y,m,1,lambda v:v["role"]=="HSE Adviser")
    verified_oim=sum(v["role"]=="Site Manager" for v in quarter_visits)
    verified_status=site_visit_status(100*verified_oo/verified_plan,100*verified_med/verified_plan,monthly_report["conformances"][3],verified_oim,bool(gov["kpi4_oim_consecutive"]),bool(gov["kpi4_oim_12m"]),gov["kpi4_oim_coverage"],gov["kpi4_findings"],gov["kpi4_justification"])
    if not month_visits and verified_status not in ("Red",):verified_status="Needs review"
    monthly_report["statuses"][3]=verified_status
    monthly_report["kpis"][3].update(Status=verified_status,Delivery=f"Verified visit weeks: Supervisor {verified_oo}/{verified_plan}; HSE Adviser {verified_med}/{verified_plan}; Site Manager {verified_oim}/1 quarter")
    monthly_report["issues"].append("KPI 4 uses recorded Visit Register visits plus saved Site Manager coverage, findings and justification reviews. Audit-week counts are supporting evidence only. Sample targets are illustrative and require client agreement.")
    # Demo KPI 3 Amber includes isolated non-conformances and recurring minor themes.
    if any(str(r.get("response","")).lower()=="no" for a in monthly_report["datasets"][2] for r in a["responses"]) and monthly_report["statuses"][2]=="Green":
        monthly_report["statuses"][2]="Amber";monthly_report["kpis"][2]["Status"]="Amber"
        monthly_report["issues"].append("KPI 3 has recorded non-conformances: the illustrative demo criteria's qualitative Amber qualification applies even where numerical conformance is at least 90%.")
    k1done=monthly_report["credits"];k1plan=monthly_report["plan"];k1p=100*k1done/k1plan if k1plan else None
    k2done=monthly_report["ascredits"];k2p=100*k2done/w
    k1c,k2c,k3c,k4raw=monthly_report["conformances"]
    k4c=round(k4raw,1) if k4raw is not None else None
    k1s,k2s,k3s,k4s=monthly_report["statuses"]
    ooweek=monthly_report["oo"];medweek=monthly_report["med"]
    if site!="All" or asset!="All":
        k2s=k3s=k4s="Needs review"
        monthly_report["issues"].append("KPI 2–4 targets are company-wide; regional/site target allocations are not configured.")
        for i in (1,2,3): monthly_report["kpis"][i]["Status"]="Needs review"
    if asset!="All":
        k2s=k3s=k4s="Needs review"  # Regional obligations await agreed allocation.
    statuses=[k1s,k2s,k3s,k4s,k5s]; assessed=[x for x in statuses if x in ("Green","Amber","Red")]
    overall=("Red" if "Red" in assessed else ("Amber" if "Amber" in assessed else "Green")) if len(assessed)==5 else "Not enough data"
    kpi_names=["KPI 1","KPI 2","KPI 3","KPI 4","KPI 5"]; adverse=[kpi_names[i] for i,x in enumerate(statuses) if x=="Red"]
    negative=[r for a in permit+tbt+lead for r in a["responses"] if str(r.get("response","")).lower()=="no"]; action_findings=negative
    bar1=sum((r.get("bar_rating") or "")=="BAR 1" for r in negative); action_recorded=sum(bool((r.get("smart_action") or "").strip()) for r in action_findings)
    unclassified=sum(permit_type(a)=="Unclassified" for a in permit); missing_core=sum(not a.get("site") or not a.get("auditor") for a in view); quality_issues=unclassified+missing_core+max(0,len(action_findings)-action_recorded)
    sample_count=sum(bool(a["metadata"].get("uat_sample")) for a in view)
    with headline_area.container():
        position=overall.upper() if len(assessed)==5 else "DATA PENDING"
        summary_label="CONTROL OF WORK OVERVIEW"
        focus="<br>".join(label+": "+", ".join(kpi_names[i] for i,x in enumerate(statuses) if x==status) for label,status in (("RED","Red"),("AMBER","Amber")) if status in statuses)
        st.markdown(f'<div class="summary"><div class="summary-main"><span class="summary-label">{summary_label}</span><strong class="summary-value">{position}</strong><span class="summary-sub">{md.strftime("%B %Y")}<br>{focus}</span></div><div class="summary-stat"><span class="summary-label">Audits Completed</span><strong class="summary-value">{len(view)}</strong><span class="summary-sub">Selected month and asset</span></div><div class="summary-stat"><span class="summary-label">Question conformance</span><strong class="summary-value">{format_percentage(q_conf(permit+tbt+lead)) if q_conf(permit+tbt+lead) is not None else "—"}</strong><span class="summary-sub">Yes of scored responses</span></div><div class="summary-stat"><span class="summary-label">Failed BAR 1 questions</span><strong class="summary-value" style="color:#bd3d43">{bar1}</strong><span class="summary-sub">Critical control verification</span></div><div class="summary-stat"><span class="summary-label">SMART actions recorded</span><strong class="summary-value">{action_recorded}/{len(action_findings)}</strong><span class="summary-sub">For No responses</span></div></div>',unsafe_allow_html=True)
        if sample_count or k5_synthetic: st.caption("Test data included — results are provisional.")
        else: st.caption("DEMO ONLY — illustrative results from generated records.")
        if quality_issues:
            with st.expander(f"Data quality checks · {quality_issues} items to review"):
                st.write(f"{unclassified} permit audits need a verified routine/non-routine category; {missing_core} records lack a site or auditor; {max(0,len(action_findings)-action_recorded)} No responses have no recorded SMART action. Review the records and evidence in Findings & Actions.")
        st.markdown('<div class="section-head">CoW KPI Results</div>',unsafe_allow_html=True)
        cols=st.columns(5)
        unassigned=[a for a in permit if permit_auditor_role(a,pmap) not in ("Site Controller","Asset Superintendent")]
        outside_groups=[a for a in permit if a["site"] not in SITE_GROUPS]
        k1detail=(f"**Completed:** {k1done}/{k1plan or '—'} across {w} reporting weeks  <br>"
                  f"**Permit samples:** Non-routine {k1nonroutine}/{k1nonroutine_plan} · Routine {k1routine}/{k1routine_plan}  <br>"
                  f"**Weekly site/category targets met:** {k1weekly}/{k1weekly_plan}; each site and permit category is checked in each reporting week  <br>"
                  f"**Site Controller audits in KPI 1:** {k1done} classified samples across the seven site groups  <br>"
                  f"**Target:** 16 per week across the seven SC groups  <br>"
                  f"**Conformance:** {k1_passed}/{len(k1_scored)} scored permits have no No answer; all-N/A permits are excluded from this percentage.  <br>"
                  f"**Required response:** {intervention(k1s)}")
        with cols[0]:
            k1_red=[label for flag,label in ((k1p is not None and k1p<70,"Sample delivery below 70%"),(k1c is not None and k1c<70,"Whole-permit conformance below 70%")) if flag]
            k1_reason=("; ".join(k1_red) or "Red criterion triggered") if k1s=="Red" else ("Monthly and weekly targets met" if k1s=="Green" else "Weekly site/category coverage needs review" if k1s=="Needs review" else "Delivery or conformance below Green threshold" if k1s=="Amber" else "Eligible samples needed")
            measure_card("KPI 1","Site Controller – Permit Quality","Weekly/category credits / plan",f"{k1done}/{k1plan or '—'} ({format_percentage(k1p)})" if k1p is not None else f"{k1done}/{k1plan or '—'}","Whole-permit conformance (SC)",format_percentage(k1c) if k1c is not None else "—",k1s,k1_reason,f"{k1_passed}/{len(k1_scored)} scored permits fully conformant · {len(sc_samples)} Site Controller samples recorded; {k1done} credited · {k1weekly}/{k1weekly_plan} weekly site/category targets met")
            with st.expander("KPI Targets & Tolerances"):
                st.markdown("**Measure and target**\nSite Controllers sample permits before issue. Routine and non-routine samples are reported separately. A permit that fails any checklist item is non-conformant for reporting.\n\n| Site | Routine per week | Non-routine per week |\n|---|---:|---:|\n| Site Alpha | 1 | 1 |\n| Site Bravo | 1 | 1 |\n| Site Charlie | 1 | 1 |\n| North Remote Sites | 2 | 1 |\n| Site Delta | 1 | 1 |\n| Site Echo | 1 | 1 |\n| South Remote Sites | 2 | 1 |\n\n**Green:** 100% or greater of planned audits completed **AND** 90% or greater audit conformance. No intervention required.\n\n**Amber:** 70% to below 100% of planned audits completed **AND/OR** 70–89% audit conformance. Site Leadership intervention to identify improvement opportunities and address emerging trends.\n\n**Red:** Less than 70% of planned audits completed **AND/OR** less than 70% audit conformance. Immediate management intervention, with improvement actions implemented within one month.")
        with cols[1]:
            k2_red=[label for flag,label in ((k2p is not None and k2p<70,"Sample delivery below 70%"),(k2c is not None and k2c<70,"Whole-permit conformance below 70%")) if flag]
            k2_reason=("; ".join(k2_red) or "Red criterion triggered") if k2s=="Red" else (("UAT thresholds met; source validation pending" if gov["kpi2_alignment"]=="Synthetic UAT alignment (unverified)" else "Delivery, conformance and source checks met") if k2s=="Green" else "Weekly rotation or comparison needs validation" if k2s=="Needs review" else f"Whole-permit conformance {format_percentage(k2c)}" if k2s=="Amber" and k2c is not None and k2c<90 else "Delivery below Green threshold" if k2s=="Amber" else "Eligible samples needed")
            measure_card("KPI 2","Asset Superintendent – Permit Quality","Reporting weeks met / plan",f"{k2done}/{k2plan or '—'} ({format_percentage(k2p)})" if k2p is not None else f"{k2done}/{k2plan or '—'}","Whole-permit conformance (AS)",format_percentage(k2c) if k2c is not None else "—",k2s,k2_reason,f"{len(as_samples)} AS audits; {k2done} credited weeks · {k2weekly}/{k2weekly_plan} weeks · {k2cov}/9 rotation groups seen")
            with st.expander("KPI Targets & Tolerances"):
                st.markdown("**Measure and target**\nAsset Superintendents complete a minimum of **one permit-quality audit per week**, rotating across Site Charlie, Site Bravo, North Mobile Team, North Support Team, Site Alpha, Site Echo, South Mobile Team, South Support Team and Site Delta. Routine and non-routine samples are reported separately. A permit that fails any checklist item is non-conformant.\n\nReview site self-verification against independent assurance findings to identify differences in the detection of non-conformances and improvement opportunities. Findings are shared with the Site Controller during the regular assurance review, attended by the QSHE Manager and Operations Director.\n\n**Green:** 100% or greater of planned audits completed **AND** 90% or greater audit conformance. No intervention required.\n\n**Amber:** 70% to below 100% of planned audits completed **AND/OR** 70–89% audit conformance. Operations Director intervention to identify improvement opportunities and address emerging trends.\n\n**Red:** Less than 70% of planned audits completed **AND/OR** less than 70% audit conformance. Immediate Operations Director intervention, with improvement actions implemented within one month.")
        with cols[2]:
            exclusions=[]
            if k3_breakdown["outside_nui"]:exclusions.append(f"{len(k3_breakdown['outside_nui'])} outside Remote Site scope")
            if k3_breakdown["role_unconfirmed"]:exclusions.append(f"{len(k3_breakdown['role_unconfirmed'])} role unconfirmed")
            if k3_breakdown["other_role"]:exclusions.append(f"{len(k3_breakdown['other_role'])} other role")
            if k3_breakdown["uat_excluded"]:exclusions.append(f"{len(k3_breakdown['uat_excluded'])} other synthetic form tests")
            k3detail=f"Q{q} · {len(quarter_lead)} leadership audit{'s' if len(quarter_lead)!=1 else ''} recorded; {k3n} KPI eligible Remote Site engagement{'s' if k3n!=1 else ''}<br>Engagement conformance {format_percentage(k3c) if k3c is not None else '—'} · {k3passed} meet standard / {k3failed} do not meet · {k3n-len(k3scored)} without scored answers"
            if exclusions:k3detail+="<br>Not counted in KPI 3: "+" · ".join(exclusions)
            k3_amber=[label for flag,label in ((k3n==2,"Two engagements"),(k3c is not None and 70<=k3c<90,"Engagement conformance below 90%"),(gov["kpi3_coverage"]=="Imbalanced","Remote Site team coverage imbalanced")) if flag]
            k3_reason=("; ".join(k3_amber) or "Quarter criteria partly met") if k3s=="Amber" else ("Engagement conformance below 70% or quarterly delivery below target" if k3s=="Red" else "Engagement, checklist and coverage criteria met" if k3s=="Green" else "Quarter coverage or source check needs review" if k3s=="Needs review" else "Company-wide quarter rating only" if site!="All" else "Quarter still in progress")
            measure_card("KPI 3","Leadership CoW Engagements – Remote Site","Quarter-to-date engagements / quarterly target",f"{k3n}/3 ({round(100*k3n/3)}%)" if site=="All" else str(k3n),"Engagement conformance (%)",format_percentage(k3c) if k3c is not None else "—",k3s,k3_reason,f"{len(k3month)} this month · {k3passed} meet / {k3failed} do not meet · Remote Site coverage {gov['kpi3_coverage']}")
            with st.expander("KPI Targets & Tolerances"):
                st.markdown("**Measure and target**\nA minimum of **three Remote Site team engagements per quarter, collectively** across the Operations Director, Deputy Operations Director, the asset assurance and operations support roles. Record the engagement count and Control of Work Leadership Engagement Checklist compliance result. Visit evidence is sourced from Visit Register.\n\nCoverage includes the fictional mobile and remote-site teams. Record an Intervention Team engagement as a single entry; include Head Office-based personnel under Office Engagements; record individual team engagements on multi-team Support visits. Quayside engagements can be included. These engagements may count towards existing Management Site Visit expectations.\n\n**Green:** Three or more visits per quarter collectively **AND** 90–100% checklist compliance, with reasonable coverage across Remote Site teams. No intervention required.\n\n**Amber:** Two visits per quarter collectively **AND/OR** 70–89% checklist compliance, isolated non-conformances, or recurring minor themes requiring attention. Site visitation demonstrates over or under coverage across Remote Site locations. Operations Director review of leadership visibility, asset coverage and engagement, and/or improvement opportunities and emerging trends.\n\n**Red:** One or fewer visits per quarter collectively **AND/OR** less than 70% checklist compliance. Immediate General Manager intervention to agree and implement a recovery plan within one month.")
        with cols[3]:
            k4_pending_nui=sum(a["site"] not in nui_sites for a in mapped)
            k4_unconfirmed=sum(tbt_auditor_role(a,tmap)=="Unconfirmed" for a in tbt)
            k4_other=len(tbt)-len(mapped)-k4_unconfirmed
            k4_reasons=[f"{k4_unconfirmed} visitor role unconfirmed" if k4_unconfirmed else "",f"{k4_other} other role" if k4_other else ""]
            k4_detail=f"Submitted-audit weeks Supervisor {ooweek}/{oo_plan} · HSE Adviser {medweek}/{med_plan} · Site Manager {oim_quarter} submitted audits this quarter; minimum 1 visit required (provisional evidence)<br>Site Manager timing and Remote Site coverage: {html.escape(gov['kpi4_oim_coverage'])}<br>Level 4 audit conformance {format_percentage(k4raw)} · {k4passed}/{len(k4scored)} scored audits fully conformant<br>{len(mapped)} provisional KPI 4 audits counted; {len(tbt)} TBT/Permit/POP audits recorded; {len(mapped)} role-eligible audit{'s' if len(mapped)!=1 else ''}."
            if med is not None and med<50:k4_detail+="<br>HSE Adviser visit delivery below 50% is Red under the provisional dashboard band."
            if k4_pending_nui:k4_detail+=f"<br>Remote Site eligibility pending: Demo administrator must verify {k4_pending_nui} counted audit(s) recorded outside the Remote Site groups."
            if any(k4_reasons):k4_detail+="<br>Not counted: "+" · ".join(reason for reason in k4_reasons if reason)
            k4_reason="Visit, conformance or qualitative Red criterion triggered" if k4s=="Red" else "100% role coverage and at least 90% conformance" if k4s=="Green" else "Role coverage or conformance below Green threshold" if k4s=="Amber" else "Eligible Remote Site monitoring evidence needed"
            measure_card("KPI 4","Site Leadership – Permit compliance Remote Site","Verified Remote Site visit coverage",f"Supervisor {verified_oo}/{verified_plan} weeks · HSE Adviser {verified_med}/{verified_plan} weeks · Site Manager {verified_oim}/1 quarter","Level 4 audit conformance (%)",format_percentage(k4raw),k4s,k4_reason,f"{k4passed}/{len(k4scored)} scored audits conformant · verify actual visits in KPI 4 detail")
            with st.expander("KPI Targets & Tolerances"):
                st.markdown("**Measure and target**\nRecord Remote Site visits by month and role, and Level 4 TBT/Compliance Monitoring outputs. Use Permit Register permit samples and Visit Register visit records; report routine and non-routine samples separately.\n\n- **Operations Supervisor:** minimum one visit per week.\n- **HSE Adviser:** minimum one visit per week.\n- **Site Manager:** minimum one visit per quarter.\n- **Target:** 100% or greater of planned audits completed **AND** 90% or greater audit conformance.\n\n**Green**\n- Supervisor and HSE Adviser: 100% or more expected Remote Site visits achieved each week during the month.\n- Site Manager: quarterly visit target achieved, with reasonable coverage across Remote Sites.\n- **AND** Level 4 monitoring demonstrates at least 90% compliance, with no repeat or significant non-conformances.\n- No intervention required.\n\n**Amber**\n- Supervisor: 50–99% of expected Remote Site visits during the month.\n- HSE Adviser: 50–99% of expected Remote Site visits during the month.\n- Site Manager: visit outside the planned quarter, or limited asset coverage.\n- **AND/OR** Level 4 compliance of 70–89%, isolated non-conformances, or recurring minor themes requiring attention.\n- Review justification, findings and corrective actions, and opportunities to recover leadership visibility and improve compliance during the next reporting period.\n- Where targets are missed, review documented justification in the monthly KPI process. Failure to provide suitable justification results in **Red**, irrespective of compliance monitoring performance.\n\n**Red**\n- Supervisor or HSE Adviser: less than 50% of expected visits during the month.\n- Site Manager: visit target not achieved within two continuous quarters, or more than two quarters in a rolling 12-month period.\n- **AND/OR** Level 4 compliance below 70%, significant non-conformances, repeat findings, or evidence that permit controls are ineffective at the worksite.\n- Immediate intervention: review justification, findings and corrective actions, and opportunities to recover leadership visibility and improve compliance during the next reporting period.\n\n**Asset visitation:** review over/under visiting by Site Managers. Where significant imbalances exist, target future visits proportionately to operational activity, risk profile and workforce exposure.")
        with cols[4]:
            if k5 and not (k5[13] or "").strip():st.warning("Incident Register source note missing; result needs validation. Any Red incident trigger remains visible.")
            k5_reason=("Incident severity or recurring-control criterion triggered" if k5s=="Red" else f"Increase from {prev} to {current}" if k5s=="Amber" and current>prev else "Incident warning criterion triggered" if k5s=="Amber" else "Source note needs validation" if k5s=="Needs review" else "No adverse incident trigger" if k5s=="Green" else "Incident Register summary needed")
            measure_card("KPI 5","Permit-Controlled Incidents","Rolling 12-month count",k5v,"Previous 12-month count",str(prev) if k5 else "—",k5s,k5_reason,"Synthetic UAT scenario" if k5_synthetic else "Company-wide Incident Register source required")
            with st.expander("KPI Targets & Tolerances"):
                st.markdown("**Measure and target**\nReport incidents confirmed as occurring during permit-controlled activities over a **rolling 12-month period**, with identification of HiPOs, losses of containment and significant injuries (MTC or above). Use reviewed Incident Register records and the Incident Register tracking spreadsheet.\n\n**Green:** No increase in the rolling 12-month incident trend. No HiPOs, significant injuries (MTC or above), or repeat loss-of-containment events identified. No intervention required; continue monitoring and discussion through Monthly Operations and QSHE meetings.\n\n**Amber:** Increasing incident trend, a single HiPO, significant injury, loss of containment, or a repeat event theme identified within the reporting period. Operations Director intervention through targeted campaigns, assurance activities or focused reviews to address identified themes.\n\n**Red:** Significant increase in incidents, multiple HiPOs, significant injuries (MTC or above), major loss-of-containment events, or evidence of recurring failures in permit controls. Immediate General Manager intervention; investigation findings, learning actions and improvement measures implemented and tracked to closure.")
        st.markdown("### Explore the assurance data")
        st.caption("Start with insights → open a detailed KPI → review findings and owners → present the leadership report. All views use the month, asset and site selected above.")
        selected_view=st.radio("Choose a data view",["Assurance Insights","Leadership Report","Detailed KPI Reports","Findings & Actions","Auditor View","Company & Site Performance","Monthly History","KPI 5 Data","Human Factors"],horizontal=True,key="dashboard-data-view",label_visibility="collapsed")
        if selected_view=="Monthly History":
            st.subheader("Monthly History")
            dated=[(a,safe_date(a["audit_date"])) for a in all_a]
            dated=[(a,d) for a,d in dated if d]
            if not dated:
                st.info("No dated audit submissions are available yet.")
            else:
                first=min(d for _,d in dated).replace(day=1)
                last=max(max(d for _,d in dated),date.today()).replace(day=1)
                available_years=range(first.year,last.year+1)
                selected_year=st.selectbox("HISTORY PERIOD",["All recorded months"]+[str(yr) for yr in reversed(available_years)])
                months=[]
                cursor=first
                while cursor<=last:
                    if selected_year=="All recorded months" or cursor.year==int(selected_year):months.append(cursor)
                    cursor=date(cursor.year+1,1,1) if cursor.month==12 else date(cursor.year,cursor.month+1,1)
                dated=[(a,d) for a,d in dated if site=="All" or a["site"]==site]
                def history_counts(rows):
                    aa=[a for a,_ in rows]
                    permits=[a for a in aa if a["form_name"]=="Control of Work: Permit Quality"]
                    eligible_lead=leadership_kpi_breakdown([a for a in aa if "Leadership Engagement" in a["form_name"]],lmap,nui_sites)["eligible"]
                    count5=next((r[4] for r in reversed(history_k5) if r[2]==month_start.strftime("%Y-%m")),None)
                    return {
                        "KPI 1 Site Controller – Permit Quality":sum(permit_auditor_role(a,pmap)=="Site Controller" and permit_type(a)!="Unclassified" for a in permits),
                        "KPI 2 Asset Superintendent – Permit Quality":sum(permit_auditor_role(a,pmap)=="Asset Superintendent" for a in permits),
                        "KPI 3 Leadership CoW Engagements – Remote Site":len(eligible_lead),
                        "KPI 4 Site Leadership – Permit compliance Remote Site":sum("Toolbox Talk" in a["form_name"] and tbt_auditor_role(a,tmap) in visit_roles and a["site"] in nui_sites for a in aa),
                        "KPI 5 Permit-controlled Incidents":count5,
                    }
                con=db(); history_k5=con.execute("SELECT * FROM kpi5 WHERE demo=0 AND site=? ORDER BY submitted_at",("All",)).fetchall(); con.close()
                monthly=[]
                for month_start in reversed(months):
                    rows=[(a,d) for a,d in dated if d.year==month_start.year and d.month==month_start.month]
                    monthly.append({"Month":month_start.strftime("%B %Y"),**history_counts(rows)})
                st.dataframe(pd.DataFrame(monthly),use_container_width=True,hide_index=True)
                st.caption("Monthly activity counts use eligible roles. These are activity counts, not historical KPI RAG ratings. KPI 5 is the company-wide rolling incident count.")
        if selected_view=="Company & Site Performance":
            st.subheader("Monthly performance by Site / Hub"); rows=[]
            month_permit=[a for a in month if a["form_name"]=="Control of Work: Permit Quality" and permit_auditor_role(a,pmap)=="Site Controller"]
            for g,(rw,nw) in selected_groups.items():
                aa=[a for a in month_permit if a["site"]==g]; routine=sum(permit_type(a)=="Routine" for a in aa); nonroutine=sum(permit_type(a)=="Non-routine" for a in aa); raw_done=routine+nonroutine; done=sum(r["Credited"] for r in monthly_report["weekly"] if r["KPI"]=="KPI 1" and r["Site / Hub"]==g); plan=(rw+nw)*w; pc=completion_percentage(done,plan) if plan else None; cf=audit_conformance([a for a in aa if permit_type(a)!="Unclassified"],rounded=False); status=rag(pc,cf)
                routine_weeks,_=weekly_coverage(aa,y,m,rw,lambda a:permit_type(a)=="Routine")
                nonroutine_weeks,_=weekly_coverage(aa,y,m,nw,lambda a:permit_type(a)=="Non-routine")
                if status=="Green" and (routine_weeks<w or nonroutine_weeks<w):status="Needs review"
                rows.append({"Site / Group":g,"Routine permits":f"{routine}/{rw*w}","Non-routine permits":f"{nonroutine}/{nw*w}","Recorded SC audits":len(aa),"Awaiting permit category verification":len(aa)-raw_done,"Planned":plan,"Eligible classified samples":done,"Completion %":round(pc,1) if pc is not None else None,"Whole-audit conformance %":round(cf,1) if cf is not None else None,"RAG":status})
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            st.caption(f"Monthly basis: {w} reporting weeks. Only Site Controller audits with a recorded routine/non-routine category count toward planned samples. Permit Register source verification remains required. Blank completion and Not assessed mean there are no SC records at that site; they do not establish zero work in Permit Register.")
            excluded=[a for a in month if a["form_name"]=="Control of Work: Permit Quality" and permit_auditor_role(a,pmap)!="Asset Superintendent" and (a["site"] not in SITE_GROUPS or permit_auditor_role(a,pmap)!="Site Controller" or permit_type(a)=="Unclassified")]
            if excluded:
                st.markdown("#### Site Controller attribution or category review")
                st.dataframe(pd.DataFrame([{"Audit ID":a["audit_id"],"Date":a["audit_date"],"Entered location":a["site"],"Auditor role":permit_auditor_role(a,pmap),"Sample category":permit_type(a),"Reason":", ".join(x for x in ("Location outside SC groups" if a["site"] not in SITE_GROUPS else "","Auditor role requires verification" if permit_auditor_role(a,pmap)!="Site Controller" else "","Category not verified" if permit_type(a)=="Unclassified" else "") if x)} for a in excluded]),use_container_width=True,hide_index=True)
                with st.expander("Validate a historic permit record against Permit Register"):
                    chosen_id=st.selectbox("Audit ID for correction",[a["audit_id"] for a in excluded],key=f"permit-fix-{period}")
                    chosen=next(a for a in excluded if a["audit_id"]==chosen_id)
                    with st.form(f"permit-correction-{chosen_id}"):
                        c1,c2,c3=st.columns(3)
                        corrected_site=c1.selectbox("Verified site / group",ASSET_GROUPS,index=ASSET_GROUPS.index(chosen["site"]) if chosen["site"] in ASSET_GROUPS else 0)
                        corrected_role=c2.selectbox("Verified auditor role",["Site Controller","Asset Superintendent","Other"],index=["Site Controller","Asset Superintendent","Other"].index(permit_auditor_role(chosen,pmap)) if permit_auditor_role(chosen,pmap) in ["Site Controller","Asset Superintendent","Other"] else 2)
                        corrected_category=c3.selectbox("Verified Permit Register category",["Routine","Non-routine"],index=["Routine","Non-routine"].index(permit_type(chosen)) if permit_type(chosen) in ["Routine","Non-routine"] else 0)
                        correction_ref=st.text_input("Permit Register source reference / validation note")
                        correct=st.form_submit_button("Save verified attribution")
                    if correct:
                        if not correction_ref.strip():st.error("Enter a Permit Register reference or validation note before changing an audit.")
                        else:
                            metadata=dict(chosen["metadata"])
                            history=list(metadata.get("attribution_history") or [])
                            history.append({"corrected_at":datetime.now().isoformat(timespec="seconds"),"source":correction_ref.strip(),"previous_site":chosen["site"],"previous_role":metadata.get("auditor_role"),"previous_category":metadata.get("permit_sample_category"),"site":corrected_site,"role":corrected_role,"category":corrected_category})
                            metadata.update(site=corrected_site,auditor_role=corrected_role,permit_sample_category=corrected_category,attribution_history=history)
                            c=db(); c.execute("UPDATE audits SET site=?,metadata=? WHERE audit_id=?",(corrected_site,json.dumps(metadata),chosen_id)); c.commit(); c.close(); st.rerun()
        if selected_view=="Findings & Actions":
            rows=[]
            for a in permit+tbt+lead:
                for r in a["responses"]:
                    if str(r.get("response","")).lower()!="no":
                        continue
                    rows.append({
                        "BAR":r.get("bar_rating",""),
                        "Date":a.get("audit_date",""),
                        "Audit ID":a.get("audit_id",""),
                        "Site":a.get("site",""),
                        "Form":a.get("form_name",""),
                        "Auditor":a.get("auditor",""),
                        "Ref":r.get("item",""),
                        "Finding":r.get("question",""),
                        "Evidence":r.get("comments_evidence",""),
                        "Immediate action":r.get("immediate_action",""),
                        "SMART action":r.get("smart_action",""),
                        "Owner":r.get("action_owner",""),
                        "Due date":r.get("action_due_date",""),
                    })
            if rows:
                findings_df=pd.DataFrame(rows)
                findings_df["_bar_order"]=findings_df["BAR"].map({"BAR 1":1,"BAR 2":2,"BAR 3":3}).fillna(4)
                findings_df=findings_df.sort_values(["_bar_order","Date","Audit ID"],ascending=[True,False,True]).drop(columns="_bar_order")
                bar1_df=findings_df[findings_df["BAR"]=="BAR 1"]
                f1,f2,f3=st.columns([1,1,2])
                selected_bar=f1.selectbox("BAR level",["All","BAR 1","BAR 2","BAR 3"],key="findings-bar")
                selected_owner=f2.selectbox("Action owner",["All"]+sorted(set(findings_df["Owner"]) - {""}),key="findings-owner")
                search=f3.text_input("Search findings",placeholder="Question, site, auditor or action…",key="findings-search")
                filtered=findings_df.copy()
                if selected_bar!="All": filtered=filtered[filtered["BAR"]==selected_bar]
                if selected_owner!="All": filtered=filtered[filtered["Owner"]==selected_owner]
                if search.strip(): filtered=filtered[filtered.astype(str).apply(lambda col: col.str.contains(search.strip(),case=False,regex=False)).any(axis=1)]
                st.caption(f"Showing {len(filtered)} of {len(findings_df)} non-conformances in the selected reporting scope.")
                st.download_button("Download selected findings",filtered.drop(columns=["Evidence","Immediate action"],errors="ignore").to_csv(index=False).encode("utf-8-sig"),f"CoW_Findings_{period}.csv","text/csv",key="findings-download")
                bar1_df=filtered[filtered["BAR"]=="BAR 1"]
                st.markdown(f"#### BAR 1 non-conformances ({len(bar1_df)})")
                st.caption("BAR is assigned to the question, not separately to the finding.")
                if len(bar1_df):
                    for finding in bar1_df.to_dict("records"):
                        with st.container(border=True):
                            st.markdown(f"**{finding['Ref'] or 'Question'} · {finding['Site']}**")
                            st.caption(f"{finding['Date']} · {finding['Form']} · Audit {finding['Audit ID']}")
                            st.write(finding["Finding"])
                            st.markdown("**Evidence**")
                            st.write(finding["Evidence"] or "Not recorded.")
                            st.markdown("**Immediate safety action / current exposure**")
                            st.write(finding["Immediate action"] or "Not recorded.")
                            st.markdown("**SMART action**")
                            st.write(finding["SMART action"] or "Not recorded.")
                            st.caption(f"Owner: {finding['Owner'] or '—'} · Due: {finding['Due date'] or '—'}")
                else:
                    st.success("No failed BAR 1 questions in this view.")
                st.markdown(f"#### Selected non-conformances ({len(filtered)})")
                st.caption("Sorted BAR 1 first. Each No response appears once.")
                st.dataframe(filtered.drop(columns=["Evidence","Immediate action"],errors="ignore"),use_container_width=True,hide_index=True)
                repeat_df=(findings_df.groupby(["Finding","BAR"],dropna=False).agg(Occurrences=("Finding","size"),Sites=("Site",lambda x:", ".join(sorted({str(v) for v in x if v})))).reset_index().sort_values(["Occurrences","BAR"],ascending=[False,True]).head(5))
                st.markdown("#### Most frequent failed questions (top five)")
                st.dataframe(repeat_df,use_container_width=True,hide_index=True)
            else:
                st.success("No negative assurance responses in this view.")
        if selected_view=="Assurance Insights":
            st.markdown("**CoW Assurance Insights.** See what the audits found, which work-control checks need attention and what to do next."); c1,c2,c3=st.columns(3); c1.metric("Question conformance",format_percentage(q_conf(permit+tbt)),help="Yes answers divided by applicable Yes/No answers. N/A answers are excluded."); c2.metric("Permit whole-audit conformance",format_percentage(audit_conformance(permit,rounded=False)),help="Percentage of scored permit audits with no No answers. One No makes an audit non-conformant."); c3.metric("TBT/POP whole-audit conformance",format_percentage(audit_conformance(tbt,rounded=False)),help="Percentage of scored TBT/POP audits with no No answers.")
            st.caption(checklist_compliance_basis(permit+tbt))
            with st.expander("How to read these results"):
                st.write("Question conformance measures individual Yes/No answers. Whole-audit conformance is the percentage of scored audits with no No answers. N/A answers are excluded. Themes group the failed checks; they do not establish causes or the condition of every barrier. Displayed percentages round upwards; RAG uses unrounded values.")
            st.markdown("#### What needs attention")
            st.info(nonconformance_narrative(permit+tbt))
            with st.expander("Controls verified by Yes responses",expanded=False):
                st.markdown("#### Controls verified by Yes responses")
                positives=[{"Date":a["audit_date"],"Site / Team":a["site"],"Audit ID":a["audit_id"],"Question":r.get("question",""),"Ref":r.get("item","")} for a in permit+tbt for r in a["responses"] if str(r.get("response","")).lower()=="yes"]
                if positives: st.dataframe(pd.DataFrame(positives),use_container_width=True,hide_index=True)
                else: st.caption("No controls verified by a Yes response in the selected view.")
                st.caption("Yes confirms checklist conformance; it does not by itself demonstrate exceptional practice. Non-conformances and actions remain the priority.")
        if selected_view=="Human Factors":
            from human_factors import render as render_hf_comment_themes
            render_hf_comment_themes(permit+tbt+lead,period)
        if selected_view=="Auditor View":
            from kpi_rules import average_audit_conformance
            st.subheader("Auditor results")
            st.caption("Compare audit counts, average question scores and audit pass rates. Select an auditor below to review their BAR non-conformances.")
            with st.expander("How auditor scores are calculated"):
                st.write("Average question score is the mean of each audit’s Yes ÷ applicable Yes/No percentage, giving each audit equal weight. Audit pass rate is the percentage of scored audits with no No answers. N/A and unscored audits are excluded from percentages; all completed audits remain in the count.")
            rr=[]
            for n in sorted({a["auditor"] for a in permit+tbt+lead if a["auditor"]}):
                aa=[a for a in permit+tbt+lead if a["auditor"]==n]; rr.append({"Auditor / Leader":n,"Audits completed":len(aa),"Average question score %":format_percentage(average_audit_conformance(aa)).removesuffix("%"),"Audit pass rate %":format_percentage(audit_conformance(aa,rounded=False)).removesuffix("%"),"Sites / Teams":", ".join(sorted({a["site"] for a in aa if a["site"]}))})
            st.dataframe(pd.DataFrame(rr),use_container_width=True,hide_index=True) if rr else st.info("No auditor data.")
            if rr:
                with st.expander("What do the BAR levels mean?"):
                    st.markdown("**BAR — Barrier Assurance Review.** Each audit question has a preset classification. A **No** records a non-conformance against that question. The BAR identifies the type of control being checked; it is not a separate score assigned to the finding.")
                    st.markdown("**BAR 1 · Critical control verification:** checks a required control against major accident or serious harm. A No requires immediate action to make work safe.\n\n**BAR 2 · Operational control:** checks planning, understanding, supervision or how work is carried out. A No requires correction and tracking.\n\n**BAR 3 · Management and learning:** checks oversight, records, lessons or improvement follow-up. A No requires an improvement action.")
                    st.caption("These are the demonstration definitions; question classifications require agreement before operational use.")
                selected_auditor=st.selectbox("Auditor / Leader for BAR non-conformances",[row["Auditor / Leader"] for row in rr],key="bar-failure-auditor")
                bar_context=(period,asset,site,selected_auditor)
                if st.button("Show BAR non-conformances",key="show-auditor-bar-failures",type="primary"):
                    st.session_state["_auditor_bar_context"]=bar_context
                if st.session_state.get("_auditor_bar_context")==bar_context:
                    failed=auditor_bar_failures(permit+tbt+lead,selected_auditor)
                    st.markdown(f"#### BAR non-conformances · {selected_auditor}")
                    st.caption(f"{len(failed)} non-conformances across {len({row['Audit ID'] for row in failed})} audit(s) · selected month and filters.")
                    if failed:
                        count_columns=st.columns(3)
                        for column,bar in zip(count_columns,["BAR 1","BAR 2","BAR 3"]):
                            column.metric(bar+" non-conformances",sum(row["BAR"]==bar for row in failed))
                        for bar in ["BAR 1","BAR 2","BAR 3","Unrated"]:
                            records=[row for row in failed if row["BAR"]==bar or (bar=="Unrated" and row["BAR"] not in {"BAR 1","BAR 2","BAR 3","Unrated"})]
                            if records:
                                with st.expander(f"{bar} · {len(records)} non-conformances",expanded=bar=="BAR 1"):
                                    st.dataframe(pd.DataFrame(records),use_container_width=True,hide_index=True)
                    else:
                        st.success("No BAR non-conformances for this auditor in the selected view.")

        if selected_view=="KPI 5 Data":
            st.subheader("KPI 5 · Company-wide Incident Register incident summary"); a,b,c=st.columns(3); current=a.number_input("Rolling 12-month permit-controlled incidents",0,999,0); prev=b.number_input("Previous rolling 12-month incidents",0,999,0); hipo=c.number_input("HiPO events",0,999,0); a,b,c=st.columns(3); injury=a.number_input("Significant injuries (MTC+)",0,999,0); loc=b.number_input("Loss of Containment",0,999,0); major=c.number_input("Major Loss of Containment",0,999,0); a,b,c=st.columns(3); repeat=a.selectbox("Repeat event theme?",["No","Yes"]); recurring=b.selectbox("Recurring permit-control failure?",["No","Yes"]); sig=c.selectbox("Significant increase?",["No","Yes"],help="No numerical threshold is assumed; use the agreed management assessment."); comments=st.text_area("Incident Register source, reviewed themes and leadership actions",height=220,help="Record the source, task and root-cause themes, interpretation, accountable action owners and follow-up. Structured counts above still drive the provisional KPI.")
            if st.button("Save KPI 5 result",type="primary"):
                if not comments.strip():st.error("Record the Incident Register tracking source and validation note before saving.")
                else:
                    rid="KPI5-"+uuid.uuid4().hex[:8].upper(); con=db(); con.execute("INSERT INTO kpi5 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(rid,datetime.now().isoformat(timespec="seconds"),period,"All",current,prev,hipo,injury,loc,major,repeat,recurring,sig,comments,0)); con.commit(); con.close(); st.success("KPI 5 result saved.")
        if selected_view=="Leadership Report":
            from monthly_report import report_controls
            report_controls(db,monthly_report,asset+" / "+site,k5s)

        if selected_view=="Detailed KPI Reports":
            st.caption("Select a KPI below to review delivery, conformance, findings, targets and leadership actions.")
            from leadership_views import render as render_leadership_details
            detail_groups={g:v for g,v in selected_groups.items() if site=="All" or g==site}
            detail_tbt=[a for a in tbt if a["site"] in {"North Remote Sites","South Remote Sites"} and tbt_auditor_role(a,tmap) in {"Operations Supervisor","HSE Adviser","Site Manager"}]
            render_leadership_details(db,recovery_actions,period,asset+" / "+site,y,m,detail_groups,sc_samples,as_samples,qlead,detail_tbt,tmap,statuses,{"all_a":all_a,"pmap":pmap,"monthly_report":monthly_report})
            with st.expander("Supporting delivery and accountability tables",expanded=False):
                st.markdown('<div class="section-head">KPI 3 – Monthly and Three-month View</div>',unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(k3_month_rows),use_container_width=True,hide_index=True)
                st.caption(f"Q{q} {y}: {k3n}/3 eligible engagements through {md.strftime('%B')}; quarter engagement conformance {format_percentage(k3c) if k3c is not None else '—'}; coverage {gov['kpi3_coverage']}. Monthly rows show contributions, while the RAG rating applies to the three-month quarter. Future months in the selected quarter are blank.")
                with st.sidebar.expander("How the provisional position is calculated"):
                    st.markdown("The provisional position shows the most adverse assessed KPI. It remains a demonstration indicator while source checks are incomplete. KPI 1 and KPI 2 use whole-permit conformance: one failed checklist item fails that permit audit, regardless of the question's preset BAR. Question BARs determine each form's result. KPI 3 uses eligible leadership engagement completion and whole-engagement conformance, with Remote Site coverage checked against Visit Register.")
                st.subheader("Weekly Site Controller delivery")
                weekly_rows=[]
                for group,(routine_target,new_target) in selected_groups.items():
                    if site!="All" and group!=site: continue
                    for category,target in (("Routine",routine_target),("Non-routine",new_target)):
                        records=[a for a in sc_samples if a["site"]==group and permit_type(a)==category]
                        met,planned=weekly_coverage(records,y,m,target)
                        weekly_rows.append({"Site / Hub":group,"Sample category":category,"Weekly target":target,"Weeks target met":met,"Weeks planned":planned,"Weeks below target":planned-met,"Recorded auditors":", ".join(sorted({a["auditor"] for a in records})),"Accountable role":"Site Controller / Site Leadership"})
                st.dataframe(pd.DataFrame(weekly_rows),use_container_width=True,hide_index=True)
                st.subheader("Accountability and required response")
                account=[]
                for i,(status,owner) in enumerate(zip(statuses,["Site Leadership","Operations Director","General Manager","Site Leadership / Operations Director","Operations Director"])):
                    if status!="Green":
                        account.append({"KPI":f"KPI {i+1}","Status":status,"Accountable role":owner,"Required response":"Validate source / target allocation" if status not in ("Red","Amber") else "Immediate intervention; actions within one month" if status=="Red" and i<4 else "Review performance and agree follow-up actions"})
                if account: st.dataframe(pd.DataFrame(account),use_container_width=True,hide_index=True)
                st.caption("Role accountability is shown above. Finding owners and due dates are in Findings & Actions. Named missed obligations require an approved rota/target allocation; recorded auditors alone do not establish who was due to audit.")

st.caption("**DEMO ONLY · Fictional data · Temporary session · Do not enter confidential information**")
import importlib, demo_audits
if demo_audits.SCENARIO != "september-conformance-75-83-hf-v3":
    importlib.reload(demo_audits)
demo_audits.prepare(db, DATA, SITE_GROUPS)
st.sidebar.markdown("### PDi | VERIFY")
st.sidebar.caption("Control of Work assurance · Demo")
with st.sidebar.expander("About this demonstration"):
    st.write("All sites, people, audits and incidents are fictional. Sample KPI targets and BAR classifications require client agreement before operational use. Failed checks are deliberately concentrated in a minority of audits to demonstrate question and whole-audit conformance around 75–83%. Data is temporary and isolated for this session.")
page=st.sidebar.radio("Navigation",["Dashboard","Permit Quality","Toolbox Talk / Permit / POP","Leadership Engagement","Submitted Audits","Dashboard Export"],label_visibility="collapsed")

if page=="Dashboard": dashboard()
elif page=="Permit Quality":
    banner("SELF VERIFICATION - LEVEL 4 MONITORING","Control of Work: Permit Quality")
    c1,c2,c3,c4=st.columns([1.5,1.2,1.2,1]); c1.selectbox("SITE / INSTALLATION:",["Select..."]+ASSET_GROUPS,key="permit-site"); c2.text_input("TEAM:",key="permit-team"); c3.date_input("DATE OF AUDIT:",date.today(),key="permit-date"); c4.checkbox("New WCC",key="permit-new")
    c1,c2,c3=st.columns([1.5,1.2,1.2]); person_input(c1,"AUDITOR:",key="permit-auditor"); person_input(c2,"SITE CONTROLLER ON WCC:",key="permit-controller"); c3.text_input("WCC NUMBER:",key="permit-ref"); st.text_input("WCC DESCRIPTION:",key="permit-description")
    st.radio("Permit sample category for KPI reporting",["Routine","Non-routine"],index=None,horizontal=True,key="permit-category",help="Classify the activity from Permit Register. A new WCC is not automatically non-routine.")
    st.selectbox("Auditor role for KPI reporting",["Site Controller","Asset Superintendent","Other"],key="permit-role",help="Site Controller self-verification counts toward KPI 1. Asset Superintendent independent assurance counts toward KPI 2.")
    if st.session_state.get("permit-role")=="Asset Superintendent":
        st.selectbox("Independent assurance group (KPI 2 rotation)",["Select..."]+AS_ASSURANCE_GROUPS,index=0,key="permit-assurance-group")
    st.caption("For self-verification, enter the Site Controller as AUDITOR. The Site Controller on the WCC may be the same person. Select Asset Superintendent only for an independent review. New WCC is a separate certificate detail, not a KPI sample category.")
    purpose("Self-verify the quality of a planned or active Work Control Certificate (WCC), including permit preparation, hazard identification, risk assessment, control selection, authorisation and worksite readiness."); bar_review(evidence_required=False); st.markdown('<div class="blackbar">QUESTION</div>',unsafe_allow_html=True); questions("ptw",DATA["ptw"],show_evidence=False); st.markdown('<div class="blackbar">ENSURE EACH NON-CONFORMANCE GENERATES A RECORDED SMART ACTION</div>',unsafe_allow_html=True)
    st.button("Submit Permit Quality Audit",type="primary",use_container_width=True,on_click=submit_assurance,args=("permit",))
    show_audit_notice("permit")
elif page=="Toolbox Talk / Permit / POP":
    banner("SELF VERIFICATION - LEVEL 4 MONITORING","Control of Work: Toolbox Talk, Permit Compliance & Operating Procedures")
    c1,c2,c3,c4=st.columns([1.5,1.2,1.2,1]); c1.selectbox("SITE / INSTALLATION:",["Select..."]+ASSET_GROUPS,key="tbt-site"); c2.text_input("TEAM:",key="tbt-team"); c3.date_input("DATE OF AUDIT:",date.today(),key="tbt-date"); activity=c4.radio("TYPE",["Routine","Non-routine","POP"],index=None,key="tbt-activity")
    c1,c2,c3=st.columns(3); person_input(c1,"AUDITOR:",key="tbt-auditor"); person_input(c2,"SITE CONTROLLER:",key="tbt-controller"); c3.text_input("WCC / POP No:",key="tbt-ref"); st.text_input("DESCRIPTION:",key="tbt-description")
    st.selectbox("Auditor role for KPI 4 reporting",["Select role...","Operations Supervisor","HSE Adviser","Site Manager","Other / not KPI 4 visitor"],key="tbt-role")
    # One classification control drives both the form and KPI metadata.
    st.session_state["tbt-permit-category"]=activity if activity in ("Routine","Non-routine") else None
    if activity in ("Routine","Non-routine"):
        st.checkbox("New WCC",key="tbt-new-wcc",help="Certificate detail only. A new WCC can cover either routine or non-routine activity.")
    st.caption("KPI 4 counts qualifying visits to Northern or Southern Remote Site teams by the selected role. The Site Controller field identifies the person engaged at the worksite.")
    purpose("Self-verify day-to-day Toolbox Talk, permit and operating-procedure conformance, workforce understanding and implementation of Control of Work requirements."); bar_review(evidence_required=False); st.markdown('<div class="blackbar">QUESTION · SITE VISIT REQUIRED · SEQUENTIAL REVIEW</div>',unsafe_allow_html=True); questions("tbt12",DATA["tbt"][:2],show_evidence=False)
    if activity=="POP":
        st.markdown('<div class="blackbar">POP REVIEW · MOVE TO QUESTION 8</div>',unsafe_allow_html=True)
        questions("pop",DATA["pop"],show_evidence=False)
    else:
        questions("tbt37",DATA["tbt"][2:],show_evidence=False)
    st.button("Submit TBT / Permit / POP Audit",type="primary",use_container_width=True,on_click=submit_assurance,args=("tbt",))
    show_audit_notice("tbt")
elif page=="Leadership Engagement":
    banner("Control of Work Leadership Engagement Review")
    c1,c2,c3,c4=st.columns([1,2,1.4,1.7]); c1.date_input("Date",date.today(),key="lead-date"); c2.text_input("Location / Team",key="lead-site"); person_input(c3,"Site Controller",key="lead-controller"); person_input(c4,"Leadership Representative",key="lead-representative")
    p1,p2=st.columns(2); p1.date_input("Learning review period start",date.today().replace(day=1),key="lead-period-start"); p2.date_input("Learning review period end",date.today(),key="lead-period-end")
    st.selectbox("Leadership role for KPI reporting",["Select role...","Operations Director","Deputy Operations Director","Asset Superintendent","Ops Support Manager","Other / not KPI 3 role"],key="lead-role")
    st.selectbox("Engagement setting",["Remote Site team visit","Intervention Team","Office Engagement","Quayside Engagement","Other location"],key="lead-context")
    st.text_input("Remote Site team engaged (one team per entry)",key="lead-nui-team",help="For Support visits with several teams, submit an individual checklist for each team engagement. Identify the team for Site Bravo, Office Engagement or quayside entries.")
    st.caption("KPI 3 includes specified leaders' Remote Site team engagements, including identified Intervention Team, Office Engagement and quayside Support engagements. Confirm counts with Visit Register.")
    purpose("Practical leadership conversation at the worksite and with the Site Controller. Each scored question has a preset BAR; discussion prompts are unscored.")
    bar_review()
    st.markdown('<div class="blackbar">QUESTIONS · LEADERSHIP ENGAGEMENT</div>',unsafe_allow_html=True)
    questions("lead",DATA["lead"])
    st.markdown('<div class="blackbar">CONVERSATION PROMPTS · NOT SCORED</div>',unsafe_allow_html=True)
    for ref,prompt in DATA["lead_narrative"]:
        st.text_area(f"{ref} · {prompt}",key=f"lead-narrative-{ref}")
    st.text_area("Opportunities for Improvement",key="lead-improvement"); st.text_area("Auditor Notes",key="lead-notes")
    st.caption("The result is calculated from question BARs. A separate serious safety concern must be made safe and escalated even if the preset question result is lower.")
    st.button("Submit Leadership Engagement",type="primary",use_container_width=True,on_click=submit_assurance,args=("lead",))
    show_audit_notice("lead")
elif page=="Submitted Audits":
    st.header("Submitted Audits"); aa=audits(); rm=role_maps()
    def submitted_role(a):
        if a["form_name"]=="Control of Work: Permit Quality":return permit_auditor_role(a,rm["permit"])
        if "Toolbox Talk" in a["form_name"]:return tbt_auditor_role(a,rm["tbt"])
        if "Leadership Engagement" in a["form_name"]:return a["metadata"].get("leadership_role") or rm["lead"].get(a["auditor"],"Unconfirmed")
        return "—"
    df=pd.DataFrame([{**{k:a[k] for k in ["audit_id","submitted_at","form_name","audit_date","site","auditor"]},"auditor_role":submitted_role(a),**{k:a[k] for k in ["reference","summary"]}} for a in aa])
    df=df.rename(columns={"audit_id":"Audit ID","submitted_at":"Submitted","form_name":"Audit type","audit_date":"Audit date","site":"Site / Hub","auditor":"Auditor / Leader","auditor_role":"Role","reference":"Reference","summary":"Result"})
    st.caption("Use the table search and column controls to find a person, site or audit.")
    if len(df):
        c1,c2=st.columns([1,2])
        audit_type=c1.selectbox("Audit type",["All"]+sorted(df["Audit type"].unique()),key="submitted-type")
        audit_search=c2.text_input("Find an audit",placeholder="Auditor, site, reference or result…",key="submitted-search")
        if audit_type!="All": df=df[df["Audit type"]==audit_type]
        if audit_search.strip(): df=df[df.astype(str).apply(lambda col:col.str.contains(audit_search.strip(),case=False,regex=False)).any(axis=1)]
        st.caption(f"{len(df)} audits shown")
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("Download displayed audits",df.to_csv(index=False).encode("utf-8-sig"),"CoW_Audit_Register.csv","text/csv")
    else: st.info("No submissions yet.")
    if len(df):st.caption("Auditor role is recorded on new forms. Historic unconfirmed roles can be verified under Dashboard → KPI role configuration; KPI site criteria still apply.")
else:
    st.header("Dashboard Export")
    st.caption("Download all audit question responses in this demo session, including comments and actions. Dashboard filters apply to dashboard views, not this full-session export.")
    flat=[]
    for a in (x for x in audits() if not x["audit_id"].startswith("DEMO-") and not x["metadata"].get("demo")):
        for r in a["responses"]:flat.append({"Audit ID":a["audit_id"],"Submitted At":a["submitted_at"],"Form":a["form_name"],"Audit Date":a["audit_date"],"Site / Installation":a["site"],"Auditor":a["auditor"],"Reference":a["reference"],"Section":r.get("section",""),"Question Ref":r.get("item",""),"BAR Rating":r.get("bar_rating",""),"Question":r.get("question",""),"Response":r.get("response",""),"Comments / Evidence":r.get("comments_evidence",""),"SMART Action":r.get("smart_action",""),"Action Owner":r.get("action_owner",""),"Action Due Date":r.get("action_due_date",""),"Immediate Safety Action":r.get("immediate_action",""),"Question-based Result":a["summary"]})
    if flat:
        df=pd.DataFrame(flat); st.dataframe(df.head(100),use_container_width=True,hide_index=True); st.download_button("Download dashboard-ready CSV",df.to_csv(index=False).encode("utf-8-sig"),"Operational_Assurance_Export.csv","text/csv",use_container_width=True)
    else:st.info("Submit a test audit first.")



