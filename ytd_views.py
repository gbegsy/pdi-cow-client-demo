"""Full-calendar-month YTD reporting from recorded demo audits."""
import calendar
from datetime import date, timedelta


def full_months(audits, year, selected_month, site='All', today=None):
    today=today or date.today()
    last_closed=today.replace(day=1)-timedelta(days=1)
    cutoff=min(selected_month,12 if year<last_closed.year else last_closed.month if year==last_closed.year else 0)
    source=[]
    for audit in audits:
        try: day=date.fromisoformat(str(audit.get('audit_date',''))[:10])
        except ValueError: continue
        if day.year==year and day.month<=cutoff and (site=='All' or audit.get('site')==site):
            source.append(audit)
    return cutoff,source,[(month,[a for a in source if int(a['audit_date'][5:7])==month]) for month in range(1,cutoff+1)]


def render(audits, year, selected_month, asset, site):
    import streamlit as st
    import pandas as pd
    from kpi_rules import audit_conformance, checklist_conformance, format_percentage
    cutoff,source,months=full_months(audits,year,selected_month,site)
    st.subheader('Year to date · Full months')
    if not cutoff:
        st.info('No completed calendar months are available for this selection.')
        return
    st.caption(f'1 January–{calendar.monthrange(year,cutoff)[1]} {calendar.month_name[cutoff]} {year} · Asset: {asset} · Site / Hub: {site}. The current unfinished month is excluded.')
    st.caption('FICTIONAL DEMONSTRATION · January–October records illustrate full-month reporting. Each audit is counted once by its calendar audit date; weeks crossing a month boundary do not duplicate audits.')
    applicable=[r for a in source for r in a.get('responses',[]) if r.get('response') in {'Yes','No'}]
    no=sum(r['response']=='No' for r in applicable)
    a,b=st.columns(2)
    a.metric('YTD audits completed',len(source))
    b.metric('Question conformance',format_percentage(checklist_conformance(source,rounded=False)))
    a.metric('Whole-audit conformance',format_percentage(audit_conformance(source,rounded=False)))
    b.metric('BAR 1 non-conformances',sum(r['response']=='No' and r.get('bar_rating')=='BAR 1' for r in applicable))
    st.caption(f'{len(applicable)-no} Yes / {len(applicable)} applicable answers · N/A excluded. YTD rates use their underlying denominators, not an average of monthly percentages.')
    records=[]
    for month,rows in months:
        permits=[a for a in rows if a.get('form_name')=='Control of Work: Permit Quality']
        tbt=[a for a in rows if 'Toolbox Talk' in a.get('form_name','')]
        lead=[a for a in rows if 'Leadership Engagement' in a.get('form_name','')]
        answers=[r for a in rows for r in a.get('responses',[]) if r.get('response') in {'Yes','No'}]
        records.append({'Month':f'{calendar.month_name[month]} {year}','Audits completed':len(rows),'Permit audits':len(permits),'TBT / Permit / POP audits':len(tbt),'Leadership engagements':len(lead),'Question conformance':format_percentage(checklist_conformance(rows,rounded=False)),'Whole-audit conformance':format_percentage(audit_conformance(rows,rounded=False)),'BAR 1 non-conformances':sum(r['response']=='No' and r.get('bar_rating')=='BAR 1' for r in answers),'No responses':sum(r['response']=='No' for r in answers)})
    frame=pd.DataFrame(records)
    st.markdown('#### Every full month')
    st.dataframe(frame,hide_index=True,use_container_width=True)
    st.vega_lite_chart(frame,{"mark":{"type":"bar","color":"#147c87","cornerRadiusTopLeft":4,"cornerRadiusTopRight":4},"encoding":{"x":{"field":"Month","type":"ordinal","sort":frame["Month"].tolist(),"axis":{"labelAngle":-35}},"y":{"field":"Audits completed","type":"quantitative"},"tooltip":[{"field":"Month","type":"nominal"},{"field":"Audits completed","type":"quantitative"}]}},use_container_width=True)
    st.download_button('Download full-month YTD data',frame.to_csv(index=False).encode('utf-8-sig'),f'CoW_YTD_{year}_through_{cutoff:02d}.csv','text/csv',key='ytd-download')
    st.caption('Conformance describes the audit sample. Monthly KPI delivery and quarterly engagement/visit requirements retain their own criteria in Detailed KPI Reports. Rolling 12-month incident snapshots are not added together as a YTD incident total.')


def audit_outcomes(audits):
    """Classify each audit once; no applicable answers is unscored."""
    counts={'Conformant':0,'Non-conformant':0,'Unscored':0}
    for audit in audits:
        answers=[r.get('response') for r in audit.get('responses',[]) if r.get('response') in {'Yes','No'}]
        counts['Non-conformant' if 'No' in answers else 'Conformant' if answers else 'Unscored']+=1
    return counts


