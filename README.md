# Gestionale ECM — Indico con CRM e agenti incorporati

Fork di [Indico](https://github.com/indico/indico) trasformato nel gestionale di
un provider ECM: accreditamento, presenze per sessione, crediti formativi
calcolati da un motore deterministico, attestati verificabili, CRM sanitario e
automazioni con memoria.

Non è un CRM affiancato a Indico. È **Indico che diventa il gestionale**: eventi,
iscrizioni, timetable, permessi e utenti restano quelli di Indico, e sopra ci
sono quattro plugin che aggiungono ciò che serve a un provider e nient'altro.

## Cosa fa, dall'interfaccia

### Per evento (`/event/<id>/manage/ecm/…`)

| Pagina | Cosa permette |
|---|---|
| **Panoramica** | Dossier, checklist di preparazione con scadenze e urgenza, contatori crediti e attestati, promemoria aperti |
| **Accreditamento** | Dossier (provider, codice attività, crediti, posti, modalità, versione regole) e richiesta all'ufficio ECM già compilata, con l'elenco di ciò che manca |
| **Presenze** | Programma accreditato con i minuti che contano, presenze per partecipante, entrata e uscita per sessione dal banco |
| **Crediti** | Per ogni iscritto: minuti, esito del questionario, verdetto delle regole **con i motivi**, assegnazione, attestato. Rivalutazione di massa, approvazione e revoca una per una |
| **Attestati** | Emissione di massa per le sole assegnazioni approvate, PDF con QR, numero e impronta SHA-256 |
| **Ospiti e transfer** | La lista che manda lo sponsor (foglio, CSV, testo, Word, PDF) diventa navette e coperti: righe scartate **con il motivo**, accompagnatori contati, gruppi per finestra oraria e capienza, fogli arrivi e partenze stampabili |
| **Inviti** | Import del foglio ospedali, costi di ospitalità per medico e per evento con confronto sul budget, tutte le lettere `.docx` in un archivio |

### Amministrazione (`/admin/…`)

| Pagina | Cosa permette |
|---|---|
| **Provider** | Anagrafica e prefisso di numerazione degli attestati |
| **Da documento a cartella** | Si incolla l'email dello sponsor o si caricano gli allegati: la piattaforma estrae codice, date, relatori, specialità e modalità, dice **da quale frase** ha preso ogni valore, elenca ciò che non ha ricavato e scarica la cartella evento in `.zip` già nominata secondo la convenzione del provider |
| **Import archivio** | Analisi dell'esportazione del gestionale precedente, con le segnalazioni riga per riga |
| **CRM** | Contatti con le loro evidenze, aziende, opportunità aperte |
| **Agenti** | Stato della coda, esecuzioni recenti, task falliti, coda di approvazione, interruttore generale |

### Pubblico

`/ecm/verify/<token>` — chiunque abbia l'attestato può verificarlo: numero,
crediti, evento accreditato, data, versione delle regole. Nessun dato personale.
Anche in JSON.

## I tre principi che non si negoziano

1. **Il core di Indico non si tocca.** Tutto passa da segnali, blueprint e
   modelli in schemi `plugin_*`. Aggiornare Indico resta possibile.
2. **L'API non decide.** Un'iscrizione o un check-in creano un task in coda;
   nessuna chiamata sincrona a un modello linguistico nel percorso HTTP.
3. **I crediti sono deterministici.** `indico_ecm.services.credit_rules` è codice
   puro, versionato e testato, senza dipendenze da Indico e senza LLM. Gli agenti
   lo interrogano in sola lettura e **non possono** scrivere un dato regolatorio:
   propongono, una persona approva.

Lo stesso vale per l'estrazione dai documenti: dove il gestionale di partenza
chiamava un modello, qui ci sono regole provate. Il modello resta un'aggiunta
facoltativa per la prosa, mai per un numero che finisce su un attestato.

## I plugin

| Plugin | Schema DB | Contenuto |
|---|---|---|
| `indico_crm` | `plugin_crm` | Aziende, contatti, professionisti sanitari, opportunità, attività, consensi, evidenze |
| `indico_ecm` | `plugin_ecm` | Provider, accreditamento, presenze, regole crediti, assegnazioni, attestati, ospiti e transfer |
| `indico_agents` | `plugin_agents` | Coda con leasing, run durabili, 26 strumenti, skill, approvazioni, audit |
| `indico_integrations` | `plugin_integrations` | Outbox transazionale verso sistemi esterni |

Dettagli in [`plugins/README.md`](plugins/README.md).

## Installazione

Prerequisiti di Indico (Python 3.12.2+, PostgreSQL con `unaccent` e `pg_trgm`,
Redis, Node) più `python-docx` e `openpyxl`.

```bash
pip install -e plugins/indico_crm plugins/indico_ecm plugins/indico_agents plugins/indico_integrations
```

In `indico.conf`:

```python
PLUGINS = {'crm', 'ecm', 'agents', 'integrations'}
```

Schemi e tabelle:

```bash
indico db prepare
for p in crm ecm agents integrations; do indico db --plugin $p upgrade; done
```

Servono **sia** `indico celery worker` **sia** `indico celery beat`: senza beat
il dispatcher degli agenti non parte mai. Gli agenti restano comunque spenti
finché non si attiva l'interruttore nel cruscotto.

## Test

```bash
# logica pura, ovunque, senza database — 376 test
cd plugins/indico_ecm && PYTHONPATH=. python -m pytest indico_ecm -q -c /dev/null -p no:indico

# integrazione, con Indico e PostgreSQL veri — 43 test
INDICO_CONFIG=/percorso/indico.conf pytest plugins/integration_test.py -v
```

Le due suite dividono il lavoro: la prima copre ciò che è calcolo (regole
crediti, corrispondenza di identità, lettura dei documenti e delle liste,
costi, promemoria), la seconda ciò che solo SQL può smentire (numerazione
concorrente, coda con leasing fra due worker, presenze dal timetable reale,
resa di tutte le pagine).

## Documentazione

[`docs/ecm-crm/`](docs/ecm-crm/) contiene il progetto e le sue ragioni:

| | |
|---|---|
| [01 — Catalogo repository](docs/ecm-crm/01-catalogo-repository.md) | I CRM esaminati, cosa prendere da ognuno e cosa impedisce la licenza |
| [02 — Mosaico dei file](docs/ecm-crm/02-mosaico-file.md) | Da quale file di quale progetto viene ogni pezzo |
| [03 — Agenti AI](docs/ecm-crm/03-agenti-ai.md) | Livelli di autonomia, tabella dei permessi, cosa un agente non può fare |
| [04 — Il CRM dentro Indico](docs/ecm-crm/04-crm-in-indico.md) | Come si innesta senza toccare il core |
| [05 — Da Cyberbrain](docs/ecm-crm/05-da-cyberbrain.md) | Cosa migrare dal gestionale in uso, cosa no, e perché |
| [06 — Stato per la produzione](docs/ecm-crm/06-stato-produzione.md) | Cosa è verificato eseguendo, i bug trovati, cosa resta fuori per scelta |

## Da dove viene

**Indico** (MIT, [CERN](https://home.cern)) è la base: eventi, iscrizioni,
timetable, permessi, autenticazione, sondaggi. Il progetto originale è su
[indico/indico](https://github.com/indico/indico) e la sua documentazione su
[docs.getindico.io](https://docs.getindico.io). Questo fork non lo modifica: lo
estende.

**trycompai/crm** (MIT) ha fornito l'architettura del CRM e dello strato
agentico — coda di lavoro durabile, strumenti tipizzati, approvazioni umane —
**riscritta** in Python sopra i modelli di Indico. Il sorgente è TypeScript su
Prisma: nessuna riga è condivisa fra i due progetti e nessun file qui è
un'opera derivata. Ciò che è stato ripreso sono le decisioni di disegno.

**Il gestionale interno del provider** ha fornito il capitolato vero: la
convenzione dei nomi cartella, le 17 voci di checklist, le lettere di invito, i
costi di ospitalità, le palette per specialità, l'estrazione dai documenti. Le
sue regole sono state congelate in funzioni pure con test di regressione, non
reinterpretate. Dove erano sbagliate — e in diversi punti lo erano — il difetto è
documentato, corretto e coperto da un test che lo riproduce.

## Licenza

MIT, come Indico. Vedi [LICENSE](LICENSE).

> *In applying the MIT license, CERN does not waive the privileges and immunities
> granted to it by virtue of its status as an Intergovernmental Organization or
> submit itself to any jurisdiction.*
