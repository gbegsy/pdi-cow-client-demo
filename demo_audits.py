"""Isolated, generated September scenario for checking all five KPIs."""
import json
from datetime import date, timedelta

PERIOD = '2026-09'
SCENARIO = 'full-months-2026-jan-oct-v4'


def prepare(db, questions, groups):
    from leadership_views import schema
    schema(db)
    c=db()
    if c.execute("SELECT COUNT(*) FROM audits WHERE audit_id LIKE 'MOCK-%'").fetchone()[0]:
        c.close()
        prepare_full_months(db)
        return
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
            # Constructed demonstration: concentrated failures keep question
            # and whole-audit conformance in the requested 75–83% range.
            import math
            for row in responses[:math.ceil(0.9*len(responses))]:
                row.update(response='No',
                    comments_evidence='Fictional failed check in a deliberately concentrated demonstration scenario.',
                    smart_action='Review and correct this failed check; verify the correction before closing.',
                    action_owner='Demo Action Owner',action_due_date='2026-10-15')
                if row['bar_rating']=='BAR 1':
                    row['immediate_action']='DEMO: work stopped and made safe; required controls to be verified before authorised restart.'
        if form=='lead':
            responses.append(dict(section='Conversation prompts',item='N-02',question='What made the task harder?',response='Comment',comments_evidence='Generated example: equipment access was restricted and the handover helped the team plan the work.'))
        hf_examples=[
            "During the toolbox briefing the team could not identify the isolation boundary from the outdated drawing in the work pack. The supervisor paused preparation and requested the current drawing before authorisation.",
            "The night-to-day handover omitted the temporary access restriction. The incoming team discovered the blocked route at the worksite and revised the equipment movement plan with the supervisor.",
            "Two concurrent jobs competed for the same lifting equipment. Time pressure and coordination gaps were discussed; the supervisor resequenced the work rather than asking the team to rush.",
            "A technician unfamiliar with this valve arrangement asked for support. A competent colleague demonstrated the identification checks and the technician repeated them before work started.",
            "High noise at the worksite made the radio briefing difficult to hear. Moving the briefing to a quiet area and using repeat-back helped each person explain their task and stop-work conditions.",
            "The procedure referred to an obsolete equipment tag. The team highlighted the ambiguous instruction and raised a document correction; no informal workaround was accepted.",
            "Restricted access required an awkward posture to read the local gauge. The team stopped the check and requested a safer access arrangement and suitable lighting.",
            "The team reported workload building near shift end. The supervisor reassigned the remaining inspection to the next shift and included the incomplete checks in the written handover.",
            "A new contractor did not understand a local abbreviation in the permit. The supervisor explained it in plain language and checked understanding through a practical walk-through.",
            "Clear equipment labels and a joint worksite walk-down helped the team verify the correct isolation points. This was a useful briefing practice observed during preparation.",
            "The crew described a recurring delay obtaining replacement tools. Leadership agreed to review tool availability with stores; the audit did not establish whether staffing was a contributing factor.",
            "A conflicting instruction between the procedure and work pack was raised during the briefing. The team held the task pending technical clarification and recorded the agreed revision."
        ]
        # Separate, explicitly fictional narrative: does not change Yes/No scores.
        hf_note="FICTIONAL HF DEMO: "+hf_examples[(serial-1)%len(hf_examples)]
        meta=dict(site=site,audit_date=str(day),auditor=person,reference=aid,team=team,nui_team=team,auditor_role=role,leadership_role=role,permit_sample_category=category,new_wcc=category=='Non-routine',demo_scenario=SCENARIO,auditor_notes=hf_note)
        c.execute('INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,str(day)+'T12:00:00',title,str(day),site,person,aid,json.dumps(meta),json.dumps(responses),'Non-conformance' if fail else 'Conformant'))

    # 48 of 80 weekly/category credits: an obvious Red delivery example.
    for site,(routine,nonroutine) in groups.items():
        for week in weeks[:3]:
            for category,target in [('Routine',routine),('Non-routine',nonroutine)]:
                for n in range(target):
                    add('permit',week+timedelta(days=1),'%s'%site,'Demo Site Controller','Site Controller',category,fail=(serial%5==0))
    # Five independent samples, one failed audit: 80% whole-audit conformance.
    for index,week in enumerate(weeks):
        add('permit',week+timedelta(days=1),'North Remote Sites','Demo Asset Superintendent','Asset Superintendent',fail=(index==1))
    # Five engagements, one failed: 80% whole-engagement conformance.
    for index,week in enumerate(weeks):
        add('lead',week+timedelta(days=1),'North Remote Sites' if index%2==0 else 'South Remote Sites',
            'Demo Operations Director','Operations Director',fail=(index==1),team=f'Demo Team {index+1}')
    # Five audits per visitor role, one failed for each: 80% conformance.
    # Visit evidence remains separately counted; extra audits do not create visits.
    for role,count,person in [('Operations Supervisor',3,'Demo Supervisor'),('HSE Adviser',4,'Demo HSE Adviser')]:
        for i,week in enumerate(weeks):
            day=week+timedelta(days=1)
            add('tbt',day,'North Remote Sites',person,role,fail=(i==1))
            if i<count:
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
    prepare_full_months(db)


def prepare_full_months(db):
    """Add fictional full calendar months once, preserving existing submissions."""
    import calendar
    from kpi_rules import reporting_weeks
    c=db()
    source=c.execute("SELECT * FROM audits WHERE audit_id LIKE 'MOCK-%' AND audit_date LIKE '2026-09-%' ORDER BY audit_date,audit_id").fetchall()
    if not source:
        c.close()
        return
    for month in list(range(1,9))+[10]:
        period=f"2026-{month:02d}"
        prefix=f"MOCK-{period}-"
        if c.execute("SELECT COUNT(*) FROM audits WHERE audit_id LIKE ?",(prefix+"%",)).fetchone()[0]:
            continue
        month_end=date(2026,month,calendar.monthrange(2026,month)[1])
        month_start=date(2026,month,1)
        target_weeks=reporting_weeks(2026,month)
        def mapped(value):
            old=date.fromisoformat(str(value)[:10])
            week_index=min(4,max(0,(old.day-1)//7))
            week=target_weeks[min(week_index,len(target_weeks)-1)]
            return max(month_start,min(month_end,week+timedelta(days=1)))
        for row in source:
            values=list(row)
            aid=prefix+row[0]
            audit_day=mapped(row[3])
            meta=json.loads(row[7] or '{}')
            responses=json.loads(row[8] or '[]')
            meta.update(audit_date=str(audit_day),reference=aid,demo_scenario=SCENARIO,fictional_full_month=True)
            for response in responses:
                if response.get('response')=='No':
                    response['action_due_date']=str(month_end+timedelta(days=15))
            values[0]=aid;values[1]=str(audit_day)+'T12:00:00';values[3]=str(audit_day);values[6]=aid
            values[7]=json.dumps(meta);values[8]=json.dumps(responses)
            c.execute("INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?)",tuple(values))
        original_visits=c.execute("SELECT * FROM kpi4_visits WHERE visit_id LIKE 'MOCK-%' AND visit_date LIKE '2026-09-%'").fetchall()
        for row in original_visits:
            visit=list(row);visit[0]=prefix+row[0];visit[1]=str(mapped(row[1]));visit[5]=prefix+row[5];visit[6]=str(month_end)
            c.execute("INSERT INTO kpi4_visits VALUES(?,?,?,?,?,?,?)",tuple(visit))
        original_rota=c.execute("SELECT * FROM leadership_obligations WHERE period='2026-09' AND obligation_id LIKE 'MOCK-%'").fetchall()
        for row in original_rota:
            rota=list(row);rota[0]=prefix+row[0];rota[1]=period
            rota[4]=str(mapped(row[4])-timedelta(days=mapped(row[4]).weekday()))
            rota[7]=prefix+row[7]
            c.execute("INSERT INTO leadership_obligations VALUES(?,?,?,?,?,?,?,?,?)",tuple(rota))
        c.execute("INSERT INTO governance VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(period,'All','Aligned and nine-group rotation confirmed',100,0,0,'Reasonable','Suitable','Reasonable','Isolated minor',0,0))
        c.execute("INSERT INTO kpi5 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(prefix+'KPI5',str(month_end)+'T12:00:00',period,'All',12,10,0,1,1,0,'No','No','No','FICTIONAL DEMO: full-month incident summary; rolling 12-month values are snapshots and must not be summed across months. Twelve versus ten incidents, one MTC and one LOC. No live Incident Register source.',0))
        c.execute("INSERT INTO kpi_recovery_actions VALUES(?,?,?,?,?,?,?,?,?,?,?)",(prefix+'ACTION',period,'All / All','KPI 1','Demo Action Owner','','Review missed sampling, agree accountable actions and verify improvements.',str(month_end+timedelta(days=15)),'Open','',json.dumps([dict(source_reference=prefix+'sampling',at=str(month_end))])))
    c.commit();c.close()
    prepare_fully_conformant_auditor(db)


def prepare_fully_conformant_auditor(db):
    """Give five existing conformant samples per month a distinct fictional auditor."""
    c=db()
    for month in range(1,11):
        period=f"2026-{month:02d}"
        if c.execute("SELECT COUNT(*) FROM audits WHERE auditor=? AND audit_date LIKE ?",('Demo Assurance Lead',period+'%')).fetchone()[0]:
            continue
        candidates=c.execute("SELECT audit_id,metadata,responses FROM audits WHERE auditor=? AND audit_date LIKE ? ORDER BY audit_date,audit_id",('Demo Site Controller',period+'%')).fetchall()
        chosen=[]
        for aid,metadata,responses in candidates:
            answers=[r.get('response') for r in json.loads(responses) if r.get('response') in ('Yes','No')]
            if answers and 'No' not in answers:
                chosen.append((aid,metadata))
            if len(chosen)==5: break
        for aid,metadata in chosen:
            meta=json.loads(metadata or '{}')
            meta['auditor']='Demo Assurance Lead'
            c.execute("UPDATE audits SET auditor=?,metadata=? WHERE audit_id=?",('Demo Assurance Lead',json.dumps(meta),aid))
    c.commit();c.close()
