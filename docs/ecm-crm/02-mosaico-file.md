# Il mosaico dei file — cosa estrarre, da dove, verso dove

Ogni albero indica i percorsi reali dei repository sorgente e l'azione da
compiere su ciascuno.

**Azioni:**
`[RIUSA]` codice da usare così com'è · `[ESTENDI]` da estendere con logica ECM ·
`[MODELLO]` da studiare e reimplementare (non copiare) · `[IGNORA]` fuori scopo.

**Affidabilità:** ✅ verificato · ○ indicativo.

---

## Tessera A — Motore eventi · `indico/indico` (MIT) ✅

Tutti i percorsi seguenti sono stati letti dal filesystem di questo repository.

```text
indico/
├── indico/
│   ├── core/                                          ✅
│   │   ├── plugins/                    [RIUSA]    ← su questo si innesta il modulo ECM
│   │   │   ├── __init__.py                            (IndicoPlugin, PluginCategory)
│   │   │   ├── alembic/                               (migrazioni per plugin)
│   │   │   ├── blueprint.py · controllers.py · views.py
│   │   ├── signals/                    [RIUSA]    ← hook per intercettare gli eventi di dominio
│   │   ├── celery/                     [RIUSA]    ← task asincroni: reminder, export, PDF
│   │   ├── db/                         [RIUSA]    ← SQLAlchemy, alembic, tipi custom
│   │   ├── storage/                    [RIUSA]    ← backend file (locale/S3) per attestati
│   │   ├── oauth/                      [RIUSA]    ← autenticazione delle app esterne
│   │   ├── settings/                   [RIUSA]    ← settings tipizzati per evento/plugin
│   │   ├── permissions.py              [ESTENDI]  ← nuovi permessi: ecm_manager, ecm_auditor
│   │   ├── notifications.py · emails.py [RIUSA]
│   │   ├── cache.py · limiter.py · logger.py · sentry.py  [RIUSA]
│   │   └── marshmallow.py              [RIUSA]    ← schemi di serializzazione API
│   │
│   ├── modules/
│   │   ├── events/                                    ✅
│   │   │   ├── models/
│   │   │   │   ├── events.py           [ESTENDI]  ← + tipo attività ECM, provider, id accreditamento
│   │   │   │   ├── persons.py          [ESTENDI]  ← EventPerson: base per la faculty
│   │   │   │   ├── principals.py       [RIUSA]    ← ACL granulari
│   │   │   │   ├── references.py       [MODELLO]  ← riferimenti esterni: modello per il codice ECM
│   │   │   │   ├── roles.py            [ESTENDI]  ← ruoli ECM: responsabile scientifico, tutor, docente
│   │   │   │   ├── reviews.py · labels.py · series.py · settings.py  [RIUSA]
│   │   │   ├── management/             [ESTENDI]  ← aggiungere il tab "ECM" alla gestione evento
│   │   │   ├── registration/           ⭐ nucleo dei dati partecipante
│   │   │   │   ├── models/
│   │   │   │   │   ├── registrations.py [ESTENDI] ← Registration.checked_in / checked_in_dt (riga ~220)
│   │   │   │   │   │                               solo booleano a livello evento: insufficiente per ECM
│   │   │   │   │   ├── forms.py         [RIUSA]   ← RegistrationForm: più form per evento
│   │   │   │   │   ├── form_fields.py   [RIUSA]   ← campi e dati salvati
│   │   │   │   │   ├── items.py         [RIUSA]   ← sezioni e voci del form
│   │   │   │   │   ├── invitations.py   [RIUSA]   ← inviti nominali: base per l'invito mirato per disciplina
│   │   │   │   │   ├── tags.py          [RIUSA]   ← etichette partecipante
│   │   │   │   │   └── legacy_mapping.py [IGNORA]
│   │   │   │   ├── fields/
│   │   │   │   │   ├── base.py          [MODELLO] ← come si scrive un tipo di campo custom
│   │   │   │   │   ├── choices.py       [RIUSA]   ← scelte singole/multiple, quote
│   │   │   │   │   ├── simple.py        [RIUSA]   ← testo, numero, data, checkbox
│   │   │   │   │   ├── sessions.py      [ESTENDI] ⭐ scelta delle sessioni: gancio per la presenza per sessione
│   │   │   │   │   ├── accompanying.py  [RIUSA]
│   │   │   │   │   └── affiliation.py   [ESTENDI] ← affiliazione: mappare su struttura sanitaria
│   │   │   │   ├── controllers/
│   │   │   │   │   ├── api/
│   │   │   │   │   │   ├── checkin.py   [ESTENDI] ⭐ API dell'app di check-in
│   │   │   │   │   │   ├── checkin_legacy.py [IGNORA]
│   │   │   │   │   │   └── misc.py      [RIUSA]
│   │   │   │   │   ├── management/      [ESTENDI] ← reglists.py, regforms.py, tickets.py, fields.py
│   │   │   │   │   └── display.py       [ESTENDI] ← area partecipante: aggiungere attestati e crediti
│   │   │   │   ├── badges.py            [RIUSA]   ← badge del partecipante
│   │   │   │   ├── wallets/             [RIUSA]   ← ticket Apple/Google Wallet
│   │   │   │   ├── stats.py             [MODELLO] ← statistiche registrazioni
│   │   │   │   ├── tasks.py             [ESTENDI] ← task periodici: aggiungere i reminder ECM
│   │   │   │   ├── notifications.py     [ESTENDI] ← email di conferma: aggiungere attestato pronto
│   │   │   │   ├── placeholders/        [ESTENDI] ← segnaposto email: crediti, ore, codice attestato
│   │   │   │   ├── schemas.py           [RIUSA]   ← serializzazione per API
│   │   │   │   ├── clone.py             [RIUSA]   ← clonazione edizione successiva
│   │   │   │   └── logging.py           [RIUSA]   ← traccia delle modifiche alle registrazioni
│   │   │   ├── timetable/               [ESTENDI] ← models/, operations.py, reschedule.py
│   │   │   │                                        ogni voce diventa un'unità di ore formative
│   │   │   ├── sessions/                [ESTENDI] ← models/: la sessione è l'unità di presenza ECM
│   │   │   ├── contributions/           [ESTENDI] ← + relatore, durata, obiettivo formativo
│   │   │   │   └── contrib_fields.py    [MODELLO] ← campi custom per contributo
│   │   │   ├── tracks/                  [RIUSA]   ← aree tematiche
│   │   │   ├── abstracts/               [RIUSA]   ← raccolta e revisione abstract
│   │   │   ├── papers/                  [IGNORA]  ← peer review proceedings: fuori scopo ECM
│   │   │   ├── editing/                 [IGNORA]
│   │   │   ├── persons/                 [ESTENDI] ⭐ faculty: CV, dichiarazioni, conflitti d'interesse
│   │   │   ├── agreements/              [ESTENDI] ⭐ base per le dichiarazioni firmate della faculty
│   │   │   │   ├── base.py · models/ · notifications.py
│   │   │   ├── requests/                [ESTENDI] ⭐ workflow di richiesta con approvazione:
│   │   │   │   ├── base.py · models/                base ideale per la domanda di accreditamento
│   │   │   ├── surveys/                 [ESTENDI] ⭐ questionari
│   │   │   │   ├── models/surveys.py · items.py · submissions.py · anonymous_submissions.py
│   │   │   │   ├── fields/              [ESTENDI] ← + campo a risposta corretta e punteggio
│   │   │   │   └── tasks.py             [RIUSA]
│   │   │   ├── payment/                 [RIUSA]   ← models/, plugins.py
│   │   │   ├── reminders/               [ESTENDI] ← promemoria evento
│   │   │   ├── notes/ · attachments/    [RIUSA]   ← materiali didattici
│   │   │   ├── features/                [RIUSA]   ← attivazione funzionalità per evento
│   │   │   ├── layout/ · themes.yaml    [RIUSA]
│   │   │   ├── roles/                   [ESTENDI]
│   │   │   ├── cloning.py · clone.py    [RIUSA]   ← duplicazione edizioni
│   │   │   ├── ical.py                  [RIUSA]
│   │   │   └── export.py · export.yaml  [MODELLO] ← modello di export strutturato
│   │   │
│   │   ├── receipts/                    ⭐⭐ base degli attestati ECM  ✅
│   │   │   ├── models/templates.py      [ESTENDI] ← template documento per evento/categoria
│   │   │   ├── models/files.py          [ESTENDI] ← file generati: aggiungere numerazione e hash
│   │   │   ├── default_templates/
│   │   │   │   ├── attendance/
│   │   │   │   │   ├── template.html    [ESTENDI] ⭐ "Certificate of Attendance" già esistente
│   │   │   │   │   ├── theme.css        [ESTENDI]
│   │   │   │   │   └── metadata.yaml    [ESTENDI]
│   │   │   │   └── receipt/             [RIUSA]   ← ricevuta di pagamento
│   │   │   ├── controllers/ · schemas.py · util.py  [ESTENDI]
│   │   │   └── settings.py              [RIUSA]
│   │   │
│   │   ├── designer/                    ← badge e poster (NON events/badges)  ✅
│   │   │   ├── models/templates.py      [RIUSA]   ← template grafici
│   │   │   ├── models/images.py         [RIUSA]
│   │   │   ├── pdf.py                   [RIUSA]   ← rendering PDF
│   │   │   └── placeholders.py          [ESTENDI] ← + segnaposto QR di check-in ECM
│   │   │
│   │   ├── logs/                        ← audit (NON events/logs)  ✅
│   │   │   ├── models/entries.py        [ESTENDI] ⭐ voce di log: base dell'audit regolatorio
│   │   │   └── renderers.py             [ESTENDI]
│   │   │
│   │   ├── users/                       ✅
│   │   │   ├── models/users.py          [ESTENDI] ← + profilo professionista sanitario
│   │   │   ├── models/affiliations.py   [ESTENDI] ← + struttura sanitaria di appartenenza
│   │   │   ├── models/emails.py · favorites.py · settings.py  [RIUSA]
│   │   │   └── models/export.py         [RIUSA]   ← export dati utente (GDPR)
│   │   ├── groups/                      [RIUSA]
│   │   ├── auth/                        [ESTENDI] ← + SSO/SPID/CIE se richiesto
│   │   ├── oauth/                       [RIUSA]   ← app esterne e token
│   │   ├── categories/                  [ESTENDI] ← + provider ECM come categoria radice
│   │   ├── rb/                          ← sale (NON events/rooms)  ✅
│   │   │   ├── models/ · api.py · event/  [RIUSA]
│   │   ├── vc/                          [RIUSA]   ← videoconferenza: base per la FAD sincrona
│   │   ├── attachments/ · files/        [RIUSA]
│   │   ├── legal/                       [ESTENDI] ⭐ privacy policy e consensi
│   │   ├── api/                         [ESTENDI] ← HTTP API legacy + export
│   │   ├── search/                      [RIUSA]
│   │   ├── admin/                       [RIUSA]
│   │   ├── announcement/ · news/ · cephalopod/ · networks/  [IGNORA]
│   │   └── bootstrap/                   [RIUSA]
│   │
│   ├── models/                          [RIUSA]   ← modelli base condivisi
│   ├── web/                             [ESTENDI] ← rotte, flask, asset
│   ├── util/                            [RIUSA]
│   └── migrations/                      [ESTENDI]
├── docs/source/                         [MODELLO]
├── pyproject.toml · hatch_build.py      [RIUSA]
└── Makefile · webpack/                  [RIUSA]
```

