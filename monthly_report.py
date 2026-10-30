"""One auditable monthly dataset drives dashboard KPIs and the downloadable report."""
import calendar
import html
from collections import Counter
from datetime import date,timedelta
from kpi_rules import reporting_weeks,weekly_coverage,permit_auditor_role,permit_sample_category,tbt_auditor_role,audit_conformance,leadership_kpi_breakdown,rag_status,leadership_status,presentation_visit_status

TITLES=['Site Controller – Permit Quality','Asset Superintendent – Permit Quality','Leadership CoW Engagements – Remote Site','Site Leadership – Permit compliance Remote Site','Permit-controlled Incidents']


def day(value):
    try:return date.fromisoformat(str(value)[:10])
    except (ValueError,TypeError):return None


def build(audits,year,month,groups,maps,coverage='Not assessed',today=None):
    today=today or date.today();weeks=reporting_weeks(year,month);end=date(year,month,calendar.monthrange(year,month)[1]);start=weeks[0]
    source=[a for a in audits if not (a.get('metadata') or {}).get('uat_sample') and not (a.get('metadata') or {}).get('demo') and not a.get('audit_id','').startswith('DEMO-')]
    rows=[a for a in source if day(a.get('audit_date')) and start<=day(a['audit_date'])<=min(end,today)]
    permits=[a for a in rows if a['form_name']=='Control of Work: Permit Quality']
    sc=[a for a in permits if a['site'] in groups and permit_auditor_role(a,maps['permit'])=='Site Controller' and permit_sample_category(a)!='Unclassified']
    asc=[a for a in permits if a['site'] in groups and permit_auditor_role(a,maps['permit'])=='Asset Superintendent' and permit_sample_category(a)!='Unclassified']
    q=(month-1)//3+1;qs=date(year,(q-1)*3+1,1);qe=date(year,q*3,calendar.monthrange(year,q*3)[1])
    leaders=[a for a in source if 'Leadership Engagement' in a['form_name'] and day(a.get('audit_date')) and qs<=day(a['audit_date'])<=min(end,today)]
    lead=leadership_kpi_breakdown(leaders,maps['lead'],{'North Remote Sites','South Remote Sites'})['eligible']
    monitoring=[a for a in rows if 'Toolbox Talk' in a['form_name'] and a['site'] in groups and a['site'] in {'North Remote Sites','South Remote Sites'} and tbt_auditor_role(a,maps['tbt']) in {'Operations Supervisor','HSE Adviser'}]
    weekly=[];credits=0
    for site,(routine,new) in groups.items():
        for week in weeks:
            last=min(week+timedelta(days=6),end);due=last<today or end<today
            for category,target in [('Non-routine',new),('Routine',routine)]:
                aa=[a for a in sc if a['site']==site and permit_sample_category(a)==category and week<=day(a['audit_date'])<=last]
                credited=min(len(aa),target);credits+=credited
                weekly.append({'KPI':'KPI 1','Site / Hub':site,'Week':f'WK{week.isocalendar().week:02d}','Category':category,'Required':target,'Submitted':len(aa),'Credited':credited,'Shortfall':max(0,target-len(aa)),'Status':'Met' if len(aa)>=target else 'Missed' if due else 'Pending','Recorded auditors':', '.join(sorted({a['auditor'] for a in aa}))})
    ascredits=0
    for week in weeks:
        last=min(week+timedelta(days=6),end);aa=[a for a in asc if week<=day(a['audit_date'])<=last];ascredits+=min(1,len(aa))
        weekly.append({'KPI':'KPI 2','Site / Hub':'Selected scope','Week':f'WK{week.isocalendar().week:02d}','Category':'All permits','Required':1,'Submitted':len(aa),'Credited':min(1,len(aa)),'Shortfall':max(0,1-len(aa)),'Status':'Met' if aa else 'Missed' if last<today else 'Pending','Recorded auditors':', '.join(sorted({a['auditor'] for a in aa}))})
    oo,_=weekly_coverage(monitoring,year,month,1,lambda a:tbt_auditor_role(a,maps['tbt'])=='Operations Supervisor');med,_=weekly_coverage(monitoring,year,month,1,lambda a:tbt_auditor_role(a,maps['tbt'])=='HSE Adviser')
    plan=sum(sum(v) for v in groups.values())*len(weeks);c1=audit_conformance(sc,rounded=False);c2=audit_conformance(asc,rounded=False);c3=audit_conformance(lead,rounded=False);c4=audit_conformance(monitoring,rounded=False)
    p1=100*credits/plan if plan else None;p2=100*ascredits/len(weeks)
    statuses=[rag_status(p1,c1),rag_status(p2,c2),leadership_status(len(lead),c3,coverage,end>=qe and today>qe),presentation_visit_status(100*oo/len(weeks),100*med/len(weeks),c4)]
    if end>=today:
        for i,conf in enumerate([c1,c2,c3,c4]):
            if (conf is None or conf>=70) and statuses[i] in ('Red','Amber','Not enough data'):statuses[i]='In progress'
    data=[sc,asc,lead,monitoring];findings=[]
    for i,aa in enumerate(data):
        for a in aa:
            for r in a['responses']:
                if str(r.get('response','')).lower()!='no':continue
                findings.append({'KPI':f'KPI {i+1}','Source':a['audit_id']+' / '+r.get('item',''),'Site':a['site'],'Date':a['audit_date'],'Auditor':a['auditor'],'Permit':a.get('reference',''),'Finding':r.get('question',''),'BAR':r.get('bar_rating',''),'Action':r.get('smart_action',''),'Owner':r.get('action_owner',''),'Due':r.get('action_due_date','')})
    themes=Counter((r['KPI'],r['Finding'],r['BAR']) for r in findings)
    repeat=[{'KPI':k[0],'Finding':k[1],'BAR':k[2],'Occurrences':v} for k,v in themes.most_common()]
    issues=[]
    excluded=[a for a in permits if a not in sc and a not in asc]
    if excluded:issues.append(f'{len(excluded)} permit audits excluded pending role, site or sample-category verification.')
    missing=sum(not r['Owner'] or not r['Action'] or not r['Due'] for r in findings)
    if missing:issues.append(f'{missing} failed questions lack a complete action, owner or due date.')
    if monitoring:issues.append('KPI 4 delivery measures weeks with monitoring audits; actual visits and duty-person obligations require separate evidence.')
    if not rows:issues.append('No non-test audits recorded in this reporting period. This does not prove there was no work.')
    if coverage=='Not assessed':issues.append('KPI 3 Remote Site coverage judgement is awaiting management review.')
    kpis=[{'KPI':f'KPI {i+1}','Title':TITLES[i],'Status':statuses[i],'Submitted':len(data[i]),'Delivery':f'{credits}/{plan} weekly/category credits' if i==0 else f'{ascredits}/{len(weeks)} weeks' if i==1 else f'{len(lead)}/3 engagements this quarter' if i==2 else f'Supervisor {oo}/{len(weeks)}; HSE Adviser {med}/{len(weeks)} monitoring weeks','Conformance %':[c1,c2,c3,c4][i]} for i in range(4)]
    return {'period':f'{year}-{month:02d}','start':str(start),'end':str(end),'kpis':kpis,'datasets':data,'weekly':weekly,'findings':findings,'repeat':repeat,'issues':issues,'credits':credits,'plan':plan,'ascredits':ascredits,'oo':oo,'med':med,'conformances':[c1,c2,c3,c4],'statuses':statuses,'excluded_ids':[a['audit_id'] for a in excluded],'source_ids':sorted({a['audit_id'] for aa in data for a in aa})}


