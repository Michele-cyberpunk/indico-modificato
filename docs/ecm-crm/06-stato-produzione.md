# Stato per la produzione — cosa è verificato e cosa no

Aggiornato dopo il collaudo su ambiente reale: Indico completo, PostgreSQL 16,
migrazioni eseguite da zero, applicazione avviata con i quattro plugin attivi.

## Risposta breve

**Il nucleo funziona davvero.** Non ci sono mock: nessun servizio finto,
nessuna funzione che restituisce dati inventati. La pipeline che porta da un
evento a un attestato numerato è stata eseguita su un database vero e produce i
risultati attesi, compresi i rifiuti quando i requisiti non sono soddisfatti.

**Non è ancora un prodotto installabile per l'utente finale**, perché manca
l'interfaccia per gran parte delle operazioni: molte funzioni oggi si
raggiungono da codice o da API, non da una pagina.

## Cosa è stato eseguito, non solo scritto ✅

| Verifica | Esito |
|---|---|
| `import_all_models()` + `configure_mappers()` con Indico reale | 19 moduli modello, mapper configurati senza errori |
| Foreign key verso il core | tutte risolte (controllo statico su 153 tabelle + risoluzione SQLAlchemy) |
| Collisioni di backref su `Event`, `User`, `Registration` | nessuna (33 backref di plugin) |
| `indico db prepare` su PostgreSQL 16 vuoto | riuscito |
| `indico db --plugin <nome> upgrade` per i 4 plugin | **28 tabelle create** |
| Avvio di `make_app()` con i plugin | 4 plugin attivi, 11 rotte registrate |
| Compilazione dei template Jinja dei plugin | 6 template, tutti compilati |
| Pipeline ECM end-to-end su database reale | vedi sotto |
| Coda agenti con leasing su database reale | vedi sotto |
| Test puri (logica senza database) | 292 test |
| ruff con la configurazione del repository | pulito |

### Pipeline ECM eseguita

Evento → sessione a programma (6 ore) → iscrizione → presenza per sessione →
questionario → valutazione apprendimento → crediti → attestato:

```text
valutazione: eligible=True crediti=9 presenza=360/360 min motivi=[]
proposta: stato=proposed crediti=9
attestato bloccato prima dell'approvazione ✔
approvazione: stato=approved da=Mario Rossi
attestato: ECM-2026-000001 stato=issued hash=1d393b00…
verifica pubblica: {'number': 'ECM-2026-000001', 'valid': True, 'credits': '9', …}
partecipante uscito a metà: eligible=False crediti=0
  motivi=['profile_unverified', 'attendance_below_threshold',
          'assessment_missing', 'survey_missing']
```

I minuti di presenza sono calcolati dal timetable reale, non da un valore
inserito a mano. La verifica pubblica non espone dati personali.

### Coda agenti eseguita

```text
task duplicato evitato ✔ (un solo task in coda)
affittati da worker-A: ['attendance_reconcile', 'registration_check']
worker-B non ruba i task affittati: 0 (FOR UPDATE SKIP LOCKED)
fallimento → stato=pending, riprova pianificata con backoff
completamento → lease rilasciato
worker morto → lease scaduto recuperato, task di nuovo disponibile
```

## Tre bug reali trovati dall'ambiente vero

Nessuno di questi era visibile nei test puri. È la ragione per cui il collaudo
è stato fatto.

1. **`FOR UPDATE` con `max()`** — PostgreSQL rifiuta il blocco di riga su una
   funzione di aggregazione, quindi la numerazione degli attestati non
   funzionava. Sostituita con un contatore per provider e anno, incrementato con
   un `INSERT … ON CONFLICT DO UPDATE … RETURNING`: due lotti concorrenti
   ottengono due numeri diversi e la serie non ha buchi.
2. **Vincolo sul lease troppo rigido** — leggere un attributo scaduto a metà
   aggiornamento provocava un autoflush di una riga incoerente, e il vincolo
   `(status = leased) = (lease IS NOT NULL)` faceva fallire l'operazione. Ora il
   vincolo descrive l'invariante (`owner` e scadenza sempre insieme; nessun
   lease se il task non è attivo) e il codice legge prima di scrivere.
