"""Transparent, local insight queries over the selected fictional audit sample."""
import re
from collections import Counter

QUESTIONS = ['What needs leadership attention?', 'Where are the BAR 1 non-conformances?', 'Which checks repeatedly fail?', 'How do the three audit types compare?', 'What do the HF comments reveal?', 'Search the audit evidence']

def query_mode(text):
    value=text.lower()
    if re.search(r'\b(hf|human factors|comments?|handover|workload)\b', value): return QUESTIONS[4]
    if re.search(r'bar\s*1|critical',value): return QUESTIONS[1]
    if re.search(r'repeat|recurr|frequen',value): return QUESTIONS[2]
    if re.search(r'compar|audit types|conformance|compliance',value): return QUESTIONS[3]
    if re.search(r'leadership|priorit|attention|overview',value): return QUESTIONS[0]
    return QUESTIONS[5]

def findings(audits):
    return [(a,r) for a in audits for r in a.get('responses',[]) if r.get('response')=='No']

def outcome_counts(audits):
    counts=Counter({'Conformant':0,'Non-conformant':0,'Unscored':0})
    for audit in audits:
        answers=[r.get('response') for r in audit.get('responses',[]) if r.get('response') in ('Yes','No')]
        counts['Non-conformant' if 'No' in answers else 'Conformant' if answers else 'Unscored']+=1
    return counts

def evidence_rows(pairs):
    return [{'Audit ID':a.get('audit_id',''),'Date':a.get('audit_date',''),'Site / Team':a.get('site',''),'Audit type':a.get('form_name',''),'Question reference':r.get('item',''),'BAR':r.get('bar_rating',''),'Question':r.get('question',''),'Evidence':r.get('comments_evidence',''),'Immediate action':r.get('immediate_action',''),'Follow-up':r.get('smart_action',''),'Owner':r.get('action_owner',''),'Due date':r.get('action_due_date','')} for a,r in pairs]

def search_pairs(audits,query):
    terms=[t for t in re.findall(r'[\w-]+',query.lower()) if len(t)>2 and t not in {'the','and','show','find','what','where','with','audit','audits','please'}]
    if not terms: return []
    matches=[]
    for a in audits:
        for r in a.get('responses',[]):
            haystack=' '.join(str(a.get(k,'')) for k in ('audit_id','site','auditor','form_name'))+' '+' '.join(str(r.get(k,'')) for k in ('item','question','comments_evidence','smart_action','action_owner'))
            if all(t in haystack.lower() for t in terms): matches.append((a,r))
    return matches

