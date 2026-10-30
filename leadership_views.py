"""Leadership detail views derived from recorded assurance and incident evidence."""
import html
import calendar
import json
import uuid
from datetime import date, timedelta, datetime
import pandas as pd
import streamlit as st
from kpi_rules import reporting_weeks, permit_auditor_role, audit_conformance, permit_sample_category, tbt_auditor_role


def week_starts(year, month):
    return reporting_weeks(year,month)


def week_of(value, year, month):
    try: day=date.fromisoformat(str(value)[:10])
    except (ValueError,TypeError): return None
    if not week_starts(year,month)[0]<=day<=date(year,month,calendar.monthrange(year,month)[1]):return None
    return day-timedelta(days=day.weekday())


def colour_delivery(value):
    if isinstance(value,str) and value.startswith('MISSED'): return 'background-color:#fde4e4;color:#a4262c'
    if isinstance(value,str) and value.startswith('PARTIAL'): return 'background-color:#fff0cd;color:#855600'
    if isinstance(value,str) and value.startswith('MET'): return 'background-color:#e0f2e7;color:#12613c'
    if str(value).lower()=='red':return 'background-color:#cc2027;color:white;font-weight:700'
    if str(value).lower()=='amber':return 'background-color:#f2ad00;color:#302000;font-weight:700'
    if str(value).lower()=='green':return 'background-color:#087542;color:white;font-weight:700'
    return ''


def matrix(records, groups, year, month, targets):
    rows=[]
    for group in groups:
        for category,target in targets(group):
            row={'Site / Hub':group,'Sample category':category,'Weekly target':target}
            selected=[a for a in records if a['site']==group and (category=='All permits' or permit_sample_category(a)==category)]
            for monday in week_starts(year,month):
                count=sum(week_of(a['audit_date'],year,month)==monday for a in selected)
                label='MET' if count>=target else 'PARTIAL' if count else 'MISSED'
                row[f"WK{monday.isocalendar().week:02d}"]=f'{label} {count}/{target}'
            row['Recorded auditors']=', '.join(sorted({a['auditor'] for a in selected if a['auditor']}))
            rows.append(row)
    return pd.DataFrame(rows)


def show_matrix(frame):
    if frame.empty: st.info('No reporting groups available.'); return
    st.dataframe(frame.style.map(colour_delivery),use_container_width=True,hide_index=True)


def findings(records):
    rows=[]
    for a in records:
        for r in a['responses']:
            if str(r.get('response','')).lower()!='no':continue
            rows.append({'Source reference':a['audit_id']+' / '+r.get('item',''),'Date':a['audit_date'],'Site / Hub':a['site'],'Permit / POP':a.get('reference',''),'Auditor':a['auditor'],'Question / expected control':r.get('question',''),'BAR':r.get('bar_rating',''),'Corrective action':r.get('smart_action',''),'Owner':r.get('action_owner',''),'Due':r.get('action_due_date','')})
    if rows:
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.caption('The checklist question states the expected control. Procedure clauses are not inferred; add a verified clause to the linked recovery action when required.')
    else:st.success('No recorded No responses in these eligible audits.')


def outcomes(records):
    scored=[a for a in records if any(str(r.get('response','')).lower() in ('yes','no') for r in a['responses'])]
    passed=sum(not any(str(r.get('response','')).lower()=='no' for r in a['responses']) for a in scored)
    a,b,c=st.columns(3);a.metric('Conformant audits',passed);b.metric('Non-conformant audits',len(scored)-passed);c.metric('Conformance',f'{100*passed/len(scored):.1f}%' if scored else 'Not assessed')
    st.caption('One applicable No makes the whole audit non-conformant. All-N/A audits are excluded from conformance.')


def schema(db):
    c=db()
    c.execute('CREATE TABLE IF NOT EXISTS leadership_obligations(obligation_id TEXT PRIMARY KEY,period TEXT,site TEXT,vessel TEXT,week_start TEXT,role TEXT,person TEXT,visit_reference TEXT,source_note TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS cow_incidents(incident_id TEXT PRIMARY KEY,event_date TEXT,site TEXT,details TEXT,task TEXT,root_cause TEXT,hipo INTEGER,injury TEXT,loc INTEGER,major_loc INTEGER,recurring INTEGER,source_reference TEXT)')
    c.commit();c.close()