def cumulative_rows(audits,year,selected_month,site='All',today=None):
    from kpi_rules import audit_conformance, checklist_conformance
    cutoff,source,months=full_months(audits,year,selected_month,site,today)
    running=[]
    output=[]
    for month,rows in months:
        running.extend(rows)
        answers=[r for a in running for r in a.get('responses',[]) if r.get('response') in {'Yes','No'}]
        outcomes=audit_outcomes(running)
        output.append({
            'Through month':f'{calendar.month_name[month]} {year}',
            'Audits this month':len(rows),
            'Cumulative audits':len(running),
            'Cumulative conformant audits':outcomes['Conformant'],
            'Cumulative non-conformant audits':outcomes['Non-conformant'],
            'Cumulative unscored audits':outcomes['Unscored'],
            'Cumulative permit audits':sum(a.get('form_name')=='Control of Work: Permit Quality' for a in running),
            'Cumulative TBT / Permit / POP':sum('Toolbox Talk' in a.get('form_name','') for a in running),
            'Cumulative leadership engagements':sum('Leadership Engagement' in a.get('form_name','') for a in running),
            'Cumulative question conformance':checklist_conformance(running,rounded=False),
            'Cumulative whole-audit conformance':audit_conformance(running,rounded=False),
            'Cumulative BAR 1 non-conformances':sum(r['response']=='No' and r.get('bar_rating')=='BAR 1' for r in answers),
        })
    return cutoff,output


def render_cumulative(audits,year,selected_month,asset,site):
    import streamlit as st
    import pandas as pd
    from kpi_rules import format_percentage
    cutoff,records=cumulative_rows(audits,year,selected_month,site)
    st.subheader('YTD Audits · Cumulative')
    if not records:
        st.info('No completed calendar months in this selection.')
        return
    st.caption(f'January–{calendar.month_name[cutoff]} {year} · Asset: {asset} · Site / Hub: {site} · Fictional demo records.')
    st.write('Each row adds the full month to the previous total. The current unfinished month is excluded; each audit is counted once by its audit date.')
    latest=records[-1]
    a,b,c=st.columns(3)
    a.metric('Cumulative audits',latest['Cumulative audits'])
    b.metric('Conformant audits',latest['Cumulative conformant audits'])
    c.metric('Non-conformant audits',latest['Cumulative non-conformant audits'])
    st.caption(f"{len(records)} completed months · Latest full month: {calendar.month_name[cutoff]}. Conformant = at least one applicable answer and no No answers. Non-conformant = at least one No. N/A answers are excluded.")
    if latest['Cumulative unscored audits']:
        st.info(f"{latest['Cumulative unscored audits']} audits have no applicable Yes/No answers and are shown separately as unscored.")
    chart=pd.DataFrame(records)
    outcome_columns={'Cumulative conformant audits':'Conformant','Cumulative non-conformant audits':'Non-conformant','Cumulative unscored audits':'Unscored'}
    plot=chart[['Through month']+list(outcome_columns)].melt(id_vars=['Through month'],value_vars=list(outcome_columns),var_name='Outcome',value_name='Cumulative audits')
    plot['Outcome']=plot['Outcome'].map(outcome_columns)
    st.vega_lite_chart(plot,{'mark':{'type':'bar'},'encoding':{'x':{'field':'Through month','type':'ordinal','sort':chart['Through month'].tolist(),'axis':{'labelAngle':-35}},'y':{'field':'Cumulative audits','type':'quantitative','stack':'zero'},'color':{'field':'Outcome','type':'nominal','scale':{'domain':['Conformant','Non-conformant','Unscored'],'range':['#16865b','#bd3d43','#8795a1']},'legend':{'orient':'top'}},'tooltip':[{'field':'Through month','type':'nominal'},{'field':'Outcome','type':'nominal'},{'field':'Cumulative audits','type':'quantitative'}]}},use_container_width=True)
    display=chart.copy()
    for column in ['Cumulative question conformance','Cumulative whole-audit conformance']:
        display[column]=display[column].map(format_percentage)
    st.markdown('#### Cumulative position through every full month')
    st.dataframe(display,hide_index=True,use_container_width=True)
    st.download_button('Download cumulative YTD audits',display.to_csv(index=False).encode('utf-8-sig'),f'CoW_Cumulative_Audits_{year}_through_{cutoff:02d}.csv','text/csv',key='ytd-cumulative-download')
    st.caption('Conformance is recalculated from the cumulative source records, not by adding or averaging monthly percentages. Use YTD Overview for separate monthly results. Incident rolling totals are excluded.')