def table(rows,columns=None):
    if not rows:return '<p>No records in this selection.</p>'
    columns=columns or list(rows[0]);esc=lambda v:html.escape(str(v if v is not None else 'Not assessed'))
    return '<table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in columns)+'</tr></thead><tbody>'+''.join('<tr class="'+({'Red':'rag-red','Amber':'rag-amber','Green':'rag-green','Missed':'rag-red','Met':'rag-green','Partial':'rag-amber'}.get(r.get('Status') or r.get('Evidence status'),'rag-neutral'))+'">'+''.join('<td>'+esc(r.get(k,''))+'</td>' for k in columns)+'</tr>' for r in rows)+'</tbody></table>'


def leadership_summary(report,recovery,today=None):
    """Evidence-based summary and suggested responses; does not assign or close actions."""
    today=today or date.today()
    owner_roles={'KPI 1':'Site Leadership','KPI 2':'Operations Director','KPI 3':'General Manager','KPI 4':'Site Leadership / Operations Director','KPI 5':'Operations Director'}
    narrative=[];priorities=[]
    for k in report['kpis']:
        cf=k.get('Conformance %');conf='not assessed' if cf is None else f'{cf:.1f}%'
        if k['KPI']!='KPI 5':narrative.append(f"{k['KPI']}: {k['Delivery']}; whole-audit conformance {conf}; position {k['Status']}.")
        failures=[r for r in report['findings'] if r['KPI']==k['KPI']]
        gaps=[r for r in report['weekly'] if r['KPI']==k['KPI'] and r['Status']=='Missed']
        if gaps:priorities.append({'KPI':k['KPI'],'Accountable role':owner_roles[k['KPI']],'Trigger':f"{len(gaps)} missed weekly/category requirements; {sum(r['Shortfall'] for r in gaps)} samples short",'Suggested leadership response':'Confirm the cause and agree a dated recovery plan; additional audits cannot retrospectively fulfil a missed week.'})
        critical=[r for r in failures if r['BAR']=='BAR 1']
        if critical:priorities.append({'KPI':k['KPI'],'Accountable role':owner_roles[k['KPI']],'Trigger':f'{len(critical)} failed BAR 1 questions','Suggested leadership response':'Verify immediate safety actions and current control effectiveness; confirm accountable owners and closure evidence.'})
    repeats=[r for r in report['repeat'] if r['Occurrences']>1]
    if repeats:narrative.append(f"{len(repeats)} checklist questions failed repeatedly; these require review for recurring control weaknesses, not an assumed root cause.")
    for r in repeats:priorities.append({'KPI':r['KPI'],'Accountable role':owner_roles[r['KPI']],'Trigger':f"Repeated {r['Occurrences']} times: {r['Finding']}",'Suggested leadership response':'Check whether local corrective actions address a shared weakness and target subsequent assurance.'})
    overdue=[r for r in recovery if r.get('Status')!='Closed' and day(r.get('Due')) and day(r['Due'])<today]
    if overdue:narrative.append(f'{len(overdue)} recorded leadership recovery actions are overdue and not marked Closed.')
    if not narrative:narrative.append('No assessed results are available for this selection.')
    return narrative,priorities,overdue


