# Catalogo repository — cosa prendere da ognuno

Legenda affidabilità: **✅** verificato in questa sessione · **○** indicativo ·
**⚠️** da verificare.

> **Direzione del progetto.** Indico è il gestionale; CRM, agenti e automazioni
> vivono dentro Indico come plugin. Il catalogo va quindi letto su due colonne:
> i progetti **MIT** (`indico`, `trycompai/crm`, `indico-plugins`, Krayin) sono
> sorgenti di **codice portabile**; tutti gli altri (AGPL/GPL/LGPL) sono
> **riferimenti concettuali** o servizi esterni non modificati. Dettaglio del
> porting in [03-agenti-ai.md](03-agenti-ai.md) e [04-crm-in-indico.md](04-crm-in-indico.md).

---

## Quadro d'insieme

| # | Repository | Licenza | Stack | Ruolo nel mosaico ECM | Priorità |
|---|---|---|---|---|---|
| 1 | `indico/indico` (questo fork) | MIT ✅ | Python/Flask/SQLAlchemy, Postgres, Celery, React | **Motore eventi**: base modificabile senza vincoli | ⭐ fondante |
| 2 | `trycompai/crm` | MIT ✅ | Next.js + NestJS/tRPC + Prisma + Postgres, runtime agenti "eve" ✅ | **Sorgente del porting agentico**: coda, tool, skill, evidenze, approvazioni | ⭐⭐ fondante |
| 2b | `Relaticle/relaticle` | AGPL-3.0 ✅ | Laravel 13, PHP 8.4, Filament 5, Livewire 4, Postgres 17 ✅ | **Modello del CRM** (schema, policy, superficie MCP) — non integrabile nel codice | media (riferimento) |
| 3 | `twentyhq/twenty` | AGPL-3.0 ⚠️ | NestJS + React + TS, Postgres, Redis ✅ | **Modello dati CRM moderno** + motore workflow | ⭐ alta (come riferimento) |
| 4 | `espocrm/espocrm` | AGPLv3 ✅ | PHP 8.3–8.5, backend REST + SPA ✅ | **ORM a metadati**: entità/campi/layout definiti in JSON | media |
| 5 | `indico/indico-plugins` | MIT ✅ | Python ✅ | **Pattern di plugin** e `livesync` per la sincronizzazione incrementale | ⭐ alta |
| 6 | `Mrgig7/Multi-Agent-Enterprise-CRM` | MIT ✅ | LangGraph, Kafka, Weaviate, OPA, Keycloak ✅ | **Governance degli agenti**: policy, kill switch, event sourcing | media (riferimento) |
| 7 | `salesagility/SuiteCRM` | AGPLv3 ✅ | PHP 8.1–8.4 ✅ | **Motore workflow legacy** e copertura funzionale enterprise | bassa |
| 8 | `krayin/laravel-crm` | MIT ✅ | Laravel + Vue, packages/Webkul ✅ | **CRM MIT**: unica alternativa con codice copiabile se servisse materiale CRM già scritto | media |
| 9 | `frappe/crm` | AGPL-3.0 ✅ | Frappe (Python) + Vue 3 ✅ | **Telefonia** (Twilio/Exotel) e WhatsApp integrati | bassa |
| 10 | `odoo/odoo` | LGPL-3.0 ⚠️ | Python, addons modulari ✅ | **Unico precedente completo** evento+CRM+survey+e-learning+firma | media (riferimento) |
| 11 | `civicrm/civicrm-core` | AGPL-3 ✅ | PHP, APIv4 ✅ | **Modello partecipante/membership**: il più vicino al dominio ECM | ⭐ alta (riferimento dati) |
| 12 | `mautic/mautic` | GPL-3.0 ⚠️ | Symfony, bundle modulari ✅ | **Marketing automation**: campagne, segmenti, form, lead scoring | media |
| 13 | `chatwoot/chatwoot` | MIT + enterprise ⚠️ | Rails + Vue ✅ | **Inbox omnicanale** + agente AI "Captain" per supporto partecipanti | media |
| 14 | `pretalx/pretalx` | Apache-2.0 ✅ | Django, Postgres, Redis ✅ | **Workflow scientifico**: CfP, revisione, speaker, schedule (licenza permissiva!) | ⭐ alta |
| 15 | `pretix/pretix` | AGPLv3 + termini aggiuntivi ✅ | Django ✅ | **Ticketing, check-in, fatturazione** | media |
| 16 | `alfio-event/alf.io` | GPL-3.0 ✅ | Java 17, Spring Boot, Postgres ✅ | **Check-in con QR e badge printing**: il modello di presenza più solido | ⭐ alta (riferimento) |
| 17 | `documenso/documenso` | AGPL-3.0 ✅ | TS, React Router 7, Hono, Prisma; firme PAdES ✅ | **Firma digitale attestati** e contratti faculty/sponsor | media |
| 18 | `openSUSE/osem` | ⚠️ | Ruby on Rails | Modello conferenza alternativo | bassa |
| 19 | `calcom/cal.com` (oggi "Cal.diy") | MIT ⚠️ | Next.js, tRPC, Prisma ✅ | **Scheduling** call commerciali e slot faculty | bassa |
| 20 | `n8n-io/n8n` | Sustainable Use License ✅ | TypeScript ✅ | ⛔ **Escluso**: vieta l'offerta a terzi come servizio | escluso |
| 21 | `temporalio/temporal` | MIT ⚠️ | Go | **Orchestrazione durabile** dei workflow lunghi (sostituto di n8n) | ⭐ alta |
| 22 | `langchain-ai/langgraph` | MIT ⚠️ | Python/TS | **Orchestrazione agenti** a grafo con stato | ⭐ alta |