**I quattro punti di innesto del modulo ECM su Indico:**

1. `indico/core/plugins/` — il plugin `indico_ecm` si registra qui.
2. `indico/core/signals/` — si intercettano registrazione creata, check-in
   effettuato, survey inviata, pagamento completato.
3. `indico/modules/events/registration/controllers/api/checkin.py` — si estende
   l'API di check-in per la presenza per sessione con entrata e uscita.
4. `indico/modules/receipts/` — si estende il template attestato con crediti,
   numerazione e QR di verifica.

---

## Tessera A2 — Pattern di integrazione · `indico/indico-plugins` (MIT) ✅

```text
indico-plugins/
├── livesync/                 [MODELLO] ⭐⭐ sincronizzazione incrementale verso l'esterno:
│                                        è il pattern per tenere allineati Indico e CRM
├── livesync_debug/           [MODELLO]
├── payment_stripe/           [RIUSA]   ← plugin di pagamento pronto
├── payment_paypal/           [RIUSA]
├── payment_sixpay/           [IGNORA]
├── payment_manual/           [RIUSA]   ← bonifico: modalità comune nei provider ECM
├── vc_zoom/                  [RIUSA]   ⭐ FAD sincrona: presenza da report Zoom
├── vc_dummy/                 [MODELLO] ← scheletro di un provider di videoconferenza
├── storage_s3/               [RIUSA]   ← archiviazione attestati
├── prometheus/               [RIUSA]   ← metriche
├── piwik/                    [IGNORA]
├── citadel/                  [IGNORA]  ← ricerca full-text (servizio CERN)
├── previewer_code/ jupyter/  [IGNORA]
├── cloud_captchas/           [RIUSA]
├── owncloud/ · ursh/         [IGNORA]
└── themes_legacy/            [IGNORA]
```

