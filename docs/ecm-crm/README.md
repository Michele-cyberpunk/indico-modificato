# Piattaforma CRM + ECM su Indico — dossier di composizione

Dossier di progettazione per trasformare **Indico nel gestionale ECM di un
provider**, con il CRM e il layer di agenti AI **incorporati** (non affiancati),
portando dentro Indico i moduli agentici, CRM e di automazione di
`trycompai/crm`.

## Indice

| Documento | Contenuto |
|---|---|
| [01-catalogo-repository.md](01-catalogo-repository.md) | Catalogo completo dei CRM e dei progetti adiacenti: licenza, stack, cosa prendere, cosa **non** prendere |
| [02-mosaico-file.md](02-mosaico-file.md) | Per ogni repository, l'albero dei file da estrarre e la mappa "tessera → destinazione" |
| [03-agenti-ai.md](03-agenti-ai.md) | ⭐ Porting del layer agentico di `trycompai/crm` dentro Indico: runtime, coda, tool, skill, governance |
| [04-crm-in-indico.md](04-crm-in-indico.md) | ⭐ CRM nativo dentro Indico: modelli, legami con gli oggetti Indico, segnali di innesto |

## La direzione

```text
Indico (questo fork, MIT)
        │
        ├── Eventi, registrazioni, sessioni, faculty
        ├── Presenze, badge, sale, abstract, timetable, questionari
        └── + moduli proprietari come plugin
                │
                ├── indico_crm          aziende · contatti · HCP · sponsor · opportunità · evidenze
                ├── indico_ecm          accreditamento · presenze · crediti · attestati · export
                ├── indico_agents       ⟵ porting di trycompai/crm: coda · tool · skill · approvazioni
                └── indico_integrations Gmail · Calendar · arricchimento · webinar · pagamenti
```

Non si costruisce un CRM separato accanto a Indico. Indico **è** il gestionale;
CRM, agenti, coda, skill e integrazioni diventano il suo strato operativo.

## Perché questa direzione regge tecnicamente e legalmente

| Progetto | Licenza | Esito |
|---|---|---|
| `indico/indico` | MIT ✅ | Base modificabile, chiudibile, rivendibile |
| `trycompai/crm` | MIT ✅ | **Codice portabile senza obblighi** |
| Relaticle, Twenty, EspoCRM, SuiteCRM, Frappe, CiviCRM, pretix, Documenso | AGPL ✅ | Contaminerebbero il gestionale se integrati nel codice |
| n8n | Sustainable Use License ✅ | ⛔ Vieta di offrire il prodotto a terzi come servizio |

MIT + MIT è l'unica combinazione emersa dalla ricerca che consente un porting
letterale. I progetti AGPL restano utili **solo come modelli concettuali**
(schemi dati, pattern) o come servizi esterni non modificati.

Unico costo tecnico del porting: il sorgente è TypeScript, Indico è Python. Si
riscrivono i meccanismi, non si copiano i file — ed è comunque l'architettura la
parte di valore.

## Metodo di verifica

Tre livelli di affidabilità, sempre marcati:

- **✅ verificato** — controllato in questa sessione: filesystem di questo
  repository per Indico, pagine GitHub per gli altri progetti.
- **○ indicativo** — struttura plausibile ma non ispezionata file per file.
- **⚠️ da verificare** — riportato in letteratura ma non confermato qui.

Sono ✅ e quindi utilizzabili senza ulteriore controllo: l'intera struttura di
Indico, l'inventario di `trycompai/crm` (27 tool, 4 skill, 35 file di `lib/`,
`hooks/`, `sandbox/`, `subagents/`), i nomi reali dei segnali di Indico, e
licenza e stack di tutti i progetti del catalogo salvo dove indicato ⚠️.

## Correzioni rispetto all'analisi iniziale

