# PDi VERIFY — Control of Work client demo

Standalone demonstration using fictional sites, people, visits, audits and incidents. All targets, role titles, checklist wording and BAR allocations are examples requiring client agreement before operational use.

Run `streamlit run app.py`. For a separate Streamlit deployment, select repository `gbegsy/pdi-cow-client-demo`, branch `main` and entry point `app.py`. Do not reuse an existing application deployment or database settings.

The demo never reads DATABASE_URL or database secrets. Each browser session receives its own temporary SQLite database, populated with generated records. Refreshes preserve that session's demo work; a new session starts fresh. Do not enter confidential or operational records.

Includes three audit forms, five KPI views, leadership narrative and HTML/PDF-print report, BAR findings/actions, auditor audit counts and average conformance, visit evidence and comment themes. September 2026 is the initial sample month. There is no historic client slide baseline or imported operational data.

Example criteria use an Amber delivery band from 70% to below 100% for permit sampling; site monitoring roles use 50% to below 100%. These are demonstration choices, not client-approved requirements.