---

## Tessera B — CRM core · `Relaticle/relaticle` (AGPL-3.0) ✅ top-level

```text
relaticle/
├── app/                                  ○ struttura Laravel standard
│   ├── Models/                [MODELLO] ← Company, Person, Opportunity, Task, Note, Team
│   ├── Policies/              [MODELLO] ⭐ autorizzazione a 5 livelli con isolamento team
│   ├── Filament/              [RIUSA]   ← UI amministrativa generata dalle risorse
│   ├── Http/Controllers/      [RIUSA]   ← API REST
│   ├── Http/Middleware/       [RIUSA]   ← tenancy e autenticazione
│   ├── Services/              [MODELLO]
│   ├── Jobs/                  [MODELLO] ← code Laravel su Redis
│   └── Providers/             [RIUSA]
├── packages/                  [MODELLO] ⭐ qui vivono custom fields (22 tipi) e server MCP (30 tool)
├── database/
│   ├── migrations/            [MODELLO] ← schema CRM di riferimento
│   ├── seeders/ · factories/  [RIUSA]   ← dati di test
├── routes/
│   ├── api.php                [RIUSA]   ⭐ superficie API su cui si appoggiano gli agenti
│   ├── web.php · console.php  [RIUSA]
├── resources/ · lang/         [ESTENDI] ← traduzione italiana
├── config/ · storage/         [RIUSA]
└── docs/                      [MODELLO] ← documentazione MCP e API
```

