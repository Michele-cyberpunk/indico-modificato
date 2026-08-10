# indico_crm

CRM incorporato in Indico: aziende, contatti, professionisti sanitari (HCP),
opportunità, attività, consensi ed evidenze, collegati agli oggetti Indico
tramite `models/links.py`.

Schema PostgreSQL: `plugin_crm`.

## Punti di innesto

Il plugin non modifica il core: si aggancia ai segnali
`registration_created`, `registration_state_updated`,
`registration_checkin_updated` ed `event.created`.

## Logica testabile senza Indico

`services/identity_rules.py` — corrispondenza di identità, deterministica e
più severa per gli HCP (senza codice fiscale o numero di albo nessuna fusione
automatica).

```bash
cd plugins/indico_crm && PYTHONPATH=. python -m pytest indico_crm/services/identity_rules_test.py -q -c /dev/null -p no:indico
```
