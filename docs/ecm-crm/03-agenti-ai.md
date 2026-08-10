# Porting del layer agentico di `trycompai/crm` dentro Indico

Obiettivo: **non** affiancare un CRM agentico a Indico, ma portare runtime,
strumenti, skill, coda e integrazioni dentro Indico, che diventa il gestionale
ECM con il CRM agentico incorporato.

## Perché il porting è legalmente pulito

| Progetto | Licenza | Conseguenza |
|---|---|---|
| `indico/indico` | MIT ✅ | Modificabile, chiudibile, rivendibile |
| `trycompai/crm` | MIT ✅ | **Codice copiabile e riadattabile senza obblighi** |

Le due licenze sono compatibili e permissive. È l'unica combinazione della
ricerca che consente un porting letterale del codice: qualsiasi CRM AGPL
(Relaticle, Twenty, EspoCRM, Frappe) avrebbe contaminato il gestionale.
Va mantenuta l'attribuzione del copyright originale nei file derivati.

Resta un solo vincolo tecnico: il codice sorgente è **TypeScript** e Indico è
**Python**. Non è un copia-incolla, è una riscrittura fedele degli stessi
meccanismi. Ciò che si porta è l'architettura, che è la parte di valore.

---

## Inventario reale del sorgente ✅

Verificato in questa sessione su `trycompai/crm`, ramo `main`.

```text
apps/agent/
├── agent/
│   ├── agent.ts                   ← definizione dell'agente principale
│   ├── instructions.md            ← istruzioni di sistema in prosa
│   ├── instructions/              ← istruzioni aggiuntive
│   ├── tools/                     ← 27 file, uno per tool
│   ├── skills/                    ← 4 file .md
│   │   ├── data-boundaries.md
│   │   ├── evidence.md
│   │   ├── identity-matching.md
│   │   └── writing-a-brief.md
│   ├── schedules/
│   │   └── dispatch.ts            ← dispatcher dei task scaduti
│   ├── subagents/
│   │   ├── agent_builder/         ← costruisce nuovi agenti
│   │   └── agent_runner/          ← esegue gli agenti costruiti
│   ├── channels/
│   │   ├── crm.ts                 ← canale verso il CRM
│   │   └── eve.ts                 ← canale del runtime
│   ├── hooks/
│   │   ├── activity.ts            ← traccia l'attività
│   │   ├── audit.ts               ← audit trail
│   │   ├── telemetry.ts           ← metriche
│   │   └── builder-delegation.ts
│   ├── sandbox/
│   │   ├── sandbox.ts             ← esecuzione isolata
│   │   └── workspace/
│   └── lib/                       ← 35 file di libreria
├── evals/                         ← valutazione dell'agente
├── scripts/ · test/ · .scratch/
├── package.json · tsconfig.json · turbo.json
```

### I 27 tool ✅

```text
tools/
├── read_crm_history.ts          ├── research_person.ts
├── read_company_history.ts      ├── research_company.ts
├── read_deal_history.ts         ├── enrich_company.ts
├── search_crm.ts                ├── get_linkedin_profile.ts
├── identify_contact.ts          ├── resolve_linkedin_profile.ts
├── list_deals.ts                ├── find_contact_socials.ts
├── list_fields.ts               ├── set_contact_socials.ts
├── list_outstanding_work.ts     ├── fetch_contact_photo.ts
├── manage_fields.ts             ├── get_contact_work_history.ts
├── set_field_value.ts           ├── record_job_change.ts
├── archive_field.ts             ├── write_brief.ts
├── record_fact.ts               ├── write_workspace_profile.ts
├── schedule_recheck.ts          ├── set_chat_title.ts
└── agent.ts
```

### I 35 file di `lib/` ✅ — i più importanti