**Attenzione architetturale:** i dati regolatori ECM non vanno nei custom field
di Relaticle. Il confine è netto — Relaticle possiede la relazione commerciale,
l'ECM Service possiede i dati che finiscono in un attestato.

---

## Tessera C — Modello dati CRM · `twentyhq/twenty` (AGPL ⚠️) ✅ modules

```text
twenty/packages/twenty-server/src/modules/          ✅ elenco verificato
├── person/standard-objects/        [MODELLO] ← anagrafica persona
├── company/standard-objects/       [MODELLO] ← anagrafica azienda
├── opportunity/standard-objects/   [MODELLO] ← pipeline commerciale
├── attachment/standard-objects/    [MODELLO]
├── note/ · task/                   [MODELLO]
├── timeline/                       [MODELLO] ⭐ timeline unificata per record
├── workflow/                       [MODELLO] ⭐⭐ automazioni dichiarative trigger→azione
├── messaging/                      [MODELLO] ⭐ ingestione email
├── messaging-webhooks/             [MODELLO]
├── calendar/                       [MODELLO] ⭐ ingestione eventi calendario
├── connected-account/              [MODELLO] ← account Google/Microsoft collegati
├── connected-account-sync-webhooks/[MODELLO]
├── contact-creation-manager/       [MODELLO] ⭐⭐ crea contatti da email e inviti
├── match-participant/              [MODELLO] ⭐ associa partecipanti email→persona
├── blocklist/                      [MODELLO] ⭐ esclusione domini e indirizzi privati
├── emailing/                       [MODELLO]
├── dashboard/ · dashboard-sync/    [MODELLO]
├── call-recording/                 [MODELLO]
├── workspace-member/               [MODELLO]
└── onboarding-invite-suggestions/  [IGNORA]
```

La catena `connected-account → messaging + calendar → match-participant →
contact-creation-manager → timeline` è il modo giusto per popolare l'anagrafica
di un provider ECM: i contatti nascono dal lavoro reale, non dal data entry.

---

## Tessera D — Runtime agenti · `trycompai/crm` (MIT) ✅

```text
crm/
├── apps/
│   ├── agent/                  ⭐⭐ il cuore da riusare                    ✅
│   │   ├── tools/          [MODELLO] ← 18 tool tipizzati
│   │   ├── skills/         [MODELLO] ⭐⭐ 4 skill come prosa versionata
│   │   ├── schedules/      [MODELLO] ← esecuzioni programmate
│   │   ├── sandbox/        [MODELLO] ⭐ bash/grep/glob, senza DB e senza egress
│   │   └── queue/          [MODELLO] ⭐⭐ leasing con FOR UPDATE SKIP LOCKED
│   ├── api/                [MODELLO] ← NestJS + tRPC tipizzato
│   └── app/                [IGNORA]  ← frontend Next.js del loro dominio
├── packages/
│   ├── db/                 [MODELLO] ← schema Prisma: guardare le tabelle di run/job
│   ├── auth/               [MODELLO]
│   ├── env/                [RIUSA]   ← gestione variabili d'ambiente tipizzata
│   └── ui/                 [IGNORA]
└── docker/ · docs/         [MODELLO]
```

○ I nomi delle sottocartelle di `apps/agent/` sono indicativi: la pagina
conferma tool, skill, schedule e sandbox come componenti, non l'esatta gerarchia.

---

## Tessera E — Governance agenti · `Mrgig7/Multi-Agent-Enterprise-CRM` (MIT) ✅

```text
Multi-Agent-Enterprise-CRM/
├── agents/            [MODELLO] ⭐ sales · support · compliance · analytics · knowledge
├── policies/          [MODELLO] ⭐⭐ Open Policy Agent: autorizzazioni fuori dal prompt
├── core_services/     [MODELLO]
├── gateway/           [MODELLO] ← ingresso unico verso gli agenti
├── observability/     [MODELLO] ⭐ tracing delle decisioni
├── schemas/           [MODELLO] ⭐ contratti di messaggio fra agenti
├── services/ · database/  [MODELLO]
├── deploy/            [IGNORA]  ← K8s: sovradimensionato
├── frontend/          [IGNORA]
├── tests/             [MODELLO]
└── docs/              [MODELLO] ← event sourcing con replay, kill switch
```

---

## Tessera F — Workflow scientifico · `pretalx/pretalx` (Apache-2.0) ✅

```text
pretalx/src/pretalx/                       ○ struttura app Django
├── submission/     [MODELLO] ⭐ proposta, stato, track, tipo di intervento
├── cfp/            [MODELLO] ← call for papers configurabile
├── orga/           [MODELLO] ⭐ revisione con punteggi e conflitti d'interesse
├── schedule/       [MODELLO] ⭐⭐ programma versionato con release e diff
├── person/         [MODELLO] ← speaker, disponibilità, biografia
├── agenda/         [MODELLO] ← vista pubblica
├── mail/           [MODELLO] ← template email per stato
├── api/            [MODELLO]
└── common/         [IGNORA]
```