---

## 1. `indico/indico` — motore eventi (MIT)

**Perché è la scelta giusta come base.** È l'unico progetto della lista che
combina tre proprietà insieme: licenza permissiva (si può modificare, chiudere e
rivendere), dominio esattamente giusto (conferenze scientifiche con abstract,
faculty, timetable, registrazioni) e maturità (CERN, in produzione da anni).

**Cosa fornisce già, verificato in questo repository:**

| Capacità ECM | Dove sta | Stato |
|---|---|---|
| Anagrafica evento, categorie, permessi | `indico/modules/events/models/events.py`, `indico/modules/categories/` | pronto |
| Form di iscrizione con campi custom | `indico/modules/events/registration/fields/` (base, choices, simple, accompanying, affiliation, sessions) | pronto |
| Dati partecipante e stato | `indico/modules/events/registration/models/registrations.py` | pronto |
| Check-in | `indico/modules/events/registration/controllers/api/checkin.py` | pronto ma **solo evento, non sessione** |
| Timetable, sessioni, contributi, track | `indico/modules/events/timetable/`, `sessions/`, `contributions/`, `tracks/` | pronto |
| Abstract e revisione | `indico/modules/events/abstracts/`, `papers/`, `editing/` | pronto |
| Questionari | `indico/modules/events/surveys/` | pronto, manca scoring/soglie |
| Pagamenti | `indico/modules/events/payment/` + plugin Stripe/PayPal/SIXPay | pronto |
| Badge / poster / QR | `indico/modules/designer/` + `events/registration/badges.py`, `wallets/` | pronto |
| **Certificato di partecipazione** | `indico/modules/receipts/default_templates/attendance/` | **già esistente**, da estendere |
| Audit log | `indico/modules/logs/models/entries.py` | pronto |
| Sale e prenotazioni | `indico/modules/rb/` | pronto |
| Videoconferenza | `indico/modules/vc/` + plugin `vc_zoom` | pronto |
| Accordi / dichiarazioni firmate | `indico/modules/events/agreements/` | base per conflitto d'interessi faculty |
| Richieste con workflow di approvazione | `indico/modules/events/requests/` | **base ideale per la domanda di accreditamento** |
| OAuth / API | `indico/modules/oauth/`, `indico/core/oauth/` | pronto |
| Plugin engine + segnali | `indico/core/plugins/`, `indico/core/signals/` | pronto |

**Cosa manca del tutto e va scritto:** identità del provider ECM e dati di
accreditamento, obiettivi formativi, profilo del professionista sanitario
(professione, disciplina, numero albo, codice fiscale), presenza a livello di
sessione con entrata/uscita, regole crediti, assegnazione crediti, attestato ECM
numerato e verificabile, export regolatori.

