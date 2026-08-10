# Stato per la produzione

Aggiornato dopo il completamento dell'interfaccia e dei documenti, con collaudo
su Indico reale e PostgreSQL 16: database creato da zero, migrazioni eseguite,
applicazione avviata, pagine e azioni provate una per una.

## Risposta breve

**Il programma è completo e funziona.** Un provider può, dalla sola interfaccia
web: creare il dossier di accreditamento, seguire la checklist di preparazione,
registrare le presenze per sessione, far valutare i crediti dal motore
deterministico, approvarli, emettere gli attestati in PDF con QR di verifica,
importare il foglio ospedali e generare le lettere di invito in Word.

**Nessun mock.** Ogni strumento autorizzato esiste, ogni azione approvabile ha
un esecutore reale, e le funzioni che dipendono da un fornitore esterno non
configurato lo dichiarano invece di inventare dati.

## Cosa fa, oggi, dall'interfaccia

| Pagina | Cosa permette |
|---|---|
| **Panoramica ECM** (`/event/<id>/manage/ecm/`) | Dossier, checklist con scadenze e urgenza, contatori crediti e attestati, promemoria aperti; ogni voce di checklist si chiude e si riapre |
| **Accreditamento** | Crea e modifica il dossier (provider, codice attività, crediti, posti, modalità, stato, versione regole, cartella) e mostra la richiesta all'ufficio ECM già compilata, con l'elenco di ciò che manca |
| **Presenze** | Programma accreditato con i minuti che contano, presenze per partecipante, presenze aperte, entrata/uscita per sessione dal banco |
| **Crediti** | Per ogni iscritto: minuti di presenza, esito del questionario, verdetto delle regole con i motivi, assegnazione, attestato. Rivalutazione di massa. Approvazione e revoca una per una |
| **Attestati** | Emissione di massa per le sole assegnazioni approvate, elenco con numero, impronta e stato, download del PDF, link alla verifica |
| **Inviti** | Import del foglio ospedali (CSV o XLSX, intestazioni italiane), costi di ospitalità per medico e per evento con confronto sul budget, generazione di tutte le lettere `.docx` in un archivio |
| **Verifica pubblica** (`/ecm/verify/<token>`) | Pagina aperta a chiunque: numero, crediti, evento accreditato, data, versione regole. Nessun dato personale. Anche in JSON |
| **Provider** (`/admin/ecm/providers`) | Anagrafica provider e prefisso di numerazione |
| **Import archivio** (`/admin/ecm/import`) | Analisi dell'esportazione del gestionale precedente con le segnalazioni riga per riga |
| **CRM** (`/admin/crm/…`) | Contatti con le loro evidenze, aziende, opportunità aperte |
| **Agenti** (`/admin/agents/`) | Stato della coda, esecuzioni recenti, task falliti, coda di approvazione con Approva/Rifiuta, interruttore generale |

## Verificato eseguendo, non leggendo

| Verifica | Esito |
|---|---|
| `indico db prepare` su database vuoto + `indico db --plugin … upgrade` ×4 | **28 tabelle** create |
| Avvio di `make_app()` con i quattro plugin | 4 plugin attivi, **16 rotte ECM** più CRM e agenti |
| Rendering di tutte le pagine con utente autenticato | **15 pagine, tutte 200** |
| Generazione PDF attestato | 12,9 KB, `%PDF`, impronta SHA-256 |
| Import foglio ospedali + generazione lettere | 2 righe importate, archivio `.zip` da ~60 KB con i `.docx` |
| Check-in dal banco | presenza registrata, risposta JSON |
| Pipeline crediti completa | 360/360 minuti dal timetable reale, 9 crediti, attestato numerato, verifica pubblica valida |
| Coda agenti | dedup, `FOR UPDATE SKIP LOCKED` fra due worker, backoff, recupero del lease di un worker morto |
| **Suite di integrazione** (`plugins/integration_test.py`) | **31 test** su Indico e PostgreSQL reali |
| Suite pure (senza database) | **292 test** |
| ruff con la configurazione del repository | pulito |

## Copertura degli strumenti degli agenti

| Controllo | Esito |
|---|---|
| Strumenti implementati | 26 |
| Autorizzati ma non implementati | **nessuno** |
| Implementati ma non autorizzati | **nessuno** |
| Azioni di approvazione senza esecutore | **nessuna** |

Due test di integrazione verificano proprio questo, così la parità non può
rompersi in silenzio.

Le funzioni che dipendono da un fornitore esterno (`research_company`,
`enrich_company`) rispondono `{'configured': False}` finché un fornitore non è
configurato nelle impostazioni del plugin: nessun dato inventato.

## I bug che solo l'esecuzione ha trovato

1. **Numerazione attestati**: `max()` con `FOR UPDATE`, rifiutato da PostgreSQL
   sugli aggregati. Sostituito da un contatore per provider e anno, incrementato
   con `INSERT … ON CONFLICT DO UPDATE … RETURNING`.
2. **Vincolo sul lease**: un autoflush a metà aggiornamento lo violava. Ora il
   vincolo descrive l'invariante e il codice legge prima di scrivere.
3. **`filter()` dopo `limit()`** in `claim_due(kinds=…)`.
4. **Foreign key** verso `receipt_files.id`, che non esiste (`file_id`).
5. **`event.session_blocks`**: non esiste in Indico, i blocchi stanno sotto le
   sessioni.
6. **Template admin** che estendevano un layout inesistente.

## Cosa resta fuori, per scelta

| Cosa | Perché |
|---|---|
| Runtime LLM | Gli agenti oggi sono deterministici e fanno un lavoro utile. `automator.build_request`/`validate_response` sono pronti per quando si vorrà collegare un modello; il prompt è versionato e vieta di dichiarare crediti |
| Sandbox degli agenti | Serve solo quando si attiveranno strumenti di ricerca esterna, oggi disattivati |
| App mobile di check-in | Il check-in funziona da pagina; un'app userebbe la stessa rotta |
| Firma digitale degli attestati | Il PDF è verificabile per numero, impronta e QR; la firma PAdES richiede un servizio esterno |
| Sincronizzazione Gmail/Calendar | L'outbox transazionale è pronto; gli adapter concreti no |

## Prerequisiti d'esercizio

- **Python 3.12.2+**, PostgreSQL con `unaccent` e `pg_trgm`, Redis.
- `indico celery worker` **e** `indico celery beat`: senza beat il dispatcher
  degli agenti non parte mai.
- `python-docx` e `openpyxl` per lettere e fogli; `weasyprint` e `qrcode` sono
  già dipendenze di Indico.
- Gli agenti restano spenti finché non si attiva l'interruttore nel cruscotto:
  il valore predefinito è `enabled = False`.

## Come rifare il collaudo

```bash
createdb indico_ecm && psql indico_ecm -c 'CREATE EXTENSION unaccent; CREATE EXTENSION pg_trgm;'
indico db prepare
for p in crm ecm agents integrations; do indico db --plugin $p upgrade; done

# logica pura, ovunque
cd plugins/indico_ecm && PYTHONPATH=. python -m pytest indico_ecm -q -c /dev/null -p no:indico

# integrazione, con Indico e PostgreSQL veri
INDICO_CONFIG=/path/to/indico.conf pytest plugins/integration_test.py -v
```

Le migrazioni sono generate dai modelli: dopo ogni modifica va prodotta una
nuova revisione, non modificata quella iniziale.