def render(audits,period):
    import streamlit as st
    import pandas as pd
    st.subheader('Mine the Diamond · Ask your assurance data')
    st.write('Turn audit records into a focused insight, supporting evidence and a practical next step.')
    st.caption(f'DEMO INSIGHT ASSISTANT · Local rules and evidence search, without a live AI model. Scope: {period}, selected asset and site, all three audit types. Free text does not change the reporting filters.')
    with st.form('diamond-question'):
        choice=st.selectbox('Pick a question',QUESTIONS)
        query=st.text_input('Or type a question / search phrase',placeholder='For example: repeated checks, BAR 1, handover, or an audit ID')
        submitted=st.form_submit_button('Find the insight',type='primary')
    if submitted: st.session_state['diamond-request']=(choice,query)
    choice,query=st.session_state.get('diamond-request',(QUESTIONS[0],''))
    mode=query_mode(query) if query.strip() else choice
    st.markdown('### '+mode)
    if query.strip(): st.caption('Matched analysis: '+mode+' · For site-specific answers, set the Site / Hub filter above. Use evidence search for exact words or IDs.')
    if not audits:
        st.info('No audits in this reporting scope. Change the reporting filters to explore available evidence.')
        return
    failed=findings(audits)
    critical=[p for p in failed if p[1].get('bar_rating')=='BAR 1']
    pairs=[]
    if mode==QUESTIONS[4]:
        from human_factors import render_leadership_narrative
        render_leadership_narrative(audits,period,key='diamond-hf')
        return
    if mode==QUESTIONS[3]:
        groups={}
        for a in audits: groups.setdefault(a.get('form_name','Unknown'),[]).append(a)
        result=[]
        for label,rows in groups.items():
            counts=outcome_counts(rows)
            result.append({'Audit type':label,'Audits':len(rows),**dict(counts)})
        st.dataframe(pd.DataFrame(result),hide_index=True,use_container_width=True)
        st.info('Next step: inspect non-conformant audits and delivery coverage in Detailed KPI Reports before comparing performance. Audit types have different questions and purposes.')
        st.caption('Any No makes an audit non-conformant. Audits with no applicable Yes/No answers are unscored.')
        return
    if mode==QUESTIONS[5]:
        if not query.strip():
            st.info('Enter a word, phrase or audit ID above to search questions, recorded evidence, actions and owners.')
            return
        pairs=search_pairs(audits,query)
        st.write(f'**{len(pairs)} matching answer records** across {len({a.get("audit_id") for a,r in pairs})} audits. Matches can include Yes, No and N/A responses.')
        st.caption('Search requires all significant words to occur in the record. Shorten the phrase if there are no matches.')
    elif mode==QUESTIONS[1]:
        pairs=critical
        st.write(f'**{len(critical)} BAR 1 non-conformances** across {len({a.get("audit_id") for a,r in critical})} audits.')
        st.info('Next step: verify the recorded immediate safety response, confirm current control status, and agree an owner, due date and verification for unresolved gaps.')
    elif mode==QUESTIONS[2]:
        grouped={}
        for a,r in failed:
            key=(a.get('form_name',''),r.get('item',''),r.get('question',''))
            grouped.setdefault(key,set()).add(a.get('audit_id'))
        repeated=[{'Audit type':k[0],'Ref':k[1],'Check':k[2],'Audits with a No':len(ids)} for k,ids in grouped.items() if len(ids)>1]
        repeated.sort(key=lambda r:-r['Audits with a No'])
        if repeated: st.dataframe(pd.DataFrame(repeated[:10]),hide_index=True,use_container_width=True)
        else: st.write('No check has a No in more than one audit in this scope.')
        keys={k for k,ids in grouped.items() if len(ids)>1}
        pairs=[(a,r) for a,r in failed if (a.get('form_name',''),r.get('item',''),r.get('question','')) in keys]
        st.info('Next step: investigate practical obstacles and whether previous actions worked. Repetition alone does not prove normalisation of deviance.')
    else:
        counts=outcome_counts(audits)
        st.write(f'**{counts["Non-conformant"]} of {len(audits)} audits contain a No; {len(critical)} BAR 1 findings require priority review.**')
        themes=Counter(r.get('question','Unspecified check') for a,r in failed)
        if themes:
            question,count=themes.most_common(1)[0]
            st.write(f'**Most frequent No response ({count} answer records):** {question}')
        pairs=critical or failed
        st.info('Leadership follow-up: verify critical-control gaps first, assign accountable actions for recurring findings, and check assurance delivery in Detailed KPI Reports. Recorded actions are not proof of closure.')
    if pairs:
        st.markdown('#### Supporting source records')
        frame=pd.DataFrame(evidence_rows(pairs))
        st.dataframe(frame.head(50),hide_index=True,use_container_width=True)
        st.caption(f'Showing {min(50,len(frame))} of {len(frame)} source records. Full evidence, actions, owners and due dates are in the download. Use Evidence Trail to inspect an audit and its related comments.')
        st.download_button('Download supporting evidence',frame.to_csv(index=False).encode('utf-8-sig'),'CoW_Diamond_Evidence_'+period+'.csv','text/csv',key='diamond-evidence')
    else: st.success('No matching source records in this reporting scope.')
    st.caption('Fictional demonstration records. These answers describe the selected audit sample, not proven causes or the condition of every barrier. Historical months reuse a constructed scenario.')