def rota_results(report,today=None):
    today=today or date.today();out=[]
    for row in report.get('rota',[]):
        week=day(row.get('Week'))
        matches=[a for a in report['datasets'][3] if week and day(a['audit_date']) and week<=day(a['audit_date'])<=week+timedelta(days=6) and a['site']==row['Site'] and a['auditor'].strip().casefold()==row['Expected person'].strip().casefold() and str(a['metadata'].get('team','')).strip().casefold()==row['Vessel/team'].strip().casefold() and a['metadata'].get('auditor_role')==row['Role']]
        visit=bool(row.get('Visit reference','').strip())
        status='Met' if matches and visit else 'Partial' if matches or visit else 'Missed' if week and min(week+timedelta(days=6),day(report['end']))<today else 'Pending'
        out.append({**row,'Monitoring audits':len(matches),'Evidence status':status})
    return out


def export_html(report,recovery,commentary,kpi5_note,scope):
    esc=lambda x:html.escape(str(x))
    body='<h1>DEMO ONLY — Control of Work monthly leadership report</h1><p>'+esc(report['period'])+' · '+esc(scope)+' · reporting window '+esc(report['start'])+' to '+esc(report['end'])+'</p><p>Generated from fictional demonstration records. Sample criteria require client agreement. Excess permit samples do not offset a missed week/category. Blank evidence is not treated as conformance.</p>'
    body+='<h2>Completeness and review checks</h2>'+''.join('<p>'+esc(x)+'</p>' for x in report['issues'])
    summary,priorities,overdue=leadership_summary(report,recovery)
    body+='<h2>Automatically generated leadership summary</h2>'+''.join('<p>'+esc(t)+'</p>' for t in summary)
    body+='<h2>Leadership priorities from the audit evidence</h2>'+table(priorities)+'<p>These are suggested responses, not newly assigned actions.</p>'
    body+='<h2>Overdue leadership recovery actions</h2>'+table(overdue)
    body+='<h2>KPI results</h2>'+table(report['kpis'])
    for i in range(1,5):
        key=f'KPI {i}';body+='<section><h2>'+key+' · '+esc(TITLES[i-1])+'</h2>'
        if i in (1,2):body+='<h3>Weekly delivery and shortfalls</h3>'+table([r for r in report['weekly'] if r['KPI']==key])
        if i==3:body+='<h3>Leadership engagements</h3>'+table([{'Date':a['audit_date'],'Leader':a['auditor'],'Team':a['metadata'].get('nui_team') or a['site'],'Audit ID':a['audit_id']} for a in report['datasets'][2]])
        if i==4:body+='<p>Delivery represents monitoring audit evidence, pending verification of actual visits and rota obligations.</p><h3>Recorded monitoring</h3>'+table([{'Date':a['audit_date'],'Site':a['site'],'Auditor':a['auditor'],'Role':a['metadata'].get('auditor_role','Unconfirmed'),'Vessel/team':a['metadata'].get('team',''),'Audit ID':a['audit_id']} for a in report['datasets'][3]])+'<h3>Expected rota obligations and supplied visit evidence</h3>'+table(rota_results(report))
        body+='<h3>Findings and submitted corrective actions</h3>'+table([r for r in report['findings'] if r['KPI']==key])
        body+='<h3>Repeated findings</h3>'+table([r for r in report['repeat'] if r['KPI']==key])
        body+='<h3>Leadership recovery actions</h3>'+table([r for r in recovery if r.get('KPI')==key])
        body+='</section>'
    body+='<section><h2>KPI 5 · Permit-controlled incidents</h2><p>'+esc(kpi5_note)+'</p><p>Incidents cannot be inferred from audit checklists. Imported records below cover the rolling year and may be incomplete; summary counts are not expanded into invented events.</p>'
    events=report.get('incident_rows',[])
    if events:
        monthly=Counter(e['Date'][:7] for e in events);tasks=Counter(e['Task'] or 'Unclassified' for e in events);causes=Counter(e['Root cause'] or 'Unclassified' for e in events)
        for title,counts in [('Monthly incidents',monthly),('Incidents by task',tasks),('Incidents by root cause',causes)]:
            body+='<h3>'+esc(title)+'</h3>'+table([{'Category':k,'Count':v} for k,v in sorted(counts.items())])
        body+='<h3>Supporting incident records</h3>'+table(events)
    else:body+='<p>No incident-level records imported for the rolling reporting period.</p>'
    body+='<h3>KPI 5 leadership actions</h3>'+table([r for r in recovery if r.get('KPI')=='KPI 5'])+'</section>'
    body+='<h2>Management review and interpretation</h2><p>'+esc(commentary or 'Not yet recorded.')+'</p><h2>Traceability</h2><p>Audit IDs used: '+esc(', '.join(report['source_ids']) or 'None')+'</p><p>Excluded permit IDs: '+esc(', '.join(report['excluded_ids']) or 'None')+'</p>'
    return '<!doctype html><html><head><meta charset="utf-8"><title>CoW '+esc(report['period'])+'</title><style>body{font:14px Arial;color:#15394f;margin:32px}h1,h2{background:#15394f;color:white;padding:12px}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:11px}th,td{padding:7px;border:1px solid #ccd8e0;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#15394f;color:white}.rag-red td{background:#fce9e9}.rag-amber td{background:#fff0d2}.rag-green td{background:#e3f4e9}.rag-red td:first-child{border-left:6px solid #cc2027;font-weight:bold}.rag-amber td:first-child{border-left:6px solid #b77700;font-weight:bold}.rag-green td:first-child{border-left:6px solid #087542;font-weight:bold}section{page-break-before:always}@media print{body{margin:8mm}thead{display:table-header-group}tr{break-inside:avoid}}</style></head><body>'+body+'</body></html>'


