# Da Cyberbrain alla piattaforma — cosa migrare e cosa no

`Michele-cyberpunk/Cyberbrain` è il gestionale eventi medici attualmente in uso
(Electron + JS, più una web app Next.js e una integrazione Gemini). Non è un
progetto open source da cui "prendere pezzi": è **il capitolato reale** del
provider, scritto in codice. Contiene le regole che gli utenti già usano ogni
giorno, e che la piattaforma non deve reinventare né peggiorare.

Analisi svolta su `f417c64` (clone del 2026-08).

## Cosa contiene, in breve ✅

| Area | File | Cosa fa |
|---|---|---|
| Gestione eventi | `CyberBrain2/js/views/events.js` (828 righe) | Anagrafica evento, checklist di preparazione, email di accreditamento, cruscotto scadenze |
| Stampa unione | `js/views/stampaUnione.js` (488) | Lettere di invito ai medici per ospedale, con template `.docx` |
| Grafica | `js/views/grafico.js` (859) | Brief grafico, palette per specialità, preparazione email |
| Specialità mediche | `js/utils/medical-identification.js` (143) | Riconosce la specialità dal testo e assegna una palette CMYK/RGB |
| Automator | `js/views/automator.js` (131) | Analisi AI di email e documenti per preparare un evento |
| Promemoria | `js/views/reminders.js` (210) | Scadenze e promemoria |
| Auth e sicurezza | `js/core/authSystem.js` (954), `rbac.js`, `security.js`, `secureStore.js` | Utenti, ruoli, cifratura locale, escaping |
| Web app | `app/` (Next.js) | UI moderna, API Gemini e generazione immagini |

## Il modello dati reale dell'evento ✅

Ricavato da `events.js` e `utils.js`:

```text
evento (55 colonne)
├── identità            ├── workflow (17 colonne Sì/No)
│   ├── nomeEvento      │   ├── attivazione
│   ├── codiceEvento    │   ├── primoContattoRelatori
│   ├── cliente         │   ├── accreditamento
│   ├── dataEvento1/2   │   ├── contrattiSponsor
│   ├── citta · luogo   │   ├── opzioneSede · contrattoHotel · briefHotel
│   ├── orario          │   ├── catering · numePiattaforma
│   ├── tipoEvento      │   ├── grafica · stampaGrafiche
│   └── numeroPartec.   │   ├── letteraIncarico · slideKit
├── ECM                 │   ├── hostess · foglioLogistica
│   ├── codieAgenas     │   └── consuntivo · invio
│   ├── creditiEvento   ├── faculty
│   └── uecm            │   └── relatore1..5 + mail1..5
├── cartella            ├── fornitori
│   └── nomeCartella    │   └── emailNume · emailGrafico · emailHostess
└── accreditamento email
    └── To · CC · BCC · Subject · Body
```

Le colonne Sì/No sono il cuore operativo: il cruscotto segnala come problematico
ogni evento futuro con almeno una di esse a "No". Accanto vivono altre due
tabelle: la stampa unione (24 colonne, inclusi i costi di ospitalità per medico)
e i promemoria speciali.

## Portato nella piattaforma ✅

Tutto in `plugins/indico_ecm` e `plugins/indico_agents`, come funzioni pure con
test di regressione: il comportamento è **congelato**, non reinterpretato.

### Regole operative

| Regola originale | Dove ora |
|---|---|
| `generateFolderName()` + percorso `S:\CONGRESSI` | `services/naming.py` |
| `pluralizzaRuolo()`, termini concordati, nomi file lettere | `services/letters.py` |
| Placeholder del `.docx` | `services/letters.py::letter_context` |
| `identifyMedicalSpecialty()` + `identifyEventType()` | `services/specialty.py` |
| Email di accreditamento + URL Outlook | `services/accreditation_mail.py` |
| Le colonne Sì/No | `services/deliverables.py` + `models/deliverables.py` |

### Schema, workflow e archivio

| Originale | Dove ora |
|---|---|
| `eventColumns` (55 campi) | `services/event_schema.py::EVENT_FIELDS`, con la destinazione di ogni colonna |
| `stampaUnioneColumns` (24 campi) | `services/event_schema.py::INVITATION_FIELDS` |
| `specialReminderColumns` | `services/event_schema.py::REMINDER_FIELDS` |
| I 17 flag Sì/No | `Deliverable` (19 voci: le 17 storiche più inviti e documenti faculty) |
| Campi operativi (codice, cartella, UECM, email fornitori, accreditamento To/CC/BCC) | `models/operations.py::EventOperations` |
| Promemoria speciali | `models/operations.py::SpecialReminder` + `services/reminders.py` |
| Righe di stampa unione e costi | `models/operations.py::InvitationBatch` + `services/costs.py` |
| Import dell'archivio esistente | `services/legacy_import.py` (eventi, stampa unione, promemoria, con elenco dei problemi riga per riga) |

### Template e automator