3. **`filter()` dopo `limit()`** — SQLAlchemy rifiuta di restringere una query
   che ha già un `LIMIT`: `claim_due(kinds=[...])` sollevava un errore. Filtro
   spostato prima del limite.

Più due incoerenze di modello: la foreign key verso `receipt_files` puntava a una
colonna `id` che non esiste (la chiave è `file_id`), e `event.session_blocks` non
esiste in Indico — i blocchi si raggiungono dalle sessioni.

## Mock, stub e promesse non mantenute

Controllati uno per uno:

| Rischio | Stato |
|---|---|
| Servizi finti che restituiscono dati inventati | **nessuno** |
| Approvazioni che non fanno nulla | **risolto**: quattro esecutori reali (`link_contact`, `create_contact`, `send_email`, `issue_certificates`). Approvare un'azione senza esecutore ora **fallisce** invece di far credere che sia stata eseguita |
| Strumenti nella tabella dei permessi ma non implementati | **presenti**: `search_crm`, `record_fact`, `research_company`, `enrich_company`, `write_brief`, `draft_email`, `create_task`, `schedule_recheck`. Sono autorizzati ma non esistono: `tools.call` solleva `LookupError` in modo esplicito, non silenzioso |
| Runtime LLM | **assente per scelta**. Gli agenti attuali sono deterministici. `automator.build_request`/`validate_response` sono pronti, manca il chiamante |
| Sandbox degli agenti | **assente**. Serve prima di attivare qualsiasi strumento di ricerca esterna |
| Generazione `.docx` delle lettere | **assente**: il contesto dei segnaposto è pronto e testato, manca lo scrittore (`python-docx`) |
| Generazione PDF degli attestati | **assente**: il modulo `receipts` di Indico esiste e il template va collegato |

## Cosa manca per l'uso quotidiano

In ordine di ciò che blocca di più un utente reale:

| # | Cosa | Perché serve |
|---|---|---|
| 1 | Pagine di gestione evento ECM: dossier, checklist, presenze, assegnazioni | Oggi esiste solo la panoramica; il resto richiede API o shell |
| 2 | Interfaccia di approvazione | La coda esiste, la pagina no |
| 3 | Import dell'archivio Cyberbrain | La trasformazione è pronta e testata; mancano pagina e scrittura |
| 4 | Lettere `.docx` e stampa unione | È il lavoro manuale più pesante che la piattaforma può togliere |
| 5 | Generazione PDF attestato con QR di verifica | La verifica pubblica risponde già; manca il documento |
| 6 | App di check-in per sessione | Il modello e i servizi ci sono; manca l'estensione dell'API di check-in |
| 7 | Test di integrazione automatici | I collaudi di oggi sono stati manuali: vanno trasformati in una suite che gira in CI con un PostgreSQL |
| 8 | Runtime LLM + sandbox | Solo dopo che i punti 1–7 sono in mano agli utenti |

## Prerequisiti d'esercizio

- **Python 3.12.2+** (Indico lo richiede; il collaudo è stato fatto su 3.11 con
  i modelli e le migrazioni, ma l'installazione ufficiale richiede 3.12).
- PostgreSQL con le estensioni `unaccent` e `pg_trgm`.
- Redis per code e cache; `indico celery worker` **e** `indico celery beat` in
  esecuzione, altrimenti il dispatcher degli agenti non parte mai.
- Gli agenti restano spenti finché non si attiva l'interruttore nelle
  impostazioni del plugin: l'impostazione predefinita è `enabled = False`.

## Come rifare il collaudo

```bash
# database vuoto
createdb indico_ecm && psql indico_ecm -c 'CREATE EXTENSION unaccent; CREATE EXTENSION pg_trgm;'
indico db prepare
for p in crm ecm agents integrations; do indico db --plugin $p upgrade; done

# logica pura, senza database
cd plugins/indico_ecm && PYTHONPATH=. python -m pytest indico_ecm -q -c /dev/null -p no:indico
```

Le migrazioni sono generate dai modelli e devono restare allineate: dopo ogni
modifica ai modelli va prodotta una nuova revisione, non modificata quella
iniziale.