Il **programma versionato** è la funzione che manca a Indico ed è rilevante per
l'ECM: se il programma cambia dopo l'accreditamento, serve sapere quale versione
era in vigore quando il partecipante era presente.

---

## Tessera G — Presenza e ticketing · `pretix` (AGPL) e `alf.io` (GPL) ✅

```text
pretix/src/pretix/                          ○
├── base/models/
│   ├── checkin.py      [MODELLO] ⭐⭐ CheckinList: liste multiple con regole di ingresso
│   ├── orders.py       [MODELLO] ← ordine, posizione, stato
│   └── invoices.py     [MODELLO] ← fatturazione
├── control/            [MODELLO] ← backoffice
├── api/                [MODELLO] ⭐ API di check-in usata dall'app mobile
└── presale/            [IGNORA]

alf.io/src/main/java/alfio/                 ○
├── manager/CheckInManager       [MODELLO] ⭐⭐ validazione QR, anti-riuso, stati
├── manager/TicketReservationManager [MODELLO]
├── controller/api/admin/        [MODELLO] ← admin API
└── util/                        [IGNORA]
```

Da queste due tessere si prende **il modello di presenza** che Indico non ha:
liste di check-in multiple per evento, regole per lista, token firmato nel QR,
protezione dal riuso, e sincronizzazione dei dispositivi offline.

---

## Tessera H — Marketing e supporto ✅ (top-level)

```text
mautic/app/bundles/
├── CampaignBundle/   [MODELLO] ⭐⭐ campagna a grafo con attese e decisioni
├── LeadBundle/       [MODELLO] ⭐ segmenti dinamici e lead scoring a punti
├── EmailBundle/      [MODELLO] ← invio, tracciamento, template
├── FormBundle/       [MODELLO] ← form e landing
├── ReportBundle/     [MODELLO]
└── (altri bundle)    [IGNORA]

chatwoot/
├── app/models/       [MODELLO] ← conversation, inbox, contact, label
├── app/javascript/   [IGNORA]
├── enterprise/       [IGNORA]  ⚠️ licenza commerciale separata
└── (usare come servizio integrato via API, non come codice)
```

---

## Tessera I — Modello partecipante nel tempo · `civicrm/civicrm-core` (AGPL) ✅

```text
civicrm-core/                                  ○
├── CRM/Contact/     [MODELLO] ⭐ il contatto esiste indipendentemente dagli eventi
├── CRM/Event/       [MODELLO] ⭐⭐ Participant, ParticipantStatus, ParticipantRole
├── CRM/Member/      [MODELLO] ⭐ membership con periodi di validità
├── CRM/Contribute/  [MODELLO] ← contributi e pagamenti
├── Civi/Api4/       [MODELLO] ⭐ un solo layer API per tutto
└── templates/       [IGNORA]
```

Lo stato del partecipante come macchina a stati (`registered`, `attended`,
`no-show`, `cancelled`, `waitlisted`, `partially attended`) è il modello da
adottare per la presenza ECM.

---

## Tessera J — Precedente completo · `odoo/odoo` (LGPL ⚠️) ✅ addon

```text
odoo/addons/
├── event/              [MODELLO] ⭐ event.registration: il partecipante come record
├── event_crm/          [MODELLO] ⭐⭐ ponte evento → lead CRM
├── event_sale/         [MODELLO] ⭐ evento → ordine → fattura
├── event_booth/ _sale/ [MODELLO] ⭐ stand sponsor venduti: rilevante per i provider
├── event_product/      [MODELLO] ← quote come prodotti
├── event_sms/          [MODELLO]
├── crm/                [MODELLO] ← pipeline, stadi, attività
├── crm_iap_enrich/     [MODELLO] ← arricchimento automatico dell'azienda
├── crm_sms/ _livechat/ [MODELLO]
├── calendar/           [MODELLO]
├── account*/           [MODELLO] ← fatturazione elettronica, PEPPOL
├── survey/             [MODELLO] ⭐⭐ questionario con certificazione e punteggio minimo  ○
├── slides/             [MODELLO] ⭐ e-learning con attestato: modello per la FAD  ○
└── sign/               [MODELLO] ← firma documenti  ○
```

○ `survey`, `slides` e `sign` non erano visibili nella porzione di pagina
fetchata: esistono in Odoo ma il percorso va confermato.

---

## Tessera K — Firma digitale · `documenso/documenso` (AGPL) ✅

```text
documenso/
├── apps/          [MODELLO] ← applicazione di firma
├── packages/      [MODELLO] ⭐ firme PAdES, certificati, audit log
├── docker/        [RIUSA]   ← deployment come servizio separato
└── scripts/       [IGNORA]
```

Da usare **come servizio esterno** chiamato via API: firma dell'attestato ECM,
contratti faculty, accordi sponsor. Modificarlo attiverebbe l'AGPL.

---

## Tessera L — CRM alternativi (riferimento) ✅ top-level