**Cosa non prendere:** il modello `indico/modules/events/papers/` (peer review di
proceedings, non serve a un provider ECM), `cephalopod/`, `news/`,
`announcement/`, `search/` con Citadel se non si indicizzano documenti.

---

## 2b. `Relaticle/relaticle` — modello del CRM (AGPL-3.0)

Il punto di forza dichiarato dal progetto e verificato sulla pagina: server MCP
di produzione con **30 tool**, API REST completa, **22 tipi di campo custom**
(incluse relazioni tra entità e campi cifrati), isolamento multi-team con
autorizzazione a 5 livelli, oltre 2000 test automatici.

Per un CRM ECM questo significa che *contatti, aziende, opportunità, task,
note, permessi e API sono già risolti* — e che gli agenti AI hanno già una
superficie MCP su cui operare senza scrivere un tool layer da zero.

**Cosa prendere:** solo idee, non codice — la licenza AGPL lo esclude dal
gestionale. Valgono lo schema di `app/Models`, l'autorizzazione a 5 livelli di
`app/Policies`, l'impianto di `database/migrations` e soprattutto il modo in cui
espone il CRM agli agenti (30 tool MCP su una superficie API stabile): è il
riferimento per progettare `indico_crm/schemas.py` e i tool CRM del layer
agentico.

**Cosa non prendere:** non ci si deve appoggiare al suo sistema di custom field
per i dati regolatori (crediti, presenze, attestati). Quei dati hanno bisogno di
vincoli relazionali forti, versioning e audit: vanno in tabelle proprie
dell'ECM Service.

**Rischio:** AGPL-3.0. Se in futuro si volesse comunque usarlo, va deployato
come servizio separato e non modificato: incorporarlo nel gestionale
obbligherebbe a pubblicare l'intero prodotto.

---

## 3. `twentyhq/twenty` — modello dati e motore workflow (AGPL ⚠️)

Struttura server verificata (`packages/twenty-server/src/modules/`): `calendar`,
`messaging`, `messaging-webhooks`, `connected-account`,
`connected-account-sync-webhooks`, `contact-creation-manager`,
`match-participant`, `blocklist`, `company/standard-objects`,
`person/standard-objects`, `opportunity/standard-objects`,
`attachment/standard-objects`, `note`, `task`, `timeline`, `dashboard`,
`dashboard-sync`, `emailing`, `workflow`, `workspace-member`,
`onboarding-invite-suggestions`.

Tre idee da rubare, indipendentemente dal codice:

1. **`contact-creation-manager` + `match-participant` + `blocklist`**: il
   contatto non si crea a mano, si deriva dalle email e dagli inviti calendario,
   con matching sui partecipanti e una blocklist per escludere domini privati.
   Per un provider ECM è esattamente il modo giusto di popolare l'anagrafica
   HCP e sponsor senza data entry.
2. **`workflow`**: motore di automazione dichiarativo dentro il CRM (trigger →
   azioni), separato dagli agenti AI. Serve per le automazioni deterministiche;
   gli agenti restano per quelle che richiedono giudizio.
3. **`timeline`**: timeline unificata per record, che è la struttura su cui gli
   agenti scrivono le loro evidenze.

**Cosa non prendere:** il metamodello a oggetti dinamici (`workspace` con schema
Postgres per tenant) è potentissimo ma è un impegno architetturale enorme; per
un provider ECM singolo è sovradimensionato.

---

## 4. `espocrm/espocrm` — ORM a metadati (AGPLv3)

Struttura verificata: `application/Espo`, `client`, `frontend`, `tests`,
`public`, `install`. PHP 8.3–8.5, backend REST + SPA.

**L'idea da prendere:** entità, campi, relazioni, layout e permessi definiti in
file JSON di metadati, non in codice. Aggiungere il campo "disciplina ECM" o
l'entità "AccreditamentoEvento" diventa una modifica dichiarativa. Se si
costruisce un CRM proprietario (percorso A), questo è il modello di estensibilità
da copiare concettualmente.

---

## 2. `trycompai/crm` — la sorgente del porting agentico (MIT) ⭐⭐