def role_evidence(db, records, year, month, sites, role_map):
    if not sites:
        st.info('Select a Remote Site group to record Remote Site rota obligations.'); return
    period=f'{year:04d}-{month:02d}'
    c=db();raw=c.execute('SELECT * FROM leadership_obligations WHERE period=? ORDER BY week_start,vessel,role,person',(period,)).fetchall();c.close()
    keys=['id','period','site','vessel','week','role','person','visit_reference','source_note']
    roster=[dict(zip(keys,r)) for r in raw if r[2] in sites]
    if roster:
        out=[]
        for r in roster:
            matches=[a for a in records if a['site']==r['site'] and a['auditor'].strip().casefold()==r['person'].strip().casefold() and str((a.get('metadata') or {}).get('team','')).strip().casefold()==r['vessel'].strip().casefold() and str(week_of(a['audit_date'],year,month))==r['week'] and tbt_auditor_role(a,role_map)==r['role']]
            status='MET' if matches and r['visit_reference'].strip() else 'PARTIAL' if matches or r['visit_reference'].strip() else 'MISSED'
            out.append({'Site / Hub':r['site'],'Vessel / team':r['vessel'],'Week':r['week'],'Required role':r['role'],'Expected person':r['person'],'Audits recorded':len(matches),'Visit evidence':r['visit_reference'],'Status':status,'Obligation reference':r['id']})
        left,right=st.columns(2)
        for container,role in ((left,'Operations Supervisor'),(right,'HSE Adviser')):
            with container:
                st.markdown('#### '+role+' | ROTA COVERAGE AND WEEKLY AUDIT DELIVERY')
                selected_rows=[r for r in out if r['Required role']==role]
                if selected_rows: show_matrix(pd.DataFrame(selected_rows).drop(columns='Required role'))
                else: st.info('No rota obligations entered for this role.')
        st.caption('Met requires both recorded monitoring and a supplied visit reference. Partial means one is missing. Name, vessel/team, role, site and reporting week must match; no matching record means no evidence recorded here, not proof no visit occurred.')
    else:st.info('No approved rota obligations entered. Named missed visits cannot be inferred from the people who submitted audits.')
    with st.expander('Record or update a weekly rota obligation'):
        selected=st.selectbox('Rota obligation',['New obligation']+[r['id'] for r in roster],key='obligation-selection')
        current=next((r for r in roster if r['id']==selected),{})
        with st.form('rota-'+selected):
            site=st.selectbox('Obligation Remote Site group',sorted(sites),index=sorted(sites).index(current['site']) if current else 0)
            vessel=st.text_input('Vessel / team on duty',value=current.get('vessel',''))
            weeks=week_starts(year,month); week=st.selectbox('Reporting week',weeks,index=weeks.index(date.fromisoformat(current['week'])) if current else 0,format_func=lambda d:f'WK{d.isocalendar().week:02d} / {d}')
            roles=['Operations Supervisor','HSE Adviser'];role=st.selectbox('Expected role',roles,index=roles.index(current['role']) if current else 0)
            person=st.text_input('Person expected to complete monitoring',value=current.get('person',''))
            reference=st.text_input('Verified visit reference, if completed',value=current.get('visit_reference',''))
            source=st.text_input('Rota / handover source',value=current.get('source_note',''))
            save=st.form_submit_button('Save rota obligation')
        if save:
            if not all(x.strip() for x in (person,vessel,source)):st.error('Enter the expected person, vessel/team and rota source.')
            else:
                c=db()
                if current:c.execute('UPDATE leadership_obligations SET site=?,vessel=?,week_start=?,role=?,person=?,visit_reference=?,source_note=? WHERE obligation_id=?',(site,vessel.strip(),str(week),role,person.strip(),reference.strip(),source.strip(),current['id']))
                else:c.execute('INSERT INTO leadership_obligations VALUES(?,?,?,?,?,?,?,?,?)',('OBL-'+uuid.uuid4().hex[:8].upper(),period,site,vessel.strip(),str(week),role,person.strip(),reference.strip(),source.strip()))
                c.commit();c.close();st.rerun()