```text
espocrm/
├── application/Espo/Resources/metadata/   [MODELLO] ⭐⭐ entità e campi come JSON
├── application/Espo/Core/                 [MODELLO] ← ORM, ACL, hook
├── application/Espo/Modules/Crm/          [MODELLO] ← Account, Contact, Lead, Opportunity
├── client/ · frontend/                    [IGNORA]
└── install/ · tests/                      [IGNORA]

SuiteCRM/
├── modules/            [MODELLO] ← checklist funzionale: Contracts, Quotes, Cases, Campaigns
├── Api/                [MODELLO] ← API V8
├── include/ metadata/  [IGNORA]  ← legacy SugarCRM
└── themes/ install/    [IGNORA]

krayin/laravel-crm/
├── packages/Webkul/    [MODELLO] ⭐ CRM MIT modulare: alternativa modificabile e chiudibile
├── app/ config/ routes/[RIUSA]
└── database/           [MODELLO]

frappe/crm/
└── crm/integrations/   [MODELLO] ⭐ Twilio ed Exotel: modello per il recall telefonico
```

---


## Tessera M — Runtime agentico · `trycompai/crm` (MIT) ✅ — inventario reale

Struttura verificata file per file (ramo `main`). È la tessera da cui viene
l'architettura dello strato agentico: i marcatori qui sotto indicano che cosa ha
fatto da **modello**, non file da copiare — nel risultato nulla è stato copiato,
tutto riscritto in Python. Dettaglio in [03-agenti-ai.md](03-agenti-ai.md).

```text
crm/apps/agent/
├── agent/
│   ├── agent.ts                [MODELLO] ← definizione dell'agente
│   ├── instructions.md         [MODELLO] ← prosa di sistema; qui riscritta per l'ECM
│   ├── instructions/           [MODELLO]
│   ├── tools/                  [MODELLO] ⭐⭐ 27 tool, uno per file
│   │   ├── read_crm_history.ts · read_company_history.ts · read_deal_history.ts
│   │   ├── search_crm.ts · identify_contact.ts · list_deals.ts
│   │   ├── list_fields.ts · manage_fields.ts · set_field_value.ts · archive_field.ts
│   │   ├── list_outstanding_work.ts · record_fact.ts · record_job_change.ts
│   │   ├── research_person.ts · research_company.ts · enrich_company.ts
│   │   ├── get_linkedin_profile.ts · resolve_linkedin_profile.ts
│   │   ├── find_contact_socials.ts · set_contact_socials.ts
│   │   ├── get_contact_work_history.ts · fetch_contact_photo.ts
│   │   ├── schedule_recheck.ts · write_brief.ts · write_workspace_profile.ts
│   │   └── set_chat_title.ts · agent.ts
│   ├── skills/                 [MODELLO] ⭐⭐ l'idea della skill come prosa versionata
│   │   ├── evidence.md · identity-matching.md
│   │   └── data-boundaries.md · writing-a-brief.md
│   ├── schedules/dispatch.ts   [MODELLO] ⭐⭐⭐ dispatcher dei task scaduti
│   ├── lib/                    [MODELLO] ⭐⭐⭐ 35 file — i critici:
│   │   ├── tasks.ts            ⭐⭐⭐ coda con claimDue e leasing
│   │   ├── dispatch.ts · run-runtime.ts · run-state.ts   ⭐⭐⭐ run durabili
│   │   ├── evidence.ts · facts.ts                        ⭐⭐⭐ provenienza
│   │   ├── approval.ts                                   ⭐⭐⭐ human-in-the-loop
│   │   ├── capabilities.ts · focus.ts · session-purpose.ts · preamble.ts
│   │   ├── crm.ts · lookup.ts · names.ts · fields.ts
│   │   ├── model.ts · pool.ts · research-instructions.ts
│   │   ├── perplexity.ts · linkdapi.ts · context-dev.ts · enrichment.ts  ⚠️ fonti esterne
│   │   ├── builder-*.ts · custom-agent-dispatch.ts       ⏸ fase 2
│   │   ├── app-auth.ts · accounts.ts · workspace.ts      [IGNORA] auth sostituita da Indico
│   │   └── brand*.ts · portrait*.ts · socials.ts         [IGNORA] fuori scopo
│   ├── hooks/                  [MODELLO] ⭐ activity.ts · audit.ts · telemetry.ts
│   ├── sandbox/                [MODELLO] ⭐⭐ sandbox.ts + workspace/ (niente DB, niente egress)
│   ├── subagents/              [MODELLO] ⏸ agent_builder/ · agent_runner/
│   └── channels/               [MODELLO] crm.ts · eve.ts
├── evals/                      [MODELLO] ⭐ test di comportamento: da non saltare
├── scripts/ · test/            [MODELLO]
└── package.json · turbo.json   [IGNORA]
```

Fuori da `apps/agent/`: `apps/api` (NestJS/tRPC) e `packages/db` (Prisma)
servono come **modello dello schema** dei task e dei run; `apps/app` (frontend
del loro dominio) e `packages/ui` si ignorano — l'interfaccia è quella di Indico.

