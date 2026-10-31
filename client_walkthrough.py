"""Demo presentation views; never modify stored assurance records."""
import math
from collections import Counter


def open_demo_evidence(label):
    import streamlit as st
    st.session_state['dashboard-data-view'] = 'Detailed KPI Reports' if label == 'KPI 5' else 'Evidence Trail'
    if label != 'KPI 5':
        st.session_state['trail-kpi'] = label


def scored(rows):
    return [(a, [r for r in a.get('responses', []) if r.get('response') in ('Yes', 'No')]) for a in rows if any(r.get('response') in ('Yes', 'No') for r in a.get('responses', []))]


def conformance_scenario(rows, corrected):
    records = scored(rows)
    passed = sum(all(r['response'] == 'Yes' for r in responses) for _, responses in records)
    failed = len(records) - passed
    corrected = max(0, min(int(corrected), failed))
    return passed, failed, (100 * (passed + corrected) / len(records) if records else None)


def snapshot(rows, statuses):
    import streamlit as st
    failed = [(a, r) for a in rows for r in a.get('responses', []) if r.get('response') == 'No']
    red = ', '.join(f'KPI {i+1}' for i, status in enumerate(statuses) if status == 'Red')
    amber = ', '.join(f'KPI {i+1}' for i, status in enumerate(statuses) if status == 'Amber')
    st.markdown('### Your CoW position in 60 seconds')
    c1, c2, c3 = st.columns(3)
    c1.metric('KPIs requiring attention', sum(s in ('Red', 'Amber') for s in statuses))
    c2.metric('Audits with non-conformances', len({a['audit_id'] for a, _ in failed}))
    c3.metric('BAR 1 non-conformances', sum(r.get('bar_rating') == 'BAR 1' for _, r in failed))
    st.write(f"**Performance:** Red: {red or 'None'} · Amber: {amber or 'None'}.")
    if failed:
        repeated = Counter(r.get('question', '') for _, r in failed)
        question, count = repeated.most_common(1)[0]
        st.write(f'**Assurance priority:** The most frequently failed check appears {count} times: {question}')
        st.write('**Leadership decision:** Confirm the response to critical-control gaps, agree owners and dates for recurring findings, and address missed assurance delivery. Use the evidence trail to review the source records.')
    else:
        st.write('No No responses in the selected audit sample. Check delivery and source coverage before drawing a wider assurance conclusion.')
    st.caption('Selected reporting scope · Fictional demonstration · Checklist results describe the audit sample.')


def evidence_trail(groups, period):
    import streamlit as st
    import pandas as pd
    from human_factors import comment_records
    st.subheader('KPI → audit → finding → action')
    label = st.selectbox('Choose a KPI evidence set', list(groups), key='trail-kpi')
    rows = groups[label]
    st.caption('These are the contributing audit records. KPI 4 visit coverage and KPI 5 incident sources are reviewed in Detailed KPI Reports; audit counts do not replace those sources.')
    if not rows:
        st.info('No contributing audits in this selection.')
        return
    register = [{'Audit ID': a['audit_id'], 'Date': a['audit_date'], 'Site': a['site'], 'Auditor': a['auditor'], 'No answers': sum(r.get('response') == 'No' for r in a['responses'])} for a in rows]
    st.dataframe(pd.DataFrame(register), hide_index=True, use_container_width=True)
    by_id = {a['audit_id']: a for a in rows}
    aid = st.selectbox('Open an audit', list(by_id), format_func=lambda key: f"{key} · {by_id[key]['site']} · {by_id[key]['auditor']}", key='trail-audit-'+label)
    audit = by_id[aid]
    st.markdown(f"#### {aid} · {audit['form_name']}")
    findings = [{'Ref': r.get('item', ''), 'BAR': r.get('bar_rating', ''), 'Question': r.get('question', ''), 'Evidence': r.get('comments_evidence', ''), 'Immediate action': r.get('immediate_action', ''), 'Required action': r.get('smart_action', ''), 'Owner': r.get('action_owner', ''), 'Due date': r.get('action_due_date', '')} for r in audit['responses'] if r.get('response') == 'No']
    if findings:
        st.dataframe(pd.DataFrame(findings), hide_index=True, use_container_width=True)
        st.download_button('Download this audit’s findings', pd.DataFrame(findings).to_csv(index=False).encode('utf-8-sig'), f'{aid}_findings.csv', 'text/csv')
    else:
        st.success('No non-conformances recorded in this audit.')
    comments = [r for r in comment_records([audit]) if r['_themes']]
    st.markdown('#### Related HF comments from this audit')
    for row in comments:
        st.write(row['Original comment'])
        st.caption('Suggested themes: '+row['Potential themes']+' · Source: '+row['Source reference'])
    if not comments:
        st.caption('No comment with a suggested HF theme in this audit.')
    st.caption('Comments are associated with the selected audit; this does not establish that they caused any non-conformance.')


def improvement_scenario(groups):
    import streamlit as st
    from kpi_rules import format_percentage
    st.subheader('What would improve this?')
    st.info('ILLUSTRATIVE SCENARIO · Stored audits, actions and reported KPI ratings remain unchanged.')
    label = st.selectbox('Choose an audit conformance measure', list(groups), key='scenario-kpi')
    rows = groups[label]
    passed, failed, current = conformance_scenario(rows, 0)
    if current is None:
        st.info('No scored audits in this selection.')
        return
    corrected = st.slider('Audits assumed fully corrected and verified', 0, failed, 0, key='scenario-corrected-'+label) if failed else 0
    _, _, projected = conformance_scenario(rows, corrected)
    a, b = st.columns(2)
    a.metric('Recorded whole-audit conformance', format_percentage(current))
    b.metric('Illustrative corrected position', format_percentage(projected))
    required = max(0, math.ceil(0.9 * (passed + failed)) - passed)
    st.write(f'**90% conformance threshold:** {required} of {failed} non-conformant audits would need every No response corrected and verified, on this fixed sample.')
    st.write(f'**Scenario:** {passed+corrected}/{passed+failed} audits fully conformant, compared with {passed}/{passed+failed} recorded.')
    st.caption('A follow-up verification is assumed for illustration. Original audit results remain a historical record. This is a conformance-only scenario: missed delivery, visit coverage, source checks and incident measures can still prevent an overall Green KPI.')
