# Il CRM dentro Indico — moduli, modelli e punti di innesto

Indico non viene affiancato da un CRM: **diventa** il gestionale ECM con il CRM
incorporato. Questo documento definisce i moduli CRM nativi, il loro legame con
gli oggetti Indico esistenti e i punti di aggancio verificati nel core.

---

## Impianto generale

```text
indico/                                  ← core, aggiornabile da upstream
│
└── plugins/                             ← tutto il nuovo codice vive qui
    ├── indico_crm/         ← aziende, contatti, professionisti, opportunità, evidenze
    ├── indico_ecm/         ← accreditamento, presenze, crediti, attestati, export
    ├── indico_agents/      ← runtime agentico (03-agenti-ai.md)
    └── indico_integrations/← Gmail, Calendar, arricchimento, comunicazioni
```

**Perché plugin e non core.** Il core di Indico continua a ricevere aggiornamenti
di sicurezza e funzionalità da upstream. Ogni riga scritta dentro
`indico/modules/` è una riga da riconciliare a ogni merge. I plugin di Indico
sono progettati esattamente per questo: aggiungono modelli, rotte, voci di menu,
colonne nelle liste e handler di segnali senza toccare il core.

Vale una sola eccezione: dove il core va **esteso** e non semplicemente
osservato (presenza per sessione, template attestato), si contribuisce la
modifica in modo generico e la si tiene in un branch di fork ridotto al minimo.

### Convenzione dei modelli di plugin ✅

Verificata in `docs/source/plugins/models.rst` di questo repository: i modelli di
un plugin vivono in uno schema Postgres dedicato.

```python
class Company(db.Model):
    __tablename__ = 'companies'
    __table_args__ = {'schema': 'plugin_crm'}
```

Schemi previsti: `plugin_crm`, `plugin_ecm`, `plugin_agents`,
`plugin_integrations`. Nessuna tabella del core viene alterata; i collegamenti
avvengono per chiave esterna verso `events.events`, `event_registration.registrations`,
`users.users`.

---

## `indico_crm` — struttura

```text
plugins/indico_crm/indico_crm/
├── plugin.py                     ← IndicoPlugin: settings, blueprint, menu, segnali
├── blueprint.py
├── models/
│   ├── companies.py              ← azienda: sponsor, provider, fornitore, struttura sanitaria
│   ├── contacts.py               ← persona di contatto
│   ├── hcp_profiles.py           ⭐ professionista sanitario (estensione ECM del contatto)
│   ├── organization_links.py     ← relazione persona ↔ azienda nel tempo (ruolo, da/a)
│   ├── opportunities.py          ← trattativa: sponsorizzazione, commessa formativa
│   ├── opportunity_stages.py     ← pipeline configurabile
│   ├── contracts.py              ← contratto sponsor/faculty
│   ├── quotes.py · invoices.py   ← preventivo e fattura (o rimando alla contabilità)
│   ├── activities.py             ← chiamata, incontro, visita
│   ├── tasks.py                  ← attività assegnata a una persona reale
│   ├── notes.py
│   ├── communications.py         ← email e messaggi collegati al record
│   ├── consents.py               ⭐ consensi privacy e marketing, con prova e data
│   ├── evidence.py               ⭐⭐ fatto + fonte + affidabilità + chi l'ha registrato
│   ├── timeline.py               ← vista unificata degli eventi su un record
│   └── links.py                  ⭐⭐ tabella ponte verso gli oggetti Indico
├── services/
│   ├── contact_service.py
│   ├── identity_service.py       ⭐ deduplica e matching
│   ├── enrichment_service.py
│   ├── pipeline_service.py
│   ├── followup_service.py
│   ├── evidence_service.py
│   └── consent_service.py
├── controllers/                  ← RH di Indico (management + display)
├── forms/                        ← WTForms come nel core
├── schemas.py                    ← marshmallow: la superficie API dei tool
├── api/                          ← REST per agenti e integrazioni
├── client/                       ← React, coerente con il frontend di Indico
├── templates/
├── placeholders.py               ← segnaposto per le email
├── signals.py                    ⭐ handler dei segnali del core
├── migrations/
└── tests/
```

---

## Il legame con gli oggetti Indico