---

## Il mosaico assemblato — albero di destinazione

Un solo gestionale: Indico con quattro plugin proprietari. Ogni foglia riporta la
tessera d'origine; `[NUOVO]` = da scrivere ex novo, nessun open source lo
fornisce.

```text
indico-ecm/                                  ← questo repository (fork MIT)
│
├── indico/                                  ← CORE, aggiornabile da upstream
│   ├── core/                                ⟵ A: plugins, signals, celery, db, storage, oauth
│   ├── modules/                             ⟵ A: events, registration, timetable, surveys,
│   │   │                                          receipts, designer, rb, logs, vc, users
│   │   └── events/registration/controllers/api/checkin.py
│   │                              ⚠️ UNICA modifica al core: presenza per sessione
│   │                              ⟵ A + G (pretix CheckinList, alf.io CheckInManager)
│   └── web/ · models/ · migrations/         ⟵ A
│
└── plugins/
    │
    ├── indico_crm/                          ← CRM NATIVO
    │   ├── models/
    │   │   ├── companies.py                 ⟵ B app/Models · C company · J crm
    │   │   ├── contacts.py                  ⟵ B · C person · I CRM/Contact
    │   │   ├── hcp_profiles.py              [NUOVO] ⭐⭐ professionista sanitario
    │   │   ├── organization_links.py        ⟵ I (relazione nel tempo)
    │   │   ├── opportunities.py             ⟵ C opportunity · J crm · L SuiteCRM
    │   │   ├── contracts.py · quotes.py · invoices.py  ⟵ L (checklist) · J account
    │   │   ├── activities.py · tasks.py · notes.py     ⟵ B · C task/note
    │   │   ├── communications.py            ⟵ C messaging · M lib/crm.ts
    │   │   ├── consents.py                  [NUOVO] ⟵ A modules/legal
    │   │   ├── evidence.py                  ⟵ M lib/evidence.ts + facts.ts  ⭐⭐
    │   │   ├── timeline.py                  ⟵ C timeline
    │   │   └── links.py                     [NUOVO] ⭐⭐ ponte verso gli oggetti Indico
    │   ├── services/
    │   │   ├── identity_service.py          ⟵ M identify_contact + skill identity-matching
    │   │   ├── enrichment_service.py        ⟵ M enrich_company · research_company
    │   │   ├── pipeline_service.py          ⟵ J crm · L SuiteCRM
    │   │   ├── followup_service.py          ⟵ M schedule_recheck
    │   │   ├── evidence_service.py          ⟵ M lib/evidence.ts
    │   │   └── consent_service.py           [NUOVO]
    │   ├── signals.py                       ⟵ A core/signals ⭐ innesto sul core
    │   ├── controllers/ · forms/ · client/ · templates/   ⟵ A (stile del core)
    │   ├── schemas.py · api/                ⟵ A marshmallow · B routes/api.php · I Api4
    │   └── migrations/ · tests/
    │
    ├── indico_ecm/                          ← DOMINIO REGOLATORIO  [tutto NUOVO]
    │   ├── models/
    │   │   ├── provider.py · accreditation.py        ⟵ pattern A events/requests
    │   │   ├── activity_type.py · learning_objective.py
    │   │   ├── session_attendance.py        ⭐ ⟵ A checkin.py + G CheckinList
    │   │   ├── attendance_adjustment.py     ⭐ rettifica tracciata
    │   │   ├── credit_rule.py               ⭐⭐⭐ versionata per anno e regione
    │   │   ├── credit_assignment.py         ⭐⭐⭐
    │   │   ├── assessment_result.py         ⟵ A surveys + J odoo survey (soglia)
    │   │   ├── certificate.py               ⟵ A receipts/models
    │   │   └── audit_record.py              ⟵ A logs/models/entries.py
    │   ├── services/
    │   │   ├── attendance_service.py        ⟵ G alf.io CheckInManager
    │   │   ├── credit_calculator.py         ⭐⭐⭐ deterministico · mai LLM
    │   │   ├── eligibility_service.py       ⭐⭐⭐ deterministico · mai LLM
    │   │   ├── certificate_service.py       ⟵ A receipts + K Documenso (firma)
    │   │   ├── reconciliation_service.py    ⟵ I ParticipantStatus
    │   │   └── export_service.py            ⟵ A export.yaml
    │   ├── templates/certificates/          ⟵ A receipts/default_templates/attendance ⭐
    │   ├── permissions.py · signals.py · tasks.py     ⟵ A core
    │   └── api/ · controllers/ · client/ · migrations/
    │
    ├── indico_agents/                       ← LAYER AGENTICO  ⟵ M (riscritto)
    │   ├── runtime/
    │   │   ├── tasks.py · leases.py         ⟵ M lib/tasks.ts (claimDue)      ⭐⭐⭐
    │   │   ├── dispatch.py                  ⟵ M schedules/dispatch.ts        ⭐⭐⭐
    │   │   ├── run_state.py · run_runtime.py⟵ M lib/run-state.ts, run-runtime.ts
    │   │   ├── model.py · pool.py · preamble.py · focus.py · capabilities.py  ⟵ M lib/
    │   ├── sandbox/worker.py · policy.py    ⟵ M sandbox/                     ⭐⭐
    │   ├── tools/
    │   │   ├── base.py · registry.py        [NUOVO]
    │   │   ├── crm/                         ⟵ M tools/ (27 tool, filtrati)
    │   │   ├── events/                      [NUOVO] ⟵ A (API Indico)
    │   │   ├── ecm/                         [NUOVO] ⭐ sola lettura sui dati regolatori
    │   │   └── comms/                       [NUOVO] ⟵ integrazioni
    │   ├── skills/                          ⟵ M skills/ (4) + 4 nuove ECM     ⭐⭐
    │   ├── agents/                          [NUOVO] 12 agenti ⟵ M agent.ts + E agents/
    │   ├── schedules/                       ⟵ M schedules/ + [NUOVO] ECM
    │   ├── governance/
    │   │   ├── approvals.py                 ⟵ M lib/approval.ts              ⭐⭐⭐
    │   │   ├── audit.py                     ⟵ M hooks/audit.ts + A modules/logs
    │   │   ├── telemetry.py                 ⟵ M hooks/telemetry.ts
    │   │   ├── policies.py                  ⟵ E policies/ (OPA)              ⭐⭐
    │   │   ├── kill_switch.py · budgets.py · redaction.py   [NUOVO]
    │   ├── channels/web.py · internal.py    ⟵ M channels/crm.ts, eve.ts
    │   ├── models/                          ⟵ M packages/db (schema task/run)
    │   ├── evals/                           ⟵ M evals/                        ⭐
    │   └── migrations/ · tests/
    │
    ├── indico_integrations/                 ← ADAPTER
    │   ├── google/gmail.py · calendar.py · oauth.py · sync.py
    │   │                                    ⟵ M integrazioni + C messaging/calendar
    │   ├── microsoft/                       [NUOVO]
    │   ├── enrichment/                      ⟵ M lib/perplexity.ts · linkdapi.ts · context-dev.ts
    │   ├── communications/                  ⟵ H Mautic (campagne, segmenti) · L frappe (telefonia)
    │   ├── webinar/zoom.py · teams.py       ⟵ A2 vc_zoom
    │   ├── payments/                        ⟵ A2 payment_stripe · A events/payment
    │   ├── signature/                       ⟵ K Documenso (servizio esterno)
    │   ├── support_inbox/                   ⟵ H Chatwoot (servizio esterno)
    │   ├── accounting/                      ⟵ J account_edi · account_peppol
    │   └── sync/outbox.py · livesync_bridge.py   ⟵ A2 livesync                ⭐⭐
    │
    └── (plugin upstream riusati)
        ├── payment_stripe/ · payment_manual/     ⟵ A2 [RIUSA]
        ├── vc_zoom/                              ⟵ A2 [RIUSA]
        ├── storage_s3/                           ⟵ A2 [RIUSA]
        └── prometheus/                           ⟵ A2 [RIUSA]
```