def report_controls(db,report,scope,kpi5_status):
    import json
    import streamlit as st
    import pandas as pd
    from leadership_views import schema
    schema(db)
    c=db();c.execute('CREATE TABLE IF NOT EXISTS monthly_leadership_review(period TEXT,scope TEXT,commentary TEXT,updated_at TEXT,PRIMARY KEY(period,scope))');c.commit()
    saved=c.execute('SELECT commentary FROM monthly_leadership_review WHERE period=? AND scope=?',(report['period'],scope)).fetchone()
    actions=c.execute('SELECT action_id,kpi,owner_name,action_text,due_date,status,verification_note,history FROM kpi_recovery_actions WHERE reporting_period=? AND scope=? ORDER BY due_date',(report['period'],scope)).fetchall()
    k5=c.execute('SELECT * FROM kpi5 WHERE reporting_month=? AND site=? AND demo=0 ORDER BY submitted_at',(report['period'],'All')).fetchall()
    obligations=c.execute('SELECT obligation_id,site,vessel,week_start,role,person,visit_reference,source_note FROM leadership_obligations WHERE period=? ORDER BY week_start',(report['period'],)).fetchall()
    allowed_sites=set(r['Site / Hub'] for r in report['weekly'] if r['KPI']=='KPI 1')
    report['rota']=[dict(zip(['Obligation ID','Site','Vessel/team','Week','Role','Expected person','Visit reference','Rota source'],r)) for r in obligations if r[1] in allowed_sites]
    events=c.execute('SELECT incident_id,event_date,site,details,task,root_cause,hipo,injury,loc,major_loc,recurring,source_reference FROM cow_incidents ORDER BY event_date').fetchall()
    end=date.fromisoformat(report['end'])
    # The rolling window starts on the first day of the month eleven months earlier.
    month_index=end.year*12+end.month-1-11;start=date(month_index//12,month_index%12+1,1)
    report['incident_rows']=[dict(zip(['Incident ID','Date','Site','Details','Task','Root cause','HiPO','Injury','LOC','Major LOC','Recurring','Source'],r)) for r in events if start<=date.fromisoformat(r[1])<=end]
    c.close()
    recovery=[]
    for r in actions:
        history=json.loads(r[7] or '[]');recovery.append({'Action ID':r[0],'KPI':r[1],'Owner':r[2],'Action':r[3],'Due':r[4],'Status':r[5],'Closure evidence':r[6],'Source':(history or [{}])[-1].get('source_reference','Unlinked')})
    note='No reviewed incident summary entered for this month.'
    if k5:
        row=k5[-1]
        if 'SYNTHETIC UAT' in (row[13] or '').upper():note='Only a synthetic test incident summary is available; excluded from this operational report.'
        else:note=f'Company-wide KPI 5: {kpi5_status}; rolling incidents {row[4]}, previous period {row[5]}, HiPO {row[6]}, significant injuries {row[7]}, LOC {row[8]}, major LOC {row[9]}. Source and interpretation: {row[13]}'
    else:report['issues'].append('KPI 5 needs the incident register or reviewed summary; audits alone cannot populate it.')
    st.subheader('Monthly leadership report from submitted audits')
    st.caption('DEMO ONLY: calculated from fictional records for the selected month and scope. Download the draft after reviewing completeness and management interpretation.')
    if report['issues']:
        with st.expander(f"Completeness / review checks ({len(report['issues'])})",expanded=True):
            for issue in report['issues']:st.write('• '+issue)
    if not any(k['KPI']=='KPI 5' for k in report['kpis']):
        usable=k5 and 'SYNTHETIC UAT' not in (k5[-1][13] or '').upper()
        report['kpis'].append({'KPI':'KPI 5','Title':TITLES[4],'Status':kpi5_status if usable else 'Not assessed','Submitted':None,'Delivery':f'{k5[-1][4]} rolling incidents' if usable else 'Incident input required','Conformance %':None})
    summary,priorities,overdue=leadership_summary(report,recovery)
    st.markdown('#### Automatically generated leadership summary')
    for sentence in summary: st.write(sentence)
    if priorities:
        st.markdown('#### Leadership priorities from the audit evidence')
        st.dataframe(pd.DataFrame(priorities),use_container_width=True,hide_index=True)
        st.caption('Suggested responses for review. They do not automatically create assigned actions.')
    if overdue:
        st.markdown('#### Overdue leadership recovery actions')
        st.dataframe(pd.DataFrame(overdue),use_container_width=True,hide_index=True)
    rota=rota_results(report)
    if rota:
        st.markdown('#### Named rota accountability and evidence')
        st.dataframe(pd.DataFrame(rota),use_container_width=True,hide_index=True)
    st.dataframe(pd.DataFrame(report['kpis']),use_container_width=True,hide_index=True)
    missing=[r for r in report['weekly'] if r['Status']=='Missed']
    if missing:
        st.markdown('#### Missed weekly audit requirements');st.dataframe(pd.DataFrame(missing),use_container_width=True,hide_index=True)
    if report['repeat']:
        st.markdown('#### Repeated findings and emerging themes');st.dataframe(pd.DataFrame(report['repeat']),use_container_width=True,hide_index=True)
    with st.form('monthly-review-'+report['period']+'-'+scope):
        commentary=st.text_area('Management interpretation and monthly priorities',value=saved[0] if saved else '',height=120,help='Record judgement, explanations and priorities. The system supplies the audit results and submitted actions.')
        save=st.form_submit_button('Save monthly review')
    if save:
        from datetime import datetime
        c=db();c.execute('DELETE FROM monthly_leadership_review WHERE period=? AND scope=?',(report['period'],scope));c.execute('INSERT INTO monthly_leadership_review VALUES(?,?,?,?)',(report['period'],scope,commentary,datetime.now().isoformat(timespec='seconds')));c.commit();c.close();st.success('Monthly review saved.')
    content=export_html(report,recovery,commentary,note,scope)
    st.download_button('Download monthly leadership report',content,file_name='CoW_Leadership_Report_'+report['period']+'.html',mime='text/html',key='monthly-html-download')
    st.caption('The self-contained HTML can be opened in a browser and printed to PDF. This is a draft report, not an automatic approval or evidence of visit verification.')

