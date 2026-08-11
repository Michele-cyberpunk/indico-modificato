# Plugin ECM per Indico

Estensioni proprietarie che trasformano questo fork di Indico nel gestionale di
un provider ECM. Progettazione e razionale in [`docs/ecm-crm/`](../docs/ecm-crm/).

| Plugin | Schema DB | Contenuto |
|---|---|---|
| `indico_crm` | `plugin_crm` | Aziende, contatti, professionisti sanitari, opportunità, attività, consensi, evidenze, ponte verso gli oggetti Indico |
| `indico_ecm` | `plugin_ecm` | Provider, accreditamento, presenza per sessione, regole crediti, assegnazioni, attestati, lista ospiti e transfer |
| `indico_agents` | `plugin_agents` | Coda di lavoro con leasing, run durabili, tool, skill, approvazioni, audit |
| `indico_integrations` | `plugin_integrations` | Outbox transazionale e adapter verso sistemi esterni |

## Principi vincolanti

1. **Il core di Indico non si tocca.** Tutto passa da segnali, blueprint e
   modelli in schemi `plugin_*`. L'unica estensione prevista del core è la
   presenza per sessione nell'API di check-in, da mantenere generica.
2. **L'API non decide.** Un'iscrizione o un check-in creano un `AgentTask`;
   nessuna chiamata sincrona a un modello linguistico nel percorso HTTP.
3. **I crediti sono deterministici.** `indico_ecm.services.credit_rules` è
   codice puro, versionato e testato, senza dipendenze da Indico e senza LLM.
   Gli agenti lo interrogano in sola lettura.

## Installazione (ambiente di sviluppo Indico)

```bash
pip install -e plugins/indico_crm
pip install -e plugins/indico_ecm
pip install -e plugins/indico_agents
pip install -e plugins/indico_integrations
```

Abilitarli in `indico.conf`:

```python
PLUGINS = {'crm', 'ecm', 'agents', 'integrations'}
```

Creare gli schemi e le tabelle (le revisioni si generano dai modelli, che sono
la fonte di verità):

```bash
indico db --plugin crm migrate -m 'initial crm schema'
indico db --plugin crm upgrade
# idem per ecm, agents, integrations
```

Avviare il dispatcher degli agenti: è un task Celery periodico registrato dal
plugin `indico_agents`, quindi è sufficiente che `indico celery worker` e
`indico celery beat` siano in esecuzione.

## Test eseguibili senza Indico

La logica regolatoria pura non dipende da Flask/SQLAlchemy ed è testabile da
sola:

```bash
cd plugins/indico_crm    && PYTHONPATH=. python -m pytest indico_crm    -q -c /dev/null -p no:indico
cd plugins/indico_ecm    && PYTHONPATH=. python -m pytest indico_ecm    -q -c /dev/null -p no:indico
cd plugins/indico_agents && PYTHONPATH=. python -m pytest indico_agents -q -c /dev/null -p no:indico
```

`-p no:indico` evita di caricare il plugin pytest di Indico, che richiede
l'applicazione completa: questi test coprono di proposito solo la logica pura
(corrispondenza di identità, regole crediti, serializzazione delle regole,
schema e import dell'archivio legacy, template, costi, promemoria, automator con
le sue espressioni regolari e la costruzione della cartella evento, lettura della
lista ospiti con transfer e coperti, backoff della coda, tabella dei permessi
degli agenti), 376 test in tutto.

## Test di integrazione

Con un ambiente Indico e un database di prova:

```bash
INDICO_CONFIG=/percorso/indico.conf pytest plugins/integration_test.py -v
```

43 test che coprono ciò che la logica pura non può: presenze calcolate dal
timetable reale, pipeline crediti fino all'attestato, numerazione concorrente,
coda con leasing fra due worker, resa di tutte le pagine, import del foglio
ospedali e generazione delle lettere, la pagina che da un documento costruisce la
cartella evento e quella che da una lista ricava navette e coperti. Senza `INDICO_CONFIG` vengono saltati.

## Cosa serve in più rispetto a Indico

`python-docx` (lettere `.docx` e lettura degli allegati Word) e `openpyxl`
(fogli `.xlsx`). `weasyprint`, `qrcode` e `pypdf`, usati per gli attestati e per
leggere gli allegati PDF, sono già dipendenze di Indico.