È il repository più prezioso della lista dopo Indico, perché è **MIT** e perché
risolve il problema che tutti gli altri lasciano aperto: come si fa girare un
agente in modo affidabile dentro un CRM.

Struttura verificata: `apps/agent` (agente di ricerca con tool, skill, schedule,
sandbox), `apps/app` (Next.js), `apps/api` (NestJS), `packages/db` (Prisma),
`packages/auth`, `packages/ui`, `packages/env`.

**I meccanismi da riusare, uno per uno:**

| Meccanismo | Come funziona lì | Perché serve al provider ECM |
|---|---|---|
| Work queue con `FOR UPDATE SKIP LOCKED` | I job vengono affittati atomicamente da worker concorrenti | Migliaia di partecipanti da processare senza doppioni né lock globali |
| Agent runtime durabile (framework "eve", filesystem-first) | Lo stato dell'agente sopravvive a riavvii e timeout | Un controllo su un evento da 800 iscritti dura minuti, non secondi |
| **Skill come file di prosa versionati** (4 skill) | Il comportamento si modifica editando testo, non codice | Le regole ECM cambiano per anno e per regione: vanno versionate come testo revisionabile |
| Sandbox con bash/grep/glob, **senza accesso DB e senza egress** | L'agente ragiona in un ambiente isolato | Requisito di sicurezza non negoziabile su dati sanitari |
| 18 tool espliciti | Ogni capacità è un tool tipizzato, non prompt libero | Ogni azione dell'agente è tracciabile e autorizzabile |
| AI Gateway invece di SDK del singolo provider | Modello sostituibile | Evita il lock-in su un fornitore LLM |

**Cosa non prendere:** il dominio (è un CRM per vendere compliance software), lo
schema Prisma, l'accoppiamento a Vercel/Neon/Upstash. Si prende l'architettura,
non l'infrastruttura.

---

## 6. `Mrgig7/Multi-Agent-Enterprise-CRM` — governance (MIT)

Struttura verificata: `agents/`, `core_services/`, `gateway/`, `observability/`,
`policies/`, `schemas/`, `services/`, `database/`, `deploy/`, `docs/`,
`frontend/`, `tests/`. Stack: LangGraph, Ollama, Postgres 16, Redis, Weaviate,
Kafka, OPA, Keycloak.

Agenti: Sales (qualificazione lead), Support (triage ticket), Compliance
(policy enforcement e risk assessment), Analytics (trend e report), Knowledge
(documentazione auto-alimentata con ricerca semantica).

**Da prendere: tre pattern di governance**, che sono la parte che rende un
sistema di agenti accettabile in un contesto regolatorio:

1. **`policies/` con Open Policy Agent** — l'autorizzazione dell'agente è
   dichiarativa ed esterna al prompt. Nessun LLM decide cosa gli è permesso fare.
2. **Event sourcing con replay** — ogni decisione è ricostruibile a posteriori.
   In caso di contestazione su un credito, si può rieseguire la storia.
3. **Kill switch** — interruttore per fermare tutti gli agenti senza spegnere la
   piattaforma.

**Da trattare con prudenza:** è un progetto di riferimento architetturale, non
una base di produzione. Kafka + Weaviate + Keycloak + OPA + Kubernetes è uno
stack pesante: per un provider ECM, Postgres + Redis coprono lo stesso bisogno
con un ordine di grandezza in meno di complessità operativa.

---

## 7–9. SuiteCRM, Krayin, Frappe CRM

**SuiteCRM** (AGPLv3, PHP 8.1–8.4, dirs `Api`, `modules`, `include`, `metadata`,
`themes`, `install`): copre Accounts, Contacts, Leads, Opportunities, Cases,
Contracts, Campaigns, Documents, Quotes, Reports, Workflow. Il valore è la
**completezza funzionale come checklist**: serve a non dimenticare entità
(contratti, preventivi, casi) quando si progetta il proprio CRM. Il codice è
legacy SugarCRM: sconsigliato come base.

**Krayin** (MIT, Laravel + Vue, `packages/Webkul/`): l'unico CRM PHP maturo con
licenza permissiva. È l'alternativa a Relaticle nel percorso A, quando serve
codice modificabile e chiudibile. Meno ricco (niente MCP), ma MIT.