È la parte che distingue un CRM incorporato da un CRM affiancato. Un contatto
non è un record isolato: è la stessa persona che si iscrive, parla, modera,
sponsorizza e riceve l'attestato.

```text
Company (plugin_crm.companies)
├── kind          → sponsor | exhibitor | provider | partner | supplier | healthcare_org
├── vat_id · sdi_code · pec        ← dati per la fatturazione italiana
├── contacts[]                     → Contact
├── opportunities[]                → Opportunity
├── contracts[]                    → Contract
├── event_links[]                  → events.events        ⭐ sponsorizzazioni per edizione
└── evidence[]                     → Evidence

Contact (plugin_crm.contacts)
├── user_id          → users.users          (facoltativo: se ha un account Indico)
├── hcp_profile      → HCPProfile           (se professionista sanitario)
├── company_links[]  → OrganizationLink     (ruolo e periodo)
├── roles[]          → participant | speaker | moderator | scientific_director
│                      | tutor | sponsor_contact | staff
├── registrations[]  → event_registration.registrations   ⭐ per evento
├── event_persons[]  → events.persons (EventPerson)       ⭐ faculty
├── communications[] · activities[] · tasks[] · notes[]
├── consents[]       → Consent
└── evidence[]       → Evidence

HCPProfile (plugin_crm.hcp_profiles)              ⭐ il cuore del dominio ECM
├── contact_id
├── tax_code                    ← codice fiscale (chiave di identità ECM)
├── profession · discipline     ← professione e disciplina
├── registry_board · registry_number · registry_region   ← albo
├── employment_type             ← dipendente | libero prof. | convenzionato | privo
├── healthcare_org_id           → Company (struttura di appartenenza)
├── credit_history[]            → plugin_ecm.credit_assignments
├── eligibility_flags           ← esclusioni, cariche, deroghe
└── verification_status         ← verificato | da verificare | contestato

Opportunity (plugin_crm.opportunities)
├── event_id          → events.events        ⭐ la trattativa è quasi sempre su un evento
├── company_id · owner_user_id
├── value · stage · probability · expected_close_dt
├── next_action · next_action_dt
└── activities[] · tasks[] · evidence[]
```

### La tabella ponte

`models/links.py` è la sola tabella che conosce entrambi i mondi, e va tenuta
sottile e indicizzata:

```text
plugin_crm.object_links
├── crm_type      (contact | company | opportunity)
├── crm_id
├── indico_type   (event | registration | event_person | contribution | session
│                  | abstract | receipt_file | agreement)
├── indico_id
├── relation      (participant | speaker | sponsor_of | contract_for | invoice_for…)
├── source        (manual | signal | agent | import)
└── created_dt
```

Ogni collegamento creato da un agente porta `source='agent'` e una riga di
`Evidence` che ne spiega la ragione. Un collegamento senza spiegazione, in un
sistema regolatorio, è un debito.

---

## Punti di innesto verificati nel core ✅

Segnali reali di Indico, letti da `indico/core/signals/` in questo repository.
Sono i ganci su cui il CRM e gli agenti si attaccano **senza modificare il core**.

| Segnale ✅ | Modulo | Uso nel gestionale ECM |
|---|---|---|
| `event.created` | `signals/event/core.py` | Crea l'opportunità collegata, la checklist e i task iniziali |
| `event.updated` | idem | Ricalcola scadenze; se cambia data o programma, segnala impatto sull'accreditamento |
| `event.cloned` | idem | Clona la struttura CRM dell'edizione precedente |
| `event.session_updated` · `session_block_updated` | idem | Ricalcola le ore formative potenziali della sessione |
| `event.registration.registration_created` | `signals/event/registration.py` | Crea o riconcilia il Contact, apre `agent_task(registration_check)` |
| `registration_updated` · `registration_personal_data_modified` | idem | Riverifica i dati ECM (albo, codice fiscale, disciplina) |
| `registration_state_updated` | idem | Segue il ciclo: in attesa → confermata → pagata → annullata |
| **`registration_checkin_updated`** ⭐ | idem | Evento cardine per la presenza: apre il task di riconciliazione |
| `registration_deleted` | idem | Chiude i task pendenti, marca l'evidenza come superata |
| `generate_ticket_qr_code` · `custom_ticket_qr_code_handler` ⭐ | idem | Inserisce nel QR il token di check-in ECM firmato |
| `registrant_list_action_menu` · `registrant_list_items` | idem | Aggiunge colonne "crediti", "presenza", "attestato" e azioni di massa alla lista iscritti |
| `event.get_log_renderers` ⭐ | `signals/event/core.py` | Rende visibili nell'audit log di Indico le azioni CRM/ECM e degli agenti |
| `event.get_feature_definitions` | idem | Attiva "ECM" come funzionalità per singolo evento |
| `event.sidemenu` | idem | Aggiunge le voci ECM e CRM al menu dell'evento |
| `event.persons.*` | `signals/event/persons.py` | Sincronizza la faculty con i Contact |
| `agreements` | `signals/agreements.py` | Dichiarazioni di conflitto d'interessi della faculty |
| `users.*` | `signals/users.py` | Fusione account, cancellazione, export GDPR |
| `rh` · `acl` | `signals/rh.py`, `acl.py` | Permessi e tracciamento richieste |