def validate_incidents(frame):
    columns=['incident_id','event_date','site','details','task','root_cause','hipo','injury','loc','major_loc','recurring','source_reference']
    if not set(columns).issubset(frame.columns):raise ValueError('Required CSV columns: '+', '.join(columns))
    frame=frame[columns].fillna('').astype(str).apply(lambda col:col.str.strip())
    if frame.empty or frame.incident_id.duplicated().any():raise ValueError('Provide unique incident IDs and at least one row.')
    rows=[]
    for row in frame.to_dict('records'):
        for key in ('incident_id','event_date','site','details','source_reference'):
            if not row[key]:raise ValueError('Missing '+key)
        date.fromisoformat(row['event_date'])
        for key in ('hipo','loc','major_loc','recurring'):
            if row[key] not in ('0','1'):raise ValueError(key+' must be 0 or 1.')
            row[key]=int(row[key])
        if row['major_loc'] and not row['loc']:raise ValueError('Major LOC must also be marked LOC.')
        if row['injury'] not in ('None','FAC','MTC','RWC','LTI','Fatality'):raise ValueError('Injury must be None, FAC, MTC, RWC, LTI or Fatality.')
        rows.append(tuple(row[k] for k in columns))
    return rows


def incident_view(db, end):
    start=(end.replace(day=1)-pd.DateOffset(months=11)).date()
    c=db();raw=c.execute('SELECT * FROM cow_incidents ORDER BY event_date').fetchall();c.close()
    columns=['Incident ID','Date','Site','Details','Task','Root cause','HiPO','Injury','LOC','Major LOC','Recurring','Source']
    frame=pd.DataFrame(raw,columns=columns)
    if not frame.empty:
        frame['Date']=pd.to_datetime(frame['Date'])
        frame=frame[(frame.Date.dt.date>=start)&(frame.Date.dt.date<=end)]
    st.caption(f'Company-wide incident detail: {start:%d %b %Y} to {end:%d %b %Y}. Import only incidents confirmed as occurring during permitted activities. Summary KPI 5 RAG remains separate until definitions and source completeness are agreed.')
    if frame.empty:st.info('No incident-level records for this rolling period. Summary counts are not expanded into invented events.')
    else:
        a,b,c,d=st.columns(4);a.metric('Recorded incidents',len(frame));b.metric('HiPOs',int(frame.HiPO.sum()));c.metric('LOC incidents',int(frame.LOC.sum()));d.metric('Major LOC',int(frame['Major LOC'].sum()))
        frame['Month']=frame.Date.dt.to_period('M').astype(str)
        trend=frame.groupby('Month').agg(Incidents=('Incident ID','count'),LOC=('LOC','sum'),HiPO=('HiPO','sum')).reindex(pd.period_range(start,end,freq='M').astype(str),fill_value=0)
        st.markdown('#### Rolling 12-month incident trend');st.bar_chart(trend)
        st.caption('Series overlap: LOC and HiPO are subsets of incidents and must not be added together. Zero means no imported records, subject to source completeness.')
        st.markdown('#### Significant-injury records');st.dataframe(frame[frame.Injury.isin(['MTC','RWC','LTI','Fatality'])][['Incident ID','Date','Site','Details','Injury','Source']],use_container_width=True,hide_index=True)
        st.markdown('#### Loss of containment and recurring themes');st.dataframe(frame[frame.LOC==1][['Incident ID','Date','Site','Details','Task','Recurring','Source']],use_container_width=True,hide_index=True)
        for label in ('Task','Root cause'):
            st.markdown('#### Incidents by '+label.lower())
            counts=frame[label].replace('','Unclassified').value_counts().rename_axis(label).to_frame('Incidents');st.bar_chart(counts,horizontal=True)
        st.markdown('#### Supporting incident records');st.dataframe(frame.drop(columns='Month'),use_container_width=True,hide_index=True)
    with st.expander('Import reviewed permitted-activity incidents'):
        st.caption('CSV: incident_id,event_date,site,details,task,root_cause,hipo,injury,loc,major_loc,recurring,source_reference. Dates YYYY-MM-DD; flags 0/1; injury None/FAC/MTC/RWC/LTI/Fatality. Root cause is the reviewed primary category; leave unconfirmed categories blank.')
        st.download_button('Download incident CSV headings','incident_id,event_date,site,details,task,root_cause,hipo,injury,loc,major_loc,recurring,source_reference\n',file_name='cow_incident_headings.csv',mime='text/csv')
        upload=st.file_uploader('Incident detail CSV',type=['csv'],key='incident-detail-csv')
        if st.button('Import incident records'):
            if upload is None:st.error('Choose a CSV first.')
            else:
                c=None
                try:
                    rows=validate_incidents(pd.read_csv(upload,dtype=str,keep_default_na=False));c=db()
                    existing={r[0]:tuple(r) for r in c.execute('SELECT * FROM cow_incidents').fetchall()}
                    for row in rows:
                        if row[0] in existing and existing[row[0]]!=row:raise ValueError('Existing incident differs: '+row[0]+'. Reconcile the source before importing.')
                    for row in rows:
                        if row[0] not in existing:c.execute('INSERT INTO cow_incidents VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',row)
                    c.commit();c.close();c=None;st.rerun()
                except Exception as exc:
                    if c is not None:c.connection.rollback();c.close()
                    st.error(str(exc))


