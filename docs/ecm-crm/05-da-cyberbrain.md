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
evento
├── nomeEvento          ├── accreditamento     (Sì/No)
├── dataEvento1/2       ├── contrattiSponsor   (Sì/No)
├── luogo · citta       ├── grafica            (Sì/No)
├── tipoEvento          ├── letteraIncarico    (Sì/No)
├── cliente (sponsor)   ├── slideKit           (Sì/No)
├── codiceEvento        └── note
├── nomeCartella  ← generata: "MMDD[-DD] NOME CITTÀ|FAD SPONSOR CODICE NOTE"
└── uecm          ← referente dell'ufficio accreditamento
```

Le cinque colonne Sì/No sono il cuore operativo: il cruscotto segnala come
problematico ogni evento futuro con almeno una di esse a "No".

## Già portato nella piattaforma ✅

Tutto in `plugins/indico_ecm/indico_ecm/services/`, come funzioni pure con test
di regressione (44 test): il comportamento è **congelato**, non reinterpretato.

| Regola originale | Dove ora | Nota |
|---|---|---|
| `generateFolderName()` | `naming.py` | Stesso ordine, stesso `PLURISPONSOR`, stesso trattamento di FAD/WEB |
| Percorso `S:\CONGRESSI <anno>\...` | `naming.py::folder_path` | Il collegamento con il disco condiviso resta valido |
| `pluralizzaRuolo()` | `letters.py::pluralize_role` | Stessa regola ingenua (parole in `-o`/`-e` → `-i`) |
| Termini concordati (`medici`, `chirurghi`, …) | `letters.py::agreement_terms` | |
| Nome file `Lettera invito - N MEDICI - …` | `letters.py::invitation_filename` | I file sono archiviati e cercati per nome |
| Placeholder del `.docx` | `letters.py::letter_context` | |
| `identifyMedicalSpecialty()` | `specialty.py` | Keyword e palette CMYK/RGB identiche |
| `identifyEventType()` | `specialty.py::identify_event_format` | Stesso ordine di test e stesso fallback |
| Email di accreditamento | `accreditation_mail.py` | Testo **verbatim**, più escaping HTML dei campi |
| URL di composizione Outlook | `accreditation_mail.py::outlook_compose_url` | Il flusso resta: la piattaforma prepara, la persona invia |
| Le 5 colonne Sì/No | `deliverables.py` + `models/deliverables.py` | Con l'aggiunta dei tempi di anticipo |

### Cosa è cambiato, e perché

**I flag hanno guadagnato una scadenza.** "Grafica: No" non significa niente a
tre mesi e tutto a quattro giorni. `DEFAULT_LEAD_TIMES` assegna a ogni voce i
giorni di anticipo (accreditamento 90, contratti 60, inviti 45, grafica 21,
lettere 14, slide kit 7) e lo stato diventa `calm → due → late → missed`. È
questa la differenza che permette a un agente di aprire l'attività **al momento
giusto** invece di elencare ogni giorno tutto ciò che manca.

**L'accreditamento è l'unico che blocca i crediti** (`is_blocking_credits`): gli
altri sono ritardi organizzativi, quello è un evento che non può erogare crediti.

**I campi utente vengono escapati** nell'email: il testo è identico, ma
`<script>` in un nome evento non arriva più intatto nel corpo HTML.

## Da migrare, non ancora fatto

| Funzione | Dove va | Priorità |
|---|---|---|
| Anagrafica evento e cruscotto scadenze | UI di `indico_ecm` sopra `EventDeliverable` | ⭐⭐⭐ |
| Generazione `.docx` delle lettere | `indico_ecm/services/letters.py` + template in `templates/letters/` | ⭐⭐⭐ |
| Stampa unione da foglio ospedali | Import CSV/XLSX → `InvitationRow` → batch di lettere | ⭐⭐⭐ |
| Email di accreditamento come azione approvabile | `indico_agents` `draft_email` + coda approvazioni | ⭐⭐ |
| Brief grafico | Tool `graphic_brief` già pronto: manca la vista e l'invio al designer | ⭐⭐ |
| Promemoria | `reminders` di Indico + `AgentTask` con `run_after` | ⭐⭐ |
| Automator (analisi AI di email/documenti) | Agente `event_setup` con runtime LLM | ⭐ |
| Auth, RBAC, secure store | **Non migrare**: Indico ha già utenti, gruppi, ACL e permessi | — |
| Integrazione Gemini | Sostituire con l'astrazione modello del layer agenti | ⭐ |
| UI Next.js `app/` | **Non migrare**: l'interfaccia è quella di Indico | — |

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