**Nota sull'unico punto che i segnali non coprono**: la presenza per **sessione**
con entrata e uscita non esiste nel core (`Registration.checked_in` è un booleano
di evento, verificato in `models/registrations.py`). Va aggiunta estendendo
`controllers/api/checkin.py` — è l'unica modifica al core davvero necessaria, e
va scritta in modo generico per poter essere proposta upstream.

---

## `indico_integrations` — gli adapter

Il porting degli adapter è una sostituzione di record, non una riscrittura di
logica: dove l'originale scrive nel proprio CRM, si scrive nei modelli
`indico_crm` e negli oggetti Indico.

```text
plugins/indico_integrations/indico_integrations/
├── google/
│   ├── gmail.py            ⟵ ingestione thread → Communication + Timeline
│   ├── calendar.py         ⟵ incontri → Activity; slot faculty
│   ├── oauth.py            ← account collegati per utente
│   └── sync.py             ⟵ sincronizzazione incrementale con cursore
├── microsoft/              ← equivalente per Microsoft 365 (molti provider lo usano)
├── enrichment/
│   ├── search_provider.py  ⟵ lib/perplexity.ts (astratto, sostituibile)
│   ├── company_data.py     ⟵ lib/enrichment.ts
│   └── linkedin.py         ⟵ lib/linkdapi.ts ⚠️ solo aziende, mai HCP senza parere DPO
├── communications/
│   ├── email.py            ← invio transazionale e campagne
│   ├── sms.py · whatsapp.py
│   └── templates.py
├── webinar/
│   ├── zoom.py             ⟵ pattern di indico-plugins/vc_zoom
│   └── teams.py
├── payments/               ⟵ pattern di indico-plugins/payment_stripe
├── accounting/             ← fatturazione elettronica, SDI
├── signature/              ← firma attestati e contratti
└── sync/
    ├── outbox.py           ⭐ pattern transactional outbox
    └── livesync_bridge.py  ⟵ pattern di indico-plugins/livesync
```

### Regola di ingestione

Le email e gli inviti calendario non creano contatti alla cieca. La catena
corretta, ripresa dal modello di Twenty e resa più severa per il contesto
sanitario:

```text
account collegato → messaggio/invito → blocklist (domini personali, no-reply)
   → matching partecipante → contatto esistente?
        sì → aggiorna timeline
        no → PROPOSTA di nuovo contatto (non creazione automatica)
             → l'agente raccoglie evidenza → approvazione se è un HCP
```

Per un'azienda sponsor la creazione automatica è accettabile. Per un
professionista sanitario no: l'anagrafica HCP è la base di dati che genera gli
attestati, e non può popolarsi da sola.

---

## `indico_ecm` — il dominio regolatorio

Riassunto qui, dettagliato in [02-mosaico-file.md](02-mosaico-file.md).