| File | Funzione | Priorità di porting |
|---|---|---|
| `tasks.ts` | Coda dei lavori, `claimDue`, leasing | ⭐⭐⭐ |
| `dispatch.ts` | Distribuzione dei task agli agenti | ⭐⭐⭐ |
| `run-runtime.ts` · `run-state.ts` | Esecuzione durabile e stato del run | ⭐⭐⭐ |
| `evidence.ts` · `facts.ts` | Registro delle evidenze con provenienza | ⭐⭐⭐ |
| `approval.ts` | Approvazione umana | ⭐⭐⭐ |
| `capabilities.ts` | Cosa l'agente può fare | ⭐⭐ |
| `crm.ts` · `lookup.ts` · `names.ts` | Accesso ai record e matching | ⭐⭐ |
| `fields.ts` | Campi custom | ⭐⭐ |
| `focus.ts` · `session-purpose.ts` | Scopo della sessione, riduzione della deriva | ⭐⭐ |
| `preamble.ts` · `research-instructions.ts` | Composizione del contesto | ⭐⭐ |
| `model.ts` | Astrazione del modello LLM | ⭐⭐ |
| `pool.ts` | Pool di connessioni/worker | ⭐ |
| `perplexity.ts` · `linkdapi.ts` · `context-dev.ts` · `enrichment.ts` | Fornitori esterni di ricerca | ⭐ sostituibili |
| `portrait*.ts` · `brand*.ts` · `socials.ts` | Immagini e branding | ⛔ fuori scopo ECM |
| `app-auth.ts` · `accounts.ts` · `workspace.ts` | Auth e tenancy | ⛔ sostituiti dall'auth di Indico |
| `builder-*.ts` · `custom-agent-dispatch.ts` | Agenti costruiti dall'utente | ⏸ fase 2 |
| `conversation-title.ts` | Titolo conversazione | ⭐ minore |

---

## Destinazione dentro Indico

Il layer agentico non va nel core: va in un plugin, per poter aggiornare Indico
da upstream. Struttura di destinazione:

