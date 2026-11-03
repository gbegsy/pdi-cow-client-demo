"""Finding concentration by existing BAR classification; no new scoring."""
from collections import Counter
from html import escape

LEVELS=[('BAR 3','Management & learning','Oversight, records and improvement follow-up','#375f83'),('BAR 2','Operational controls','Planning, understanding and how work is carried out','#a56300'),('BAR 1','Critical control verification','Required controls against major accident or serious harm','#b33640')]

def breakdown(audits):
    pairs=[(a,r) for a in audits for r in a.get('responses',[]) if r.get('response')=='No']
    counts=Counter(r.get('bar_rating') if r.get('bar_rating') in {'BAR 1','BAR 2','BAR 3'} else 'Unclassified' for a,r in pairs)
    return pairs,[{'BAR':bar,'Focus area':title,'Findings':counts[bar],'Share of findings %':round(100*counts[bar]/len(pairs),1) if pairs else 0} for bar,title,_,_ in LEVELS],counts['Unclassified']

def render(audits,period):
    import streamlit as st
    import pandas as pd
    pairs,rows,unknown=breakdown(audits)
    st.markdown('### Safety staircase · Where leadership should focus')
    st.caption('Steps group non-conformances by their existing BAR classification. Steps are ranked by share of non-conformances: the largest concentration is on the highest step. Rank indicates frequency; BAR classification indicates the type of control.')
    if not pairs:
        st.info('No non-conformances in this reporting scope. Check audit delivery and coverage before drawing a wider assurance conclusion.')
        return
    tiles=[]
    ranked=sorted(rows,key=lambda row:(-row['Findings'],row['BAR']))
    level_details={bar:(title,description,colour) for bar,title,description,colour in LEVELS}
    for index,row in enumerate(ranked):
        bar=row['BAR']
        title,description,colour=level_details[bar]
        tiles.append(f'<div class="safety-step step-{index}" style="--step-colour:{colour}"><span class="step-tag">#{index+1} · {bar}</span><h4>{escape(title)}</h4><strong>{row["Share of findings %"]:.1f}%</strong><p>{row["Findings"]} of {len(pairs)} non-conformances</p><small>{escape(description)}</small></div>')
    st.markdown('''<style>
    .safety-stairs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-items:end;gap:0;margin:24px 0 18px;padding-top:12px;border-bottom:3px solid #aec2ce}
    .safety-step{background:white;border:1px solid #ccdce5;border-top:7px solid var(--step-colour);border-radius:8px 8px 0 0;padding:20px;color:#102d42;box-shadow:0 3px 12px #102d420b;box-sizing:border-box}
    .safety-step.step-0{min-height:440px;background:#e9f3f5}.safety-step.step-1{min-height:350px;background:#f2f6f8}.safety-step.step-2{min-height:260px}
    .safety-step .step-tag{font-size:13px;font-weight:800;color:var(--step-colour)}.safety-step h4{font-size:19px;margin:9px 0 16px;min-height:50px}
    .safety-step strong{font-size:36px;line-height:1.1;color:var(--step-colour)}.safety-step p{font-size:15px!important;margin:10px 0}.safety-step small{font-size:14px;line-height:1.5;display:block;color:#526a7c}
    @media(max-width:700px){.safety-stairs{grid-template-columns:1fr;gap:12px;border-bottom:0}.safety-step.step-0,.safety-step.step-1,.safety-step.step-2{min-height:0}.safety-step h4{min-height:0}}
    </style><div class="safety-stairs">'''+''.join(tiles)+'</div>',unsafe_allow_html=True)
    if unknown: st.warning(f'{unknown} findings have no recognised BAR level ({100*unknown/len(pairs):.1f}% of all findings). Review their classification; they are retained in the denominator.')
    largest=max(rows,key=lambda row:row['Findings'])
    critical=next(row['Findings'] for row in rows if row['BAR']=='BAR 1')
    st.info(f'Leadership focus: the largest concentration is {largest["Focus area"]} ({largest["Share of findings %"]:.1f}%). '+(f'Prioritise review of the {critical} BAR 1 findings and verify current control status, alongside action on the recurring operational and management gaps.' if critical else 'Review repeated checks and agree accountable improvements with follow-up verification.'))
    st.caption('Percentages use all No responses across the three audit types in the selected month, asset and site. One failed question = one finding; an audit can contribute several. Share of findings is not a failure rate: the number of applicable questions differs by BAR level. A small share of BAR 1 findings can still require the most urgent attention. Percentages are shown to one decimal place.')
    chosen=st.selectbox('Reveal findings for a staircase step',[row['BAR'] for row in ranked]+(['Unclassified'] if unknown else []),key='staircase-bar')
    selected=[(a,r) for a,r in pairs if (r.get('bar_rating') if r.get('bar_rating') in {'BAR 1','BAR 2','BAR 3'} else 'Unclassified')==chosen]
    with st.expander(f'{chosen} · View {len(selected)} supporting findings',expanded=False):
        if selected:
            frame=pd.DataFrame([{'Audit ID':a.get('audit_id',''),'Audit type':a.get('form_name',''),'Site / Team':a.get('site',''),'Question reference':r.get('item',''),'Question':r.get('question',''),'Evidence':r.get('comments_evidence',''),'Immediate action':r.get('immediate_action',''),'Follow-up':r.get('smart_action',''),'Owner':r.get('action_owner',''),'Due':r.get('action_due_date','')} for a,r in selected])
            st.dataframe(frame,hide_index=True,use_container_width=True)
            st.download_button('Download staircase findings',frame.to_csv(index=False).encode('utf-8-sig'),'CoW_Staircase_'+chosen.replace(' ','')+'_'+period+'.csv','text/csv',key='staircase-download')
        else: st.write('No findings at this step in the selected reporting scope.')