| Originale | Dove ora |
|---|---|
| Template email sparsi nelle view | `services/templates.py`: registro unico, 8 template versionati con segnaposto dichiarati |
| `templates/lettera_invito.docx` | `indico_ecm/templates/letters/lettera_invito.docx` |
| File della cartella evento (`info_evento.txt`, `briefing.txt`, `agenda.txt`, `report_template.txt`, `email_draft.html`) | `services/templates.py::EVENT_FOLDER_FILES` |
| `AUTOMATOR_PROMPT` + `automatorResponseSchema` | `services/automator.py`, prompt versionato e con hash |
| Estrazione dati dall'email | `services/automator.py::extract`, deterministica (codice, date, relatori, specialità) |

### Agenti che eseguono il workflow

| Agente | Cosa fa |
|---|---|
| `event_setup_agent` | Alla creazione di un evento crea la checklist completa e calcola la cartella |
| `checklist_agent` | Ogni giorno rilegge le scadenze e apre una segnalazione per ogni voce in ritardo, poi si riprogramma |
| `registration_agent`, `contact_resolution_agent` | Dati mancanti per l'attestato, corrispondenza con l'anagrafica |
| `attendance_agent`, `credit_agent` | Anomalie di presenza, proposta di crediti dal motore deterministico |

Strumenti disponibili agli agenti sopra questo strato: `inspect_event_checklist`,
`list_due_reminders`, `invitation_costs`, `prepare_graphic_brief`,
`draft_accreditation_request`, `prepare_invitation_letters`.

### Cosa è cambiato, e perché

**I flag hanno guadagnato una scadenza.** "Grafica: No" non significa niente a
tre mesi e tutto a quattro giorni. `DEFAULT_LEAD_TIMES` assegna a ogni voce i
giorni di anticipo e lo stato diventa `calm → due → late → missed`. Consuntivo e
invio hanno un anticipo negativo: sono attesi *dopo* l'evento, e non risultano
scaduti il giorno dopo.

**I promemoria non si perdono più.** L'originale mostrava un promemoria solo nel
giorno esatto: un giorno di assenza e non lo vedeva nessuno. Ora resta aperto
finché qualcuno non lo chiude, e riporta di quanti giorni è in ritardo.

**L'accreditamento è l'unico che blocca i crediti** (`is_blocking_credits`).

**I campi utente vengono escapati** in tutti i template: un `<script>` in un nome
evento non arriva più intatto nel corpo HTML.

**Nell'automator la piattaforma decide, il modello descrive.** Codice evento,
date e nome cartella sono estratti da regole; se il modello ne propone di
diversi, vince la piattaforma e la divergenza viene registrata come conflitto.
Il prompt vieta esplicitamente di dichiarare crediti.

**I costi di ospitalità si sommano.** Erano stampati sulla lettera e basta: ora
`services/costs.py` produce il totale per medico, per evento, e il confronto con
il budget dello sponsor.

## Da completare

| Funzione | Cosa manca | Priorità |
|---|---|---|
| Lettere `.docx` | Il rendering del template Word con `letter_context` (serve `python-docx`) | ⭐⭐⭐ |
| Import archivio | La UI e la scrittura su database: la trasformazione è pronta e testata | ⭐⭐⭐ |
| Anagrafica evento | Le viste sopra `EventOperations` e `EventDeliverable` | ⭐⭐⭐ |
| Stampa unione | Import CSV/XLSX del foglio ospedali verso `InvitationBatch` | ⭐⭐ |
| Automator | Il runtime LLM che esegue `build_request` e `validate_response` | ⭐⭐ |
| Brochure e sfondi generati | `generateMedicalBrochure`, `createMedicalBackground`: funzione di generazione immagini, da rivalutare | ⭐ |
| Voice control | `js/core/voice.js`: mai citato come necessario, non portato | — |

## Cosa non portare, e perché

- **`authSystem.js`, `rbac.js`, `userAuth.js`, `secureStore.js`** (~1800 righe):
  Indico ha già autenticazione, gruppi, ACL per evento e permessi granulari.
  Reimplementarli significherebbe mantenere due sistemi di sicurezza.
- **`security.js`** (escaping manuale): Jinja e marshmallow lo fanno per
  costruzione.
- **`compression.js`, `state.js`, `voice.js`**: infrastruttura di un'app desktop
  senza database. Qui il database c'è.
- **La UI Next.js**: due frontend significa due backlog. L'interfaccia della
  piattaforma è quella di Indico.
- **I `.bat` di avvio e distribuzione**: il deployment diventa quello di Indico.

## Il guadagno atteso

Ciò che l'app attuale non può fare, e che la migrazione rende possibile:

1. **Iscrizioni e presenze collegate all'evento** — oggi vivono altrove.
2. **Crediti e attestati calcolati sui dati reali** invece che a mano.
3. **Storico per persona**: quante volte quel medico ha partecipato, con quali
   crediti, per quale sponsor.
4. **Un solo archivio**: contatti, ospedali, sponsor e contratti smettono di
   essere fogli.
5. **Automazioni con memoria**: un agente che riapre la pratica al momento
   giusto perché il task ha una data, non perché qualcuno se ne ricorda.

## Ordine consigliato di migrazione

1. Anagrafica evento + checklist (i dati che già esistono) — **sblocca tutto**.
2. Import degli eventi storici dal formato attuale.
3. Lettere e stampa unione: è il lavoro manuale più pesante che si elimina.
4. Email di accreditamento come azione approvabile.
5. Promemoria e brief grafico.
6. Automator, per ultimo: è la parte che richiede il runtime LLM.
