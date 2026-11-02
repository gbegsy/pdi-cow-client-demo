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