| Affermazione precedente | Realtà ✅ |
|---|---|
| `indico/modules/events/badges/` | Non esiste. Badge in `indico/modules/designer/` + `events/registration/badges.py` |
| `indico/modules/events/rooms/` | Non esiste. Sale in `indico/modules/rb/`, aggancio evento in `rb/event/` |
| `indico/modules/events/logs/` | Non esiste. Audit in `indico/modules/logs/models/entries.py` |
| `indico/modules/fields/` | Non esiste come modulo. Campi per dominio: `events/fields.py`, `contributions/contrib_fields.py`, `registration/fields/` |
| "Indico non ha certificati" | Falso: `indico/modules/receipts/default_templates/attendance/` è un *Certificate of Attendance* già pronto |
| "manca l'API di check-in" | Falso: `indico/modules/events/registration/controllers/api/checkin.py` |
| trycompai: agenti in `agents/`, tool 18, skill 4 | Reale: `apps/agent/agent/` con **27 tool**, 4 skill (`evidence`, `identity-matching`, `data-boundaries`, `writing-a-brief`), `lib/` da 35 file, `subagents/agent_builder` e `agent_runner` |
| Indico ha un modulo crediti ECM | Confermato: **non esiste**. Va scritto ex novo |

## L'architettura in una figura

```text
┌──────────────────────────────────────────────────────────────────┐
│                     INDICO (core MIT, fork)                      │
│  eventi · registrazioni · timetable · sessioni · abstract        │
│  faculty · survey · pagamenti · badge · receipts · rb · logs     │
└───────┬──────────────────────────────────────────────┬───────────┘
        │ segnali del core                             │ estensione minima
        │ registration_created                         │ checkin.py →
        │ registration_checkin_updated                 │ presenza per sessione
        │ event.created · sidemenu · get_log_renderers │
        ▼                                              ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│   indico_crm     │   │   indico_ecm     │   │ indico_integrations  │
│                  │   │                  │   │                      │
│ aziende          │   │ accreditamento   │   │ Gmail · Calendar     │
│ contatti · HCP   │◄─►│ presenze sessione│   │ arricchimento        │
│ opportunità      │   │ regole crediti ⚙ │   │ webinar · pagamenti  │
│ contratti        │   │ attestati        │   │ firma · contabilità  │
│ consensi         │   │ export ECM       │   │ outbox               │
│ evidenze         │   │                  │   │                      │
└────────┬─────────┘   └────────┬─────────┘   └──────────┬───────────┘
         │                      │ ⚙ deterministico       │
         │                      │   mai LLM              │
         └──────────┬───────────┴────────────────────────┘
                    ▼
        ┌───────────────────────────────────────┐
        │           indico_agents               │
        │  coda con leasing (FOR UPDATE SKIP    │
        │  LOCKED) · dispatch su Celery beat    │
        │  run durabili · 27+ tool · skill .md  │
        │  sandbox senza DB · evidenze          │
        │  approvazioni · audit · kill switch   │
        └───────────────────────────────────────┘
```

Due principi che attraversano tutto il progetto:

1. **L'API non decide.** Un'iscrizione o un check-in salvano un record e creano
   un *task*; nessuna chiamata sincrona a un modello linguistico nel percorso
   HTTP. L'agente interpreta dopo, in modo asincrono e riprovabile.
2. **I crediti non passano da un LLM.** `credit_calculator.py` e
   `eligibility_service.py` sono deterministici, versionati per anno e regione,
   testati. L'agente li interroga, prepara e segnala; non decide e non firma.

## Ordine di costruzione

| Fase | Contenuto | Riferimento | Stima |
|---|---|---|---|
| 1 | `indico_crm`: modelli, tabella ponte, servizi, UI minima | 04 | 5 sett. |
| 2 | Aggancio ai segnali del core; il CRM si popola dal lavoro reale | 04 | 2 sett. |
| 3 | `indico_ecm`: profilo HCP, presenza per sessione, estensione `checkin.py` | 04, 02 | 6 sett. |
| 4 | `indico_ecm`: regole crediti, idoneità, attestati sopra `receipts/` | 02 | 8 sett. |
| 5 | `indico_agents`: coda, dispatch, run durabili, audit, sandbox | 03 | 6 sett. |
| 6 | Agenti L0 (sola lettura) in produzione | 03 | 2 sett. |
| 7 | `indico_integrations`: Gmail, Calendar, outbox, webinar | 04 | 5 sett. |
| 8 | Approvazioni + agenti L1/L2 | 03 | 6 sett. |
| 9 | Export regolatori, reportistica, evals degli agenti | 02, 03 | 4 sett. |

Le fasi 3 e 4 sono il prodotto: nessun progetto open source fornisce crediti,
presenze regolatorie e attestati ECM. Tutto il resto è infrastruttura che
conviene non riscrivere.