```text
indico/                                       ← il core, aggiornabile da upstream
└── plugins/
    ├── indico_crm/                           ← CRM nativo (vedi 04-crm-in-indico.md)
    ├── indico_ecm/                           ← dominio ECM: crediti, attestati
    └── indico_agents/                        ⭐ questo documento
        ├── plugin.py                         ⟵ nuovo (IndicoPlugin)
        ├── blueprint.py                      ⟵ nuovo
        ├── signals.py                        ⟵ hooks/activity.ts
        │
        ├── runtime/
        │   ├── tasks.py                      ⟵ lib/tasks.ts          ⭐⭐⭐
        │   ├── leases.py                     ⟵ lib/tasks.ts (claimDue)
        │   ├── dispatch.py                   ⟵ schedules/dispatch.ts + lib/dispatch.ts
        │   ├── run_state.py                  ⟵ lib/run-state.ts
        │   ├── run_runtime.py                ⟵ lib/run-runtime.ts
        │   ├── pool.py                       ⟵ lib/pool.ts
        │   ├── model.py                      ⟵ lib/model.ts
        │   ├── preamble.py                   ⟵ lib/preamble.ts
        │   ├── focus.py                      ⟵ lib/focus.ts + lib/session-purpose.ts
        │   └── capabilities.py               ⟵ lib/capabilities.ts
        │
        ├── sandbox/
        │   ├── worker.py                     ⟵ sandbox/sandbox.ts    ⭐
        │   ├── policy.py                     ⟵ nuovo (allowlist egress)
        │   └── workspace/                    ⟵ sandbox/workspace/
        │
        ├── tools/
        │   ├── base.py                       ⟵ nuovo: decoratore @agent_tool
        │   ├── registry.py                   ⟵ nuovo
        │   ├── crm/                          ⟵ i tool CRM portati (sotto)
        │   ├── events/                       ⟵ nuovi tool Indico
        │   ├── ecm/                           ⟵ nuovi tool ECM
        │   └── comms/                        ⟵ nuovi tool email/calendario
        │
        ├── skills/
        │   ├── evidence.md                   ⟵ skills/evidence.md          ⭐⭐
        │   ├── identity-matching.md          ⟵ skills/identity-matching.md ⭐⭐
        │   ├── data-boundaries.md            ⟵ skills/data-boundaries.md   ⭐⭐
        │   ├── writing-a-brief.md            ⟵ skills/writing-a-brief.md
        │   ├── ecm-compliance.md             ⟵ nuovo ⭐⭐⭐
        │   ├── attendance-rules.md           ⟵ nuovo
        │   ├── faculty-conflicts.md          ⟵ nuovo
        │   └── sponsor-outreach.md           ⟵ nuovo
        │
        ├── agents/
        │   ├── base.py                       ⟵ agent/agent.ts
        │   ├── instructions.md               ⟵ agent/instructions.md
        │   ├── event_agent.py                ⟵ nuovo
        │   ├── registration_agent.py         ⟵ nuovo
        │   ├── faculty_agent.py              ⟵ nuovo
        │   ├── sponsor_agent.py              ⟵ research_person + research_company
        │   ├── participant_agent.py          ⟵ nuovo
        │   ├── attendance_agent.py           ⟵ nuovo
        │   ├── credit_agent.py               ⟵ nuovo (solo verifica)
        │   ├── certificate_agent.py          ⟵ nuovo (solo bozza)
        │   ├── compliance_agent.py           ⟵ nuovo
        │   ├── sales_followup_agent.py       ⟵ schedule_recheck
        │   ├── communication_agent.py        ⟵ nuovo
        │   └── reporting_agent.py            ⟵ write_brief
        │
        ├── schedules/
        │   ├── dispatch.py                   ⟵ schedules/dispatch.ts ⭐⭐⭐
        │   ├── sync_google.py                ⟵ nuovo
        │   ├── sync_registrations.py         ⟵ nuovo
        │   ├── reconcile_attendance.py       ⟵ nuovo
        │   └── review_certificates.py        ⟵ nuovo
        │
        ├── governance/
        │   ├── approvals.py                  ⟵ lib/approval.ts       ⭐⭐⭐
        │   ├── audit.py                      ⟵ hooks/audit.ts + modules/logs
        │   ├── telemetry.py                  ⟵ hooks/telemetry.ts
        │   ├── policies.py                   ⟵ nuovo (autorizzazioni fuori dal prompt)
        │   ├── kill_switch.py                ⟵ nuovo
        │   ├── budgets.py                    ⟵ nuovo (limite costi/ricerche)
        │   └── redaction.py                  ⟵ nuovo (PII fuori dai prompt)
        │
        ├── channels/
        │   ├── web.py                        ⟵ channels/crm.ts (chat contestuale in UI)
        │   └── internal.py                   ⟵ channels/eve.ts
        │
        ├── models/                           ← tabelle SQLAlchemy, vedi sotto
        ├── migrations/
        ├── evals/                            ⟵ evals/  ⭐ non saltare
        └── tests/
```

---

## Mappa di porting, file per file

### Runtime — il cuore

| Sorgente TS ✅ | Destinazione Python | Traduzione tecnica |
|---|---|---|
| `lib/tasks.ts` (`claimDue`) | `runtime/tasks.py` | `SELECT … FOR UPDATE SKIP LOCKED` diventa `query.with_for_update(skip_locked=True)` in SQLAlchemy. Postgres è lo stesso, il meccanismo è identico |
| `schedules/dispatch.ts` | `schedules/dispatch.py` + Celery beat | Un task Celery periodico ogni minuto affitta i task scaduti e avvia i run. **Il dispatcher non interpreta il lavoro**: prende ciò che è scaduto e avvia l'agente |
| `lib/run-state.ts` | `runtime/run_state.py` | Stato del run persistito su Postgres a ogni step, non in memoria: un run interrotto riprende |
| `lib/run-runtime.ts` | `runtime/run_runtime.py` | Ciclo tool-call → osservazione → decisione, con limite di step e budget |
| `lib/model.ts` | `runtime/model.py` | Astrazione del provider LLM. Un solo punto da cambiare per sostituire il modello |
| `lib/pool.ts` | `runtime/pool.py` | Concorrenza dei worker: in Indico si appoggia ai worker Celery esistenti |
| `sandbox/sandbox.ts` | `sandbox/worker.py` | Worker separato **senza credenziali DB**: i tool sono chiamate RPC autenticate verso l'app, non query dirette |