REPORT_TITLES=['PERMIT QUALITY, SITE CONTROLLER','PERMIT QUALITY, ASSET SUPERINTENDENT','CoW LEADERSHIP ENGAGEMENT','LEVEL 4 CONFORMANCE AND FINDINGS','Incident Registers DURING PERMITTED ACTIVITIES | ROLLING 12-MONTH TREND']
PURPOSES=["Site Controllers sample the quality of active permits, including routine activity, prior to issue, recording permits sampled and non-conformance against SSoW requirements.","Asset Superintendents sample the quality of active permits between Permit Authorisation and Issued stages, recording permits sampled and non-conformance against SSoW requirements.","Effective supervision is consistently demonstrated at the worksite through regular Remote Site team engagement, providing visibility, assurance and oversight of work execution.","Operations Supervisor and HSE Adviser complete weekly Remote Site visits and Level 4 monitoring to verify TBT, permit and worksite-control effectiveness.","Permit-controlled activities resulting in incidents may indicate hazards are incorrectly identified, controls are ineffective, or work is not executed safely as authorised."]


def report_styles():
    st.markdown("""<style>
.lr-header{background:#15394f;color:white;padding:14px 18px;margin:18px 0 14px}.lr-header small{font-size:10px;font-weight:700}.lr-header h3{color:white;font-size:19px;margin:3px 0}.lr-header p{font-size:12px;margin:3px 0;color:#e3edf4}
.lr-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:10px 0 18px}.lr-tile{border:1px solid #d5dfe5;border-radius:7px;padding:13px;background:#fff}.lr-tile small{display:block;font-size:10px;font-weight:700;color:#334b60}.lr-tile strong{display:block;font-size:23px;margin:8px 0}.lr-tile span{font-size:11px;display:block}.lr-tile.red{background:#fce9e9;color:#a22429}.lr-tile.amber{background:#fff0d2;color:#865900}.lr-tile.green{background:#e3f4e9;color:#12643f}.lr-bands{display:grid;grid-template-columns:140px repeat(3,1fr);gap:8px;align-items:stretch;font-size:11px;margin:16px 0 24px}.lr-bands>div,.lr-bands>b{padding:10px;border:1px solid #d4dfe4;border-radius:5px}.lr-bands .green{background:#e3f4e9;color:#12643f}.lr-bands .amber{background:#fff0d2;color:#865900}.lr-bands .red{background:#fce9e9;color:#a22429}@media(max-width:700px){.lr-bands{grid-template-columns:1fr}.lr-header h3{font-size:16px}}
.lr-tile{border-top:5px solid #15394f;box-shadow:0 2px 8px #15394f12}.lr-tile.red{border-top-color:#cc2027}.lr-tile.amber{border-top-color:#b76b00}.lr-tile.green{border-top-color:#087542}.lr-tile.overall.red{background:#cc2027;color:#fff;border-color:#cc2027}.lr-tile.overall.amber{background:#f2ad00;color:#302000;border-color:#b77700}.lr-tile.overall.green{background:#087542;color:#fff;border-color:#087542}.lr-tile.overall small,.lr-tile.overall span{color:inherit}.lr-tile.overall strong{font-size:30px;font-weight:900}.lr-header{border-left:7px solid #2d91c9}.lr-bands .red{border-top:5px solid #cc2027}.lr-bands .amber{border-top:5px solid #b77700}.lr-bands .green{border-top:5px solid #087542}
</style>""",unsafe_allow_html=True)


def report_header(number,action=False):
    title=("ACTION: " if action else "")+f"KPI {number} | "+REPORT_TITLES[number-1]
    st.markdown('<div class="lr-header"><small>CONTROL OF WORK DASHBOARD</small><h3>'+html.escape(title)+'</h3><p>Purpose: '+html.escape(PURPOSES[number-1])+'</p></div>',unsafe_allow_html=True)