**Frappe CRM** (AGPL-3.0, Frappe/Python + Vue 3): da guardare per un solo motivo,
la **telefonia integrata** (Twilio ed Exotel con registrazione chiamate) e
WhatsApp. Per un provider ECM che fa recall telefonico verso i partecipanti è il
riferimento su come modellare chiamate e registrazioni.

---

## 10. `odoo/odoo` — l'unico precedente completo (LGPL-3 ⚠️)

Addon verificati nella repository: `crm`, `crm_iap_enrich`, `crm_iap_mine`,
`crm_livechat`, `crm_sms`, `crm_mail_plugin`, `crm_sale_project`, `event`,
`event_booth`, `event_booth_sale`, `event_crm`, `event_crm_sale`, `event_product`,
`event_sale`, `event_sms`, `account*`, `calendar`, `google_calendar`.

**Perché guardarlo:** `event_crm` è letteralmente il ponte fra evento e CRM
(genera lead dalle registrazioni), `event_sale` collega evento e fatturazione.
Odoo ha inoltre `survey` (con certificazione e punteggio minimo!), `slides`
(e-learning con attestato) e `sign` — che sono la triade evento → valutazione →
attestato, cioè il flusso ECM. La licenza LGPL degli addon community consente
l'uso come libreria senza contaminare, ma va confermata modulo per modulo.

**Cosa prendere:** il *modello relazionale* di `event.registration ↔ crm.lead ↔
sale.order` e le regole di `survey` con soglia di superamento. Non il codice: la
dipendenza dal framework Odoo è totale.

---

## 11. `civicrm/civicrm-core` — il modello dati più vicino all'ECM (AGPL-3)

È il progetto meno citato e forse il più pertinente. CiviCRM modella nativamente
**contatti + partecipanti a eventi + membership + contributi**, cioè la stessa
struttura di un provider ECM: la persona esiste indipendentemente dall'evento,
partecipa a più eventi nel tempo, accumula stati e diritti.

**Da prendere:** lo schema `Contact / Participant / Event / ParticipantStatus`
(con stati registrato, presente, cancellato, in lista d'attesa) e il concetto di
APIv4 come layer unico su cui tutto passa. È la mappa concettuale su cui
costruire la relazione professionista ↔ evento ↔ crediti nel tempo.

---

## 12–13. Mautic e Chatwoot

**Mautic** (Symfony; bundle `CampaignBundle`, `LeadBundle`, `EmailBundle`,
`FormBundle`, `ReportBundle`): da prendere il modello di **campagna a grafo**
(trigger, decisioni, azioni con attese temporali) e il **lead scoring per
punti**. Per un provider ECM serve per gli inviti mirati per professione e
disciplina e per i reminder a più stadi. Utilizzabile anche come servizio
separato invece che come codice.

**Chatwoot** (Rails + Vue): inbox omnicanale (email, WhatsApp, Telegram, SMS,
live chat), help center, note private, assegnazione automatica, CSAT, e
l'agente AI "Captain". Per il supporto ai partecipanti (domande su iscrizione,
attestato, crediti) è la scorciatoia migliore: si integra come servizio, non si
copia. Attenzione: la directory `enterprise/` ha licenza commerciale separata.

---

## 14–16. Eventi scientifici e ticketing

**pretalx** (Apache-2.0 ✅ — la licenza più permissiva del gruppo eventi):
Django, app `submission`, `cfp`, `orga`, `schedule`, `person`, `agenda`, `mail`,
`api`. Se il workflow di call for papers di Indico risultasse troppo pesante,
pretalx è l'unica alternativa che si può integrare e modificare senza vincoli
AGPL. Da prendere: il modello di **review con punteggi e conflitti di interesse**
e la gestione dello **schedule versionato** (le release di programma).

**pretix** (AGPLv3 con termini aggiuntivi): ticketing, check-in, fatturazione,
API. Da prendere il modello di **check-in list** (liste multiple per evento, con
regole di ingresso) — che è precisamente ciò che manca a Indico per l'ECM.