### Tool CRM — porting diretto

| Sorgente ✅ | Destinazione | Adattamento ECM |
|---|---|---|
| `read_crm_history.ts` | `tools/crm/read_contact_history.py` | Legge la timeline del contatto e delle sue partecipazioni a eventi |
| `read_company_history.ts` | `tools/crm/read_company_history.py` | Storico sponsorizzazioni ed edizioni |
| `read_deal_history.ts` | `tools/crm/read_opportunity_history.py` | Trattativa sponsor/contratto |
| `search_crm.ts` | `tools/crm/search_crm.py` | Ricerca su contatti, aziende, opportunità |
| `identify_contact.ts` | `tools/crm/identify_contact.py` | ⭐ Matching HCP: nome + email + codice fiscale + albo. La regola di matching è più stretta dell'originale |
| `list_deals.ts` | `tools/crm/list_opportunities.py` | — |
| `list_outstanding_work.ts` | `tools/crm/list_outstanding_work.py` | Cosa resta da fare su evento/contatto |
| `list_fields.ts` · `manage_fields.ts` · `set_field_value.ts` · `archive_field.ts` | `tools/crm/fields_*.py` | ⚠️ **Vietati sui campi regolatori**: crediti, presenze e attestati non sono modificabili da tool generici |
| `record_fact.ts` | `tools/crm/record_fact.py` | ⭐⭐ Ogni fatto salvato porta fonte, data e affidabilità |
| `record_job_change.ts` | `tools/crm/record_job_change.py` | Cambio struttura sanitaria del professionista: rilevante per l'invito mirato |
| `research_person.ts` | `tools/crm/research_person.py` | Ricerca faculty e referenti |
| `research_company.ts` · `enrich_company.ts` | `tools/crm/research_company.py`, `enrich_company.py` | Sponsor, aziende farmaceutiche, provider partner |
| `write_brief.ts` | `tools/crm/write_brief.py` | ⭐ Briefing pre-call e pre-evento |
| `schedule_recheck.ts` | `tools/crm/schedule_recheck.py` | ⭐⭐ L'agente si riprogramma da solo: base di tutti i follow-up |
| `write_workspace_profile.ts` | `tools/crm/write_provider_profile.py` | Profilo del provider ECM |
| `get_linkedin_profile.ts` · `resolve_linkedin_profile.ts` · `find_contact_socials.ts` · `set_contact_socials.ts` · `get_contact_work_history.ts` | `tools/crm/social_*.py` | ⏸ Bassa priorità. Su dati di professionisti sanitari, l'arricchimento da fonti social va valutato con il DPO prima di attivarlo |
| `fetch_contact_photo.ts` | — | ⛔ Non portare: dato personale non necessario |
| `set_chat_title.ts` | `tools/crm/set_chat_title.py` | Minore |
| `agent.ts` (tool) | `tools/crm/delegate.py` | Delega a un altro agente |

### Tool nuovi — dominio Indico ed ECM

Sono i tool che il sorgente non ha e che rendono l'agente utile a un provider:

```text
tools/events/
├── search_events.py              ← eventi per periodo, tipo, stato
├── inspect_event.py              ← configurazione, faculty, timetable, stato accreditamento
├── inspect_registration.py       ← singola iscrizione, dati mancanti, pagamento
├── list_registrations.py         ← con filtri: incomplete, non pagate, senza presenza
├── inspect_timetable.py          ← sessioni, durate, conflitti relatori
├── list_faculty.py               ← relatori, ruoli, documenti mancanti
├── check_room_conflicts.py       ← sovrapposizioni sale/sessioni
└── draft_event_checklist.py      ← checklist e scadenze per evento

tools/ecm/
├── inspect_attendance.py         ← check-in/out per sessione, anomalie
├── verify_eligibility.py         ⭐ SOLA LETTURA: chiama il servizio deterministico
├── simulate_credits.py           ⭐ SOLA LETTURA: simulazione, mai assegnazione
├── list_certificate_candidates.py← aventi diritto secondo il servizio ECM
├── prepare_certificate_batch.py  ⚠️ crea una BOZZA in stato pending_approval
├── check_accreditation_docs.py   ← documenti mancanti per la pratica
└── export_regulatory_report.py   ⚠️ genera, non trasmette

tools/comms/
├── draft_email.py                ⚠️ bozza, mai invio diretto
├── send_approved_email.py        ← invia solo ciò che è già approvato
├── read_email_thread.py          ← thread collegato al contatto
├── schedule_meeting.py           ← slot faculty e call commerciali
└── create_task.py                ← task per una persona reale
```