## Conteggio onesto

| Origine | Quota stimata del sistema finale |
|---|---|
| Indico riusato direttamente (MIT) | ~45% |
| Architettura di `trycompai/crm` (MIT) riscritta in Python — runtime, tool, skill, governance | ~15% |
| Pattern reimplementati da progetti AGPL/GPL (solo idee: modelli dati, presenze, campagne) | ~10% |
| **Codice ECM e CRM proprietario nuovo** | **~30%** |

Quel 30% è il valore commerciale della piattaforma: profilo del professionista
sanitario, presenza per sessione, regole crediti, attestati, export regolatori e
i tool ECM degli agenti. Il resto è infrastruttura che conviene non riscrivere.

## Confine da non attraversare

Nel mosaico ci sono due categorie di tessere che non vanno mescolate:

- **Codice riutilizzabile** — solo da progetti MIT: Indico, `trycompai/crm`,
  `indico-plugins`, Krayin. Copiare sarebbe lecito, purché si mantenga la nota
  di copyright originale nei file copiati. *In concreto l'unico codice
  riutilizzato è quello di Indico, che è la base del fork: da `trycompai/crm` è
  stata ripresa l'architettura e riscritta in Python, da Krayin nulla.*
- **Riferimento concettuale** — da progetti AGPL/GPL: Relaticle, Twenty,
  EspoCRM, SuiteCRM, Frappe, CiviCRM, Mautic, pretix, alf.io, Documenso,
  Chatwoot, Odoo. Si studiano gli schemi e i comportamenti, si riscrive
  autonomamente. Nessuna riga copiata.

Se una funzione di un progetto AGPL è troppo complessa per essere riscritta,
la risposta corretta non è copiarla: è usare quel progetto **come servizio
esterno non modificato** (è il caso di Documenso per le firme e Chatwoot per
l'inbox di supporto).