def report_tiles(items):
    cells=[]
    for label,value,status,detail in items:
        tone=str(status).lower() if status in ('Red','Amber','Green') else 'neutral'
        emphasis=' overall' if str(label).startswith('OVERALL KPI') else ''
        cells.append('<div class="lr-tile '+tone+emphasis+'"><small>'+html.escape(str(label))+'</small><strong>'+html.escape(str(value))+'</strong><span>'+html.escape(str(detail))+'</span></div>')
    st.markdown('<div class="lr-tiles">'+''.join(cells)+'</div>',unsafe_allow_html=True)


def tolerance_strip(number):
    if number in (1,2):bands=['≥100% delivery AND ≥90% conformance','70–<100% delivery AND/OR 70–<90% conformance','<70% delivery OR <70% conformance']
    elif number==3:bands=['3+ engagements/quarter AND ≥90% conformance; reasonable coverage','2 engagements AND/OR 70–<90% conformance; review coverage and themes','≤1 engagement at quarter end OR <70% conformance']
    elif number==4:bands=['Supervisor/Medic 100%; Site Manager quarterly target and reasonable coverage; ≥90% conformance, no repeat/significant findings','Supervisor 50–99%; Medic 75–99%; Site Manager timing/coverage; 70–89% or minor themes; suitable justification required','Supervisor/Medic <50%; Site Manager repeated missed quarters; <70%, significant/repeat findings or unsuitable justification']
    else:bands=['No increasing trend; no HiPO/significant injury or repeat LOC','Increasing trend; single HiPO/significant injury/LOC or repeat event theme','Significant increase; multiple severe events, major LOC or recurring control failures']
    st.markdown('<div class="lr-bands"><b>TARGETS &amp; TOLERANCES</b>'+''.join('<div class="'+tone+'"><b>'+label+'</b><br>'+html.escape(text)+'</div>' for tone,label,text in zip(['green','amber','red'],['GREEN','AMBER','RED'],bands))+'</div>',unsafe_allow_html=True)


def kpi5_reference_actions():
    """September report actions; reference guidance, not newly assigned actions."""
    st.caption('September 2026 report reference — Operations Director intervention. Confirm relevance to the selected period and record named owners, deadlines and evidence in the recovery tracker.')
    st.markdown('**Targeted LOC review:** Determine why Diving / ROV hydraulic and integrity-related containment failures are recurring, test whether existing equipment assurance and work-planning controls are effective, and implement common preventative actions across assets and contractors.')
    st.markdown('**Sites to target Level 4 assurance:** Focus on permits for **Cold Work / Mechanical activities**, checking plant / equipment condition and whether work is being executed as authorised.')
    st.markdown('**Root cause focus:** Use the **CoW Leadership Engagement Tool and Work Safety Culture** to direct management safety visits towards **Equipment / Safety System Condition, Equipment Use, Procedure / Rule Compliance and Integrity / Corrosion**. Look for and discuss these weaknesses before the next incident occurs.')
    st.caption('Source rating: Amber; 0 HiPOs, 2 significant injuries, 0 major LOC and 4 recurring failures. The reported Amber conflicts with the written Red triggers; it is a reported source position pending clarification, not a recalculated rating.')


def report_week_matrix(records,groups,year,month):
    rows=[]
    for group,(routine,new) in groups.items():
        row={'Site':group}
        for week in week_starts(year,month):
            for label,category,target in [('NEW*','Non-routine',new),('ROUTINE','Routine',routine)]:
                count=sum(a['site']==group and permit_sample_category(a)==category and week_of(a['audit_date'],year,month)==week for a in records)
                row[f'WK{week.isocalendar().week:02d} {label}']=f'{count}/{target}'
        rows.append(row)
    if rows:
        frame=pd.DataFrame(rows)
        def shade(value):
            try:actual,target=map(int,str(value).split('/'));return 'background-color:#e0f2e7;color:#12613c' if actual>=target else 'background-color:#fde4e4;color:#a4262c'
            except (ValueError,TypeError):return ''
        st.dataframe(frame.style.map(shade),use_container_width=True,hide_index=True)
    st.caption('*NEW retains the presentation heading; counted samples require an explicit non-routine category. Each cell is actual/required. Excess samples do not offset another week/category.')


