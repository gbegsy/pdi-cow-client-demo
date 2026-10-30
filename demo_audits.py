"""Isolated, generated September scenario for checking all five KPIs."""
import json
from datetime import date, timedelta

PERIOD = '2026-09'
SCENARIO = 'september-kpi-check-v1'


def prepare(db, questions, groups):
    from leadership_views import schema
    schema(db)
    c=db()
    if c.execute("SELECT COUNT(*) FROM audits WHERE audit_id LIKE 'MOCK-%'").fetchone()[0]:
        c.close(); return
    weeks=[date(2026,8,31)+timedelta(days=7*i) for i in range(5)]
    serial=0

    def add(form,day,site,person,role,category='Routine',fail=False,team='Demo Remote Site Team'):
        nonlocal serial
        serial+=1; aid=f'MOCK-{serial:03d}'
        key='ptw' if form=='permit' else 'tbt' if form=='tbt' else 'lead'
        title={'permit':'Control of Work: Permit Quality','tbt':'Control of Work: Toolbox Talk, Permit Compliance & Operating Procedures','lead':'Control of Work Leadership Engagement Checklist'}[form]
        responses=[]
        for si,(section,items) in enumerate(questions[key]):
            if key=='ptw' and ((si==1 and category=='Routine') or (si==2 and category!='Routine')):continue
            for q in items:
                responses.append(dict(section=section,item=q[0],question=q[1],bar_rating=q[2],response='Yes',comments_evidence='',smart_action='',action_owner='',action_due_date='',immediate_action=''))
        if fail:
            row=next(r for r in responses if r['bar_rating']=='BAR 2')
            row.update(response='No',comments_evidence='Generated example: the task procedure was unclear; the supervisor helped clarify the sequence.',smart_action='Review the task procedure with the work party.',action_owner='Demo Action Owner',action_due_date='2026-10-15')
        if form=='lead':
            responses.append(dict(section='Conversation prompts',item='N-02',question='What made the task harder?',response='Comment',comments_evidence='Generated example: equipment access was restricted and the handover helped the team plan the work.'))
        meta=dict(site=site,audit_date=str(day),auditor=person,reference=aid,team=team,nui_team=team,auditor_role=role,leadership_role=role,permit_sample_category=category,new_wcc=category=='Non-routine',demo_scenario=SCENARIO)
        c.execute('INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,str(day)+'T12:00:00',title,str(day),site,person,aid,json.dumps(meta),json.dumps(responses),'Non-conformance' if fail else 'Conformant'))

    # 48 of 80 weekly/category credits: an obvious Red delivery example.
    for site,(routine,nonroutine) in groups.items():
        for week in weeks[:3]:
            for category,target in [('Routine',routine),('Non-routine',nonroutine)]:
                for n in range(target):
                    add('permit',week+timedelta(days=1),'%s'%site,'Demo Site Controller','Site Controller',category,fail=(site=='Site Alpha' and week==weeks[1] and n==0 and category=='Routine'))
    # Five correctly spaced independent samples: Green.
    for week in weeks:
        add('permit',week+timedelta(days=1),'North Remote Sites','Demo Asset Superintendent','Asset Superintendent')
    # Two collective engagements in Q3: Amber.
    add('lead',date(2026,8,18),'North Remote Sites','Demo Operations Director','Operations Director',team='Demo North Mobile Team')
    add('lead',date(2026,9,15),'South Remote Sites','Demo Deputy Operations Director','Deputy Operations Director',team='Demo South Support Team Team')
    # Role-week visit coverage 60% and 80%, with suitable justification and one Site Manager visit.
    for role,count,person in [('Operations Supervisor',3,'Demo Supervisor'),('HSE Adviser',4,'Demo Medic')]:
        for i,week in enumerate(weeks[:count]):
            day=week+timedelta(days=1)
            add('tbt',day,'North Remote Sites',person,role,fail=(role=='HSE Adviser' and i==1))
            c.execute('INSERT INTO kpi4_visits VALUES(?,?,?,?,?,?,?)',(f'MOCK-VIS-{role}-{i}',str(day),role,'North Remote Sites','Demo Remote Site Team',f'MOCK-VISIT-{role}-{i}',str(day)))
            c.execute('INSERT INTO leadership_obligations VALUES(?,?,?,?,?,?,?,?,?)',(f'MOCK-ROTA-{role}-{i}',PERIOD,'North Remote Sites','Demo Remote Site Team',str(week),role,person,f'MOCK-VISIT-{role}-{i}','Generated demo rota, not a real duty record'))
    c.execute('INSERT INTO kpi4_visits VALUES(?,?,?,?,?,?,?)',('MOCK-Site Manager','2026-09-15','Site Manager','North Remote Sites','Demo Remote Site Team','MOCK-VISIT-Site Manager','2026-09-15'))
    c.execute('INSERT INTO governance VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(PERIOD,'All','Aligned and nine-group rotation confirmed',100,0,0,'Reasonable','Suitable','Reasonable','Isolated minor',0,0))
    # Reviewed mock incident summary, in this isolated database only.
    c.execute('INSERT INTO kpi5 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('MOCK-KPI5','2026-09-30T12:00:00',PERIOD,'All',12,10,0,1,1,0,'No','No','No','DEMO ONLY: generated incident summary. Twelve rolling incidents versus ten previously; one MTC and one LOC. Review equipment access and procedure clarity. No real Incident Register source.',0))
    for i in range(12):
        day=date(2026,9,1)-timedelta(days=25*i)
        c.execute('INSERT INTO cow_incidents VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(f'MOCK-INC-{i+1}',str(day),'North Remote Sites','Generated permitted-activity incident for demonstration only','Demo mechanical task','Unconfirmed',0,'MTC' if i==0 else 'None',int(i==1),0,0,f'MOCK-Incident Register-{i+1}'))
    c.execute('INSERT INTO kpi_recovery_actions VALUES(?,?,?,?,?,?,?,?,?,?,?)',('MOCK-ACTION',PERIOD,'All / All','KPI 1','Demo Action Owner','','Review missed weekly sampling and agree the next assurance priorities.','2026-10-15','Open','',json.dumps([dict(source_reference='MOCK weekly sampling shortfalls',at='2026-09-30')])) )
    c.commit();c.close()

