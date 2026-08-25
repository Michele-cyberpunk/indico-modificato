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
| File della cartella evento (`info_evento.txt`, `briefing.txt`, `agenda.txt`, `report_template.txt`, `email_draft.html`) | `services/automator.py::FOLDER_TEMPLATES`; l'elenco dei nomi resta in `services/templates.py::EVENT_FOLDER_FILES` e un test impedisce ai due di divergere |
| `AUTOMATOR_PROMPT` + `automatorResponseSchema` | `services/automator.py`, prompt versionato e con hash |
| Estrazione dati dall'email | `services/automator.py::extract`, deterministica (codice, date, relatori, specialità) |
| Caricamento del documento (`automator.js`: incolla o allega, poi scarica lo zip) | Pagina `/admin/ecm/automator`; `read_document` legge txt, Word, PDF, HTML/eml; `build_folder_archive` restituisce lo zip con la cartella già nominata |
| `extractWithRegex` + raggruppamento transfer (`app/src/app/page.tsx`) | `services/guests.py` e pagina `/event/<id>/manage/ecm/guests`: lettura riga per riga, righe scartate motivate, coperti, navette per finestra e capienza, fogli stampabili |

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

**E oggi il modello non serve per costruire la cartella.** L'originale mandava
tutto a Gemini e riceveva indietro anche i nomi dei file: senza chiave l'intera
funzione era ferma. Qui l'estrazione è deterministica e i cinque documenti
iniziali sono modelli compilati con i dati estratti, quindi la pagina funziona
sempre. Il runtime LLM resta un'aggiunta facoltativa per la prosa, non un
prerequisito.

**La lista ospiti non passa più da un modello.** L'originale provava tre modelli
Gemini in cascata e cadeva su `extractWithRegex` solo quando mancava la chiave o
tutte le quote erano esaurite. Qui il percorso a regole è l'unico: una lista di
partecipanti è testo corto e formulare, e una regex provata è più prevedibile —
e verificabile — di un modello che risponde diversamente il martedì. La pagina
conserva per ogni riga il testo di partenza e il frammento che ogni regola ha
letto, così un transfer sbagliato si risale fino alla causa. E le righe scartate
si vedono con il motivo: una riga persa in silenzio è una persona che atterra
senza nessuno ad aspettarla.

**Anche quella regex era sbagliata, in otto modi.** Provata su righe realistiche
prima di essere riscritta: `ROSSI MARIO` (il formato più comune nelle liste
italiane) non produceva alcun nome; `Niccolò Verdi` nemmeno, per l'accento;
`Prof. Gian Luca De Angelis` diventava `Gian Luca`; `no pranzo` contava come un
pranzo; `vegetariano` da solo veniva buttato via perché la parola chiave *era* il
valore; `+ 1 accompagnatore` non contava, perché `pax` era fisso a 1 e la navetta
partiva con un posto in meno; `Hotel Excelsior Milano` diventava un ospite di
nome Hotel; e `Bosch: 10:30` veniva letto come un arrivo perché la `h` di
"h 10:30" non era ancorata. Ognuno è un test.

**Nome e cognome, quando la riga non lo dice, non si indovinano.** `Mario Rossi`
e `Rossi Mario` sono gli stessi caratteri nello stesso ordine. La piattaforma
cerca un segnale vero — la virgola di `Rossi, Mario`, il cognome in maiuscolo di
`ROSSI Mario`, un nome proprio riconoscibile — e quando non ce n'è lo dichiara,
mostrando in pagina un pulsante per invertire i due.

**Le espressioni regolari sono state strette, non copiate.** Il pattern originale
del codice evento accettava anche `[A-Z]{1,3}\d{2,5}`, che pesca `IT12345` da una
partita IVA, `A101` da una sala e `FT2026` da una fattura: un codice sbagliato
archivia la richiesta di accreditamento sotto l'evento sbagliato. Ora vale la sola
convenzione del provider, più tutto ciò che il testo annuncia esplicitamente come
codice ("codice evento:", "rif."). Il pattern dei relatori si fermava a due parole
in maiuscolo e trasformava `Prof. Gian Luca De Angelis` in `Gian Luca De`: ora le
particelle dei cognomi (`de`, `della`, `van`, `von`, `d'`…) fanno parte del nome e
le parole di ruolo che seguono (`Presidente`, `Moderatore`…) vengono tolte. Ogni
caso è un test.

**I costi di ospitalità si sommano.** Erano stampati sulla lettera e basta: ora
`services/costs.py` produce il totale per medico, per evento, e il confronto con
il budget dello sponsor.

## Stato del porting

| Funzione | Stato |
|---|---|
| Lettere `.docx` | **Fatto** — `services/letters.py` rende il template Word e la pagina Inviti genera l'archivio |
| Lettere di incarico (`src/lib/word/incarico.ts`) | **Fatto** — `services/engagement_letter.py` + `services/faculty.py`, pagina Faculty: saluti matriciali, importi in lettere, ritenuta 20%, sesso dal codice fiscale; il `.docx` storico del provider è in `templates/letters/lettera_incarico.docx` |
| Email come bozza (`src/lib/email/sender.ts`) | **Fatto** — `services/mail_draft.py`: messaggio `.eml` scaricabile dalla pagina Messaggi, allegati già dentro, niente parte finché una persona non preme invio |
| Template email sparsi nelle view | **Fatto** — registro unico in `services/templates.py`, pagina Messaggi che li mostra riempiti coi dati dell'evento |
| Servizi albergo (`src/lib/import/hotelServices.ts`) | **Fatto** — `services/hotel.py` deduce i servizi dal programma (timetable + descrizione); la pagina Messaggi riempie il template `hotel_quote` e l'agente ha il tool `prepare_hotel_brief`, in sola lettura come il brief grafico |
| Import archivio | **Fatto** — `/admin/ecm/import`, con le segnalazioni riga per riga |
| Anagrafica evento e checklist | **Fatto** — panoramica, accreditamento, scadenze con urgenza |
| Stampa unione | **Fatto** — import CSV/XLSX del foglio ospedali verso `InvitationBatch` |
| Lista ospiti, transfer e coperti | **Fatto** — `/event/<id>/manage/ecm/guests`, regole soltanto: il percorso AI dell'originale non è stato portato perché quello a regole lo copre per intero |
| Automator | **Fatto nella parte deterministica** — `/admin/ecm/automator` legge il materiale, estrae, mostra da quale frase, costruisce e scarica la cartella. Resta facoltativo il runtime LLM che esegue `build_request`/`validate_response` per la prosa |
| Brochure e sfondi generati | Non portato: serve una funzione di generazione immagini, da rivalutare |
| Voice control | Non portato: `js/core/voice.js` non è mai stato citato come necessario |

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

## Ordine di adozione in ufficio

Il porting è concluso; questo è l'ordine con cui conviene metterlo in uso, dal
dato che sblocca tutto il resto all'ultimo passaggio facoltativo.

1. Anagrafica evento + checklist (i dati che già esistono) — **sblocca tutto**.
2. Import degli eventi storici dal formato attuale.
3. Lettere e stampa unione: è il lavoro manuale più pesante che si elimina.
4. Email di accreditamento come azione approvabile.
5. Promemoria e brief grafico.
6. Automator: si usa da subito nella parte deterministica; il runtime LLM, se
   servirà, si collega dopo senza toccare la pagina.