Regola di progettazione dei tool: **ogni tool che scrive un dato regolatorio non
esiste**. Al suo posto esiste un tool che prepara una proposta in stato
`pending_approval` e un'interfaccia dove una persona autorizzata approva.

### Skill — prosa versionata

Le 4 skill originali si portano quasi invariate (sono testo, non codice), più
quelle di dominio:

| Skill | Origine | Contenuto per il provider ECM |
|---|---|---|
| `evidence.md` | ✅ portata | Nessun fatto senza fonte. Distinzione fra osservato, dichiarato e dedotto |
| `identity-matching.md` | ✅ portata | Quando due record sono la stessa persona. Per l'ECM la soglia è più severa: senza codice fiscale o numero di albo, non si fonde |
| `data-boundaries.md` | ✅ portata | Cosa l'agente può leggere. Per l'ECM: dati sanitari e categorie particolari mai nel prompt |
| `writing-a-brief.md` | ✅ portata | Come si scrive un briefing utile |
| `ecm-compliance.md` | nuovo ⭐⭐⭐ | Cosa l'agente **non** decide mai: crediti, idoneità, validità di una presenza |
| `attendance-rules.md` | nuovo | Come si legge un'anomalia di presenza e come si segnala |
| `faculty-conflicts.md` | nuovo | Dichiarazioni e conflitti d'interesse |
| `sponsor-outreach.md` | nuovo | Limiti nella comunicazione verso aziende farmaceutiche |

**Requisito di audit**: ogni run registra l'hash delle skill caricate. Se una
decisione viene contestata a distanza di mesi, si deve poter dire con quale
versione delle regole l'agente stava operando.

---

## Il modello dati del layer agentico

```text
indico_agents/models/
├── agent_task.py         ← la coda
├── agent_run.py          ← esecuzione
├── agent_step.py         ← singolo passo
├── tool_call.py          ← chiamata a tool con input/output
├── evidence.py           ← fatto + fonte + affidabilità
├── approval.py           ← richiesta di approvazione umana
├── agent_budget.py       ← consumo di token/ricerche per run e per evento
├── skill_version.py      ← versioni delle skill caricate in un run
└── policy_decision.py    ← cosa è stato permesso o negato, e perché
```

Schema essenziale di `agent_task` — la tabella che regge tutto:

```text
agent_task
├── id
├── kind                  (registration_check, attendance_reconcile, sponsor_research…)
├── subject_type          (event | registration | contact | company | certificate_batch)
├── subject_id
├── event_id              ← quasi sempre valorizzato: il lavoro è ancorato a un evento
├── payload               (jsonb)
├── run_after             ⭐ timestamp: il "quando" è un dato, non un cron
├── priority
├── status                (pending | leased | running | done | failed | cancelled)
├── lease_owner           ⭐ worker che l'ha affittato
├── lease_expires_at      ⭐ se scade, il task torna disponibile
├── attempts · max_attempts
├── last_error
├── created_by            (signal | schedule | agent | user)
└── created_dt · updated_dt
```

Il leasing è ciò che rende il sistema affidabile: un worker che muore non blocca
il task, perché il lease scade e un altro worker lo riprende. È la ragione per
cui `claimDue` va portato fedelmente e non sostituito con una coda Celery
semplice — Celery distribuisce il lavoro, ma non dà scadenze riprogrammabili né
visibilità sul perché un lavoro esiste.