def render(db, recovery, period, scope, year, month, groups, sc, asc, qlead, tbt, tmap, statuses, measures):
    schema(db)
    report_styles()
    st.subheader('KPI 1–5 Detailed Reports')
    st.caption('Reporting weeks start on Monday and include the opening week intersecting the month, ending at the selected month end. September 2026 therefore uses WK36–40, from 31 August to 30 September. Headline plans and weekly matrices use the same basis; an opening-week record can appear in two monthly views and monthly totals must not be added as unique annual activity.')
    titles=['KPI 1 · Site Controller','KPI 2 · Asset Superintendent','KPI 3 · Leadership engagements','KPI 4 · Site Leadership Remote Site','KPI 5 · Incidents']
    tabs=st.tabs(titles)
    owners=['Site Leadership','Operations Director','General Manager','Site Leadership / Operations Director','Operations Director']
    datasets=[sc,asc,qlead,tbt,[]]
    for i,tab in enumerate(tabs):
        with tab:
            report_header(i+1)
            scored=[a for a in datasets[i] if any(str(r.get('response','')).lower() in ('yes','no') for r in a['responses'])]
            cf=audit_conformance(scored,rounded=False)
            conf='Not assessed' if cf is None else f'{cf:.1f}%'
            tiles=[('OVERALL KPI '+str(i+1),statuses[i],statuses[i],'Selected reporting period'),('AUDIT CONFORMANCE',conf,'Green' if cf is not None and cf>=90 else 'Red' if cf is not None and cf<70 else 'Amber' if cf is not None else '', 'Any applicable No fails the audit'),('REQUIRED RESPONSE',owners[i],statuses[i],'Review findings and missed targets')]
            if i==0:
                plan=sum(sum(v) for v in groups.values())*len(week_starts(year,month));credited=measures.get('monthly_report',{}).get('credits',len(sc));tiles.insert(1,('AUDIT DELIVERY',f'{credited}/{plan}','Green' if plan and credited>=plan else 'Amber' if plan and credited/plan>=.7 else 'Red','Weekly/category credits; raw samples '+str(len(sc))))
            elif i==1:
                credited=measures.get('monthly_report',{}).get('ascredits',len(asc));tiles.insert(1,('AUDIT DELIVERY',f'{credited}/{len(week_starts(year,month))}','Green' if credited>=len(week_starts(year,month)) else 'Amber' if credited/len(week_starts(year,month))>=.7 else 'Red','Weeks met; raw samples '+str(len(asc))))
            elif i==2:tiles.insert(1,('ENGAGEMENT DELIVERY',f'{len(qlead)}/3',statuses[i],'Completed / quarterly target'))
            if i!=4:report_tiles(tiles)
            if i==0:
                st.markdown('#### PLANNED AUDITS VS COMPLETED');report_week_matrix(sc,groups,year,month)
                st.markdown('#### SITE CONTROLLER AUDITORS | RECORDED IN DATA SET')
                st.dataframe(pd.DataFrame([{'Site':g,'Recorded Site Controllers':', '.join(sorted({a['auditor'] for a in sc if a['site']==g})) or 'None recorded'} for g in groups]),use_container_width=True,hide_index=True)
                report_header(1)
                st.caption('Non-routine is the explicit Permit Register sample category. A New WCC alone does not prove that category. Excess samples in one week do not fill another week’s missed cells.')
                outcomes(sc)
            elif i==1:
                st.markdown('#### MONTHLY AUDIT DELIVERY')
                history=measures.get('all_a',[]);pmap=measures.get('pmap',{})
                prev=date(year,month,1)-timedelta(days=1)
                monthly=[]
                for first in (prev.replace(day=1),date(year,month,1)):
                    end=date(first.year,first.month,calendar.monthrange(first.year,first.month)[1])
                    eligible=[a for a in history if a['form_name']=='Control of Work: Permit Quality' and a['site'] in groups and permit_auditor_role(a,pmap)=='Asset Superintendent' and permit_sample_category(a)!='Unclassified' and week_starts(first.year,first.month)[0]<=date.fromisoformat(a['audit_date'])<=end]
                    target=len(week_starts(first.year,first.month));monthly.append({'Month':first.strftime('%B %Y'),'Completed':len(eligible),'Planned':target,'Delivery %':round(100*len(eligible)/target,1)})
                st.dataframe(pd.DataFrame(monthly),use_container_width=True,hide_index=True)
                show_matrix(matrix([dict(a,site='All sites') for a in asc],['All sites'],year,month,lambda g:[('All permits',1)]));outcomes(asc)
            elif i==2:
                a,b,c=st.columns(3);a.metric('Quarter target',3);b.metric('Completed',len(qlead));c.metric('Outstanding',max(0,3-len(qlead)));outcomes(qlead)
                rows=[]
                for audit in qlead:
                    meta=audit.get('metadata') or {}
                    positives=[r.get('question','') for r in audit['responses'] if str(r.get('response','')).lower()=='yes']
                    improvements=[r.get('question','') for r in audit['responses'] if str(r.get('response','')).lower()=='no']
                    rows.append({'Audit ID':audit['audit_id'],'Date':audit['audit_date'],'Leader':audit['auditor'],'Team':meta.get('nui_team') or audit['site'],'Controls verified':'; '.join(positives),'Opportunities / gaps':meta.get('opportunities_for_improvement') or '; '.join(improvements),'Actions agreed':'; '.join(r.get('smart_action','') for r in audit['responses'] if r.get('smart_action'))})
                if rows:st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                else:st.info('No eligible leadership engagements recorded.')
            elif i==3:
                st.caption('KPI 4 follows the illustrative demo criteria, including verified Visit Register visits, Site Manager quarterly requirements, coverage, findings and missed-target justification. Monitoring audit weeks below are supporting evidence, not verified visit counts.')
                left,right=st.columns(2)
                for container,role in ((left,'Operations Supervisor'),(right,'HSE Adviser')):
                    rows=[]
                    for w in week_starts(year,month):
                        aa=[a for a in tbt if tbt_auditor_role(a,tmap)==role and week_of(a['audit_date'],year,month)==w]
                        rows.append({'Week':f'WK{w.isocalendar().week:02d}','Recorded auditors':', '.join(sorted({a['auditor'] for a in aa})) or 'None evidenced','Audits':len(aa),'Visit verification':'See rota evidence below'})
                    with container:
                        st.markdown('#### '+role+' | AUDITS COMPLETED BY WEEK')
                        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                st.caption('Recorded monitoring audits are not automatically verified visits. Non-Remote Site submissions are excluded.')
                role_evidence(db,tbt,year,month,set(groups)&{'North Remote Sites','South Remote Sites'},tmap);outcomes(tbt)
            else:
                c=db();summary=c.execute('SELECT * FROM kpi5 WHERE reporting_month=? AND site=? AND demo=0 ORDER BY submitted_at',(period,'All')).fetchall();c.close()
                k5=summary[-1] if summary else None
                report_tiles([('OVERALL KPI 5',statuses[i],statuses[i],'Rolling 12-month position'),('HiPOs',k5[6] if k5 else 'Not entered','','Recorded summary'),('SIGNIFICANT INJURIES',k5[7] if k5 else 'Not entered','','Definition subject to reconciliation'),('MAJOR LOC / RECURRING FAILURES',f'{k5[9]} / {k5[11]}' if k5 else 'Not entered','','Recorded summary'),('REQUIRED RESPONSE','Operations Director',statuses[i],'Targeted campaigns, assurance or focused reviews')])
                incident_view(db,date(year,month,calendar.monthrange(year,month)[1]))
                if k5 and k5[13]:st.markdown('#### LEADERSHIP INTERPRETATION');st.write(k5[13])
            if i<4:
                st.markdown('#### AUDIT FINDINGS');findings(datasets[i])
            tolerance_strip(i+1)
            report_header(i+1,action=True)
            st.markdown('#### '+owners[i]+' action')
            response=('No intervention triggered by the assessed KPI.' if statuses[i]=='Green' else 'Validate the target, eligibility and source evidence before final judgement.' if statuses[i] not in ('Red','Amber') else 'Review the shortfall and agree targeted corrective actions.' if statuses[i]=='Amber' else 'Immediate leadership intervention; record the recovery response and agreed deadlines.')
            st.info(response)
            if i==4:
                with st.expander('KPI 5 targeted leadership actions | September report reference',expanded=period=='2026-09'):
                    kpi5_reference_actions()
            recovery(period,scope,f'KPI {i+1}')
            tolerance_strip(i+1)