**alf.io** (GPL-3.0, Java 17 + Spring Boot + Postgres): validazione QR, badge
printing, fatturazione, admin API, app di check-in. È il riferimento più solido
per la **presenza rilevata**: token di validazione, anti-riuso, check-in offline
con sincronizzazione. Da studiare, non da integrare (stack Java isolato).

---

## 5. `indico/indico-plugins` (MIT) ⭐

Plugin verificati: `citadel`, `cloud_captchas`, `livesync`, `livesync_debug`,
`owncloud`, `payment_manual`, `payment_paypal`, `payment_sixpay`,
`payment_stripe`, `piwik`, `previewer_code`, `previewer_jupyter`, `prometheus`,
`storage_s3`, `themes_legacy`, `ursh`, `vc_dummy`, `vc_zoom`.

**Il plugin più importante da studiare è `livesync`**: è il meccanismo con cui
Indico esporta le modifiche verso sistemi esterni in modo incrementale e
affidabile. È esattamente l'infrastruttura che serve per tenere sincronizzati
Indico e il CRM senza polling. Subito dopo: `payment_stripe` come modello di
plugin di pagamento, `vc_zoom` come modello di integrazione con provider esterni
(utile per il webinar FAD), `storage_s3` per gli attestati, `prometheus` per il
monitoraggio.

---

## 17–19. Firma, scheduling, alternative

**Documenso** (AGPL-3.0, firme PAdES, audit log, API tRPC): per la firma
digitale degli attestati ECM e dei contratti faculty/sponsor. Da usare come
servizio separato — modificarlo attiverebbe l'AGPL.

**Cal.com / Cal.diy** (⚠️ il repository oggi si presenta come Cal.diy sotto MIT):
scheduling per call commerciali e disponibilità faculty. Basso valore
architetturale, alto valore operativo. Integrabile via API.

**OSEM** (`openSUSE/osem`, Rails) ⚠️: modello conferenza alternativo, superato
da Indico e pretalx per i nostri scopi. Nessuna parte da estrarre.

---

## 20–22. Orchestrazione — la scelta critica

| Opzione | Licenza | Verdetto |
|---|---|---|
| **n8n** | Sustainable Use License ✅ | ⛔ **Da escludere.** La licenza vieta di offrire a terzi un prodotto che sia sostanzialmente n8n. Un provider ECM che vende la piattaforma o la offre a partner viola la licenza. Utilizzabile solo per automazioni interne, mai come componente del prodotto |
| **Temporal** | MIT ⚠️ | ✅ Workflow durabili, retry, timer di giorni o settimane, compensazioni. È lo strumento giusto per "invito → reminder → check-in → questionario → attestato", che è un processo lungo settimane |
| **LangGraph** | MIT ⚠️ | ✅ Orchestrazione degli agenti a grafo con stato, checkpointing e human-in-the-loop nativo. Da usare *dentro* i singoli step Temporal, non al posto suo |

La combinazione corretta è **Temporal per il processo di business** (lungo,
deterministico, con scadenze regolatorie) e **LangGraph per il ragionamento
dell'agente** (breve, non deterministico, revisionabile).

---

## Cosa non prendere da nessuno

Un elenco altrettanto importante, perché il rischio principale in un progetto
composito è ereditare complessità che non serve:

- **Il multi-tenant a schema dinamico** (Twenty): serve a un SaaS con migliaia di
  workspace, non a un provider ECM.
- **I metamodelli a oggetti** (EspoCRM, SuiteCRM) se si è già scelto Relaticle:
  due sistemi di campi custom nello stesso prodotto sono un debito garantito.
- **Il codice legacy SugarCRM** (SuiteCRM).
- **Kafka, Weaviate, Keycloak, Kubernetes** insieme (Multi-Agent CRM): Postgres,
  Redis e un buon reverse proxy coprono il 95% del bisogno.
- **Qualsiasi calcolo di crediti scritto da altri**: nessun progetto open source
  implementa le regole ECM italiane. Ciò che si trova va ignorato, non adattato.
- **Le librerie di certificazione generiche**: l'attestato ECM ha requisiti di
  numerazione, verificabilità e revoca che vanno progettati sul regolamento del
  provider, non ereditati.