---

## Il principio da non violare

Il progetto originale è esplicito: **l'API non contiene intelligenza
decisionale**. Registra che è successo qualcosa; l'agente interpreta e decide il
lavoro successivo. Portato in Indico:

```text
   Un partecipante si iscrive
              │
              ▼
   Indico salva la Registration          ← nessuna chiamata AI qui
              │
              ▼
   signals.registration_created           ← core/signals di Indico
              │
              ▼
   agent_task(kind='registration_check',  ← si crea un TASK, non si chiama un LLM
              run_after=now+5min)
              │
              ▼
   dispatch.py affitta il task scaduto    ← Celery beat, ogni minuto
              │
              ▼
   Agent run: carica skill, chiama tool, raccoglie evidenze
              │
              ├── dati completi        → chiude il task, registra evidenza
              ├── dati mancanti        → crea bozza email + task di follow-up
              └── anomalia regolatoria → apre approval per una persona
```

Nessun percorso sincrono fra la richiesta HTTP del partecipante e un modello
linguistico. Il gestionale resta veloce e prevedibile; l'intelligenza è
asincrona, riprovabile e tracciata.

---

## Catalogo agenti e livelli di autonomia

| Livello | Significato | Chi lo usa |
|---|---|---|
| **L0** | Sola lettura: osserva, segnala, produce briefing | Reporting, Compliance, Credit |
| **L1** | Redige bozze che una persona invia o pubblica | Communication, Certificate, Sponsor |
| **L2** | Agisce su dati non regolatori (task, note, campi CRM), con audit | Registration, Sponsor, Sales follow-up |
| **L3** | Agisce autonomamente entro policy esplicite | Nessun agente ECM. Riservato a operazioni interne (sincronizzazioni) |

| Agente | Trigger | Tool principali | Livello | Limite invalicabile |
|---|---|---|---|---|
| `event_agent` | Evento creato o modificato | `inspect_event`, `draft_event_checklist`, `create_task` | L2 | Non modifica il programma né lo stato di accreditamento |
| `registration_agent` | Iscrizione creata, pagamento ricevuto | `inspect_registration`, `identify_contact`, `draft_email` | L2 | Non modifica dati anagrafici sensibili senza conferma |
| `faculty_agent` | Relatore assegnato, documento caricato | `list_faculty`, `research_person`, `record_fact` | L1 | Non approva una faculty né valida un conflitto d'interessi |
| `sponsor_agent` | Nuova azienda, rinnovo, evento in preparazione | `research_company`, `enrich_company`, `schedule_recheck` | L2 | Non invia offerte né contratti |
| `participant_agent` | Domanda del partecipante | `read_contact_history`, `inspect_registration` | L1 | Accede solo ai dati del richiedente |
| `attendance_agent` | Fine sessione, fine evento | `inspect_attendance`, `record_fact` | L0/L1 | **Non convalida né corregge una presenza** |
| `credit_agent` | Evento chiuso | `verify_eligibility`, `simulate_credits` | **L0** | **Non assegna crediti. Mai.** |
| `certificate_agent` | Crediti assegnati da una persona | `list_certificate_candidates`, `prepare_certificate_batch` | L1 | Emissione solo dopo approvazione |
| `compliance_agent` | Periodico e pre-scadenza | `check_accreditation_docs`, `export_regulatory_report` | L0 | Non trasmette nulla all'esterno |
| `sales_followup_agent` | Inattività, scadenza contratto | `list_opportunities`, `schedule_recheck`, `draft_email` | L2 | Non promette condizioni commerciali |
| `communication_agent` | Campagna, reminder | `draft_email`, `send_approved_email` | L1 | Invia solo contenuti già approvati |
| `reporting_agent` | Fine evento, richiesta direzione | `write_brief`, `read_*_history` | L0 | Solo dati tracciati e citabili |

