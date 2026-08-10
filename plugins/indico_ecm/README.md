# indico_ecm

Dominio regolatorio ECM: provider, dossier di accreditamento, presenza per
sessione con entrata/uscita, regole crediti versionate, assegnazioni e
attestati numerati e verificabili.

Schema PostgreSQL: `plugin_ecm`.

## Il vincolo centrale

`services/credit_rules.py` è puro: nessun import di Indico, nessun database,
nessun orologio, nessun modello linguistico. Stessi input, stesso risultato,
sempre — è ciò che rende una decisione difendibile a distanza di anni.

`services/eligibility.py` separa in modo netto le tre operazioni:

| Funzione | Scrive | Chi può chiamarla |
|---|---|---|
| `evaluate_registration` | no | chiunque, agenti compresi |
| `propose_assignment` | proposta | agenti e interfaccia |
| `approve_assignment` | assegna i crediti | solo una persona autorizzata |

## Test

```bash
cd plugins/indico_ecm && PYTHONPATH=. python -m pytest indico_ecm/services -q -c /dev/null -p no:indico
```