```text
plugins/indico_ecm/indico_ecm/
├── models/
│   ├── provider.py · accreditation.py · activity_type.py
│   ├── learning_objective.py
│   ├── session_attendance.py      ⭐ entrata/uscita per sessione
│   ├── attendance_adjustment.py   ⭐ rettifica con motivazione e autore
│   ├── credit_rule.py             ⭐⭐ versionata per anno e regione
│   ├── credit_assignment.py       ⭐⭐ assegnazione, con chi e quando
│   ├── assessment_result.py       ← esito del questionario di apprendimento
│   ├── certificate.py             ← numerazione, hash, stato, revoca
│   └── audit_record.py
├── services/
│   ├── attendance_service.py
│   ├── credit_calculator.py       ⭐⭐⭐ deterministico. Nessun LLM.
│   ├── eligibility_service.py     ⭐⭐⭐ deterministico. Nessun LLM.
│   ├── certificate_service.py
│   ├── reconciliation_service.py  ← iscritti vs presenti vs aventi diritto
│   └── export_service.py
├── templates/certificates/        ⟵ estende indico/modules/receipts/default_templates/attendance/
├── api/ · controllers/ · forms/ · client/
├── tasks.py · signals.py · permissions.py
└── migrations/
```

### Il confine fra CRM e ECM

| Domanda | Risposta | Dove vive il dato |
|---|---|---|
| Chi è questa persona, chi conosce, cosa le abbiamo scritto | Relazione | `plugin_crm` |
| Questa persona era presente e ha diritto a 12 crediti | Regolatorio | `plugin_ecm` |
| L'azienda X sponsorizza l'evento Y per 15.000 € | Relazione | `plugin_crm` |
| L'evento Y è accreditato con id Z per 250 partecipanti | Regolatorio | `plugin_ecm` |

Un agente può scrivere liberamente (con audit) nel primo gruppo. Nel secondo può
solo leggere, simulare e proporre.

---

## Interfaccia utente

Il gestionale deve sembrare un solo prodotto, non tre plugin cuciti insieme.

| Punto UI | Aggancio ✅ | Contenuto |
|---|---|---|
| Menu laterale dell'evento | `event.sidemenu` | Voci "CRM", "ECM", "Agenti" |
| Lista iscritti | `registrant_list_items`, `registrant_list_action_menu` | Colonne presenza, crediti, attestato; azioni di massa |
| Scheda contatto | blueprint del plugin | Timeline, evidenze, partecipazioni, crediti storici |
| Scheda azienda | blueprint del plugin | Sponsorizzazioni per edizione, contratti, opportunità |
| Pannello agente contestuale | `channels/web.py` | Chat sul record aperto, con lo stesso contesto dell'agente |
| Coda approvazioni | blueprint del plugin | Bozze email, attestati proposti, fusioni contatto |
| Log evento | `event.get_log_renderers` | Azioni degli agenti visibili nell'audit nativo di Indico |

Il pannello agente contestuale è la funzione che rende evidente il valore: sulla
scheda di un'azienda sponsor, l'agente ha già in contesto le edizioni precedenti,
i contratti, le email e le opportunità aperte — senza che nessuno debba
riassumergli la situazione.

---

## Sequenza realistica di costruzione

| Fase | Contenuto | Perché in quest'ordine |
|---|---|---|
| 1 | `indico_crm`: modelli, `links.py`, servizi base, UI minima | Senza anagrafica non c'è né ECM né agenti |
| 2 | `signals.py`: aggancio a `registration_created`, `event.created`, `registration_checkin_updated` | Il CRM si popola dal lavoro reale, non da un import |
| 3 | `indico_ecm`: profilo HCP, presenza per sessione, estensione `checkin.py` | Il dato regolatorio prima delle automazioni |
| 4 | `indico_ecm`: regole crediti, idoneità, attestati sopra `receipts/` | Il prodotto vero |
| 5 | `indico_agents`: coda, dispatch, run durabili, audit, sandbox | Fondamenta del layer agentico (03) |
| 6 | Agenti L0 in produzione | Nessuna scrittura: si costruisce fiducia |
| 7 | `indico_integrations`: Gmail, Calendar, outbox | Le fonti che alimentano gli agenti |
| 8 | Agenti L1 e L2 con approvazioni | Il valore operativo quotidiano |

Fase 3 e 4 restano il centro di gravità del progetto: sono l'unica parte che
nessun repository open source fornisce, e sono ciò per cui un provider ECM
sceglierebbe questa piattaforma invece di un CRM generico.