**La regola che tiene in piedi tutto**: `credit_calculator.py` e
`eligibility_service.py` (nel plugin `indico_ecm`) sono codice deterministico,
versionato per anno e regione, testato e auditabile. L'agente li **interroga**
tramite `verify_eligibility` e `simulate_credits`, non li sostituisce. Un LLM non
tocca mai un credito formativo.

---

## Governance

| Componente | Origine | Cosa fa nel gestionale ECM |
|---|---|---|
| `approvals.py` | ⟵ `lib/approval.ts` | Coda di approvazione con motivazione, approvatore, timestamp e diff di ciò che verrà applicato |
| `audit.py` | ⟵ `hooks/audit.ts` + `indico/modules/logs` | Ogni tool call finisce nel log evento di Indico, visibile agli amministratori |
| `policies.py` | nuovo | Chi può fare cosa, valutato **prima** della tool call e fuori dal prompt |
| `kill_switch.py` | nuovo | Ferma tutti gli agenti senza spegnere il gestionale |
| `budgets.py` | nuovo | Tetto di token, ricerche esterne e costo per run e per evento |
| `redaction.py` | nuovo | Rimuove identificativi diretti prima dell'invio al modello |
| `skill_version.py` | nuovo | Congela quale versione delle regole ha guidato ogni run |
| `evals/` | ⟵ `evals/` | Test di comportamento dell'agente: da mantenere, è ciò che impedisce le regressioni silenziose |

### Trattamento dei dati

Un provider ECM tratta dati di professionisti sanitari identificabili. Tre
vincoli da rispettare nel porting:

1. Il sandbox non ha credenziali di database e non ha egress libero (già vero
   nell'originale ✅): i tool sono RPC autenticate, non query.
2. `redaction.py` sostituisce nome, email, codice fiscale e numero di albo con
   identificativi opachi prima di comporre il prompt; la risoluzione avviene
   dopo, lato applicazione.
3. Le fonti esterne di arricchimento (`perplexity.ts`, `linkdapi.ts`,
   `context-dev.ts`) vanno attivate **solo per aziende e sponsor**, mai per
   ricerche su singoli professionisti sanitari, senza una valutazione del DPO.

---

## Ordine di porting

| Passo | Cosa | Perché prima | Stima |
|---|---|---|---|
| 1 | `models/` + `runtime/tasks.py` + `leases.py` | Senza coda affidabile il resto non ha senso | 1 sett. |
| 2 | `schedules/dispatch.py` su Celery beat | Il motore che fa girare tutto | 3 giorni |
| 3 | `runtime/run_state.py` + `run_runtime.py` | Run durabili e riprendibili | 1,5 sett. |
| 4 | `tools/base.py` + `registry.py` + 3 tool di lettura | Prova il ciclo completo end-to-end | 1 sett. |
| 5 | `skills/` (4 portate + `ecm-compliance.md`) | Il comportamento diventa editabile senza deploy | 3 giorni |
| 6 | `governance/audit.py` + `policies.py` + `kill_switch.py` | **Prima** di dare all'agente qualunque capacità di scrittura | 1 sett. |
| 7 | `sandbox/worker.py` | Isolamento prima dei tool di ricerca esterna | 1 sett. |
| 8 | `evidence.py` + `record_fact` | Da qui in poi ogni affermazione ha una fonte | 4 giorni |
| 9 | `reporting_agent` + `compliance_agent` (L0) | Primi agenti in produzione: non scrivono nulla | 1 sett. |
| 10 | `approvals.py` + UI di approvazione | Sblocca gli agenti L1 | 1,5 sett. |
| 11 | `registration_agent`, `attendance_agent`, `certificate_agent` | Il valore operativo quotidiano | 3 sett. |
| 12 | `sponsor_agent`, `sales_followup_agent` + arricchimento | Il valore commerciale | 2 sett. |
| 13 | `subagents/` (agent builder/runner) | Solo quando il resto è stabile | 2 sett. |

Passi 6 e 7 non sono negoziabili e non vanno rimandati: sono l'unica cosa che
separa un sistema di agenti utile da un incidente su dati sanitari.
