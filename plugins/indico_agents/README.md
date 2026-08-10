# indico_agents

Porting del layer agentico di [trycompai/crm](https://github.com/trycompai/crm)
(MIT) dentro Indico: coda con leasing, esecuzioni durabili, strumenti
autorizzati, skill versionate, approvazioni umane e audit.

Schema PostgreSQL: `plugin_agents`.

## Corrispondenze con il sorgente

| trycompai/crm | qui |
|---|---|
| `lib/tasks.ts` (`claimDue`) | `runtime/tasks.py` — `with_for_update(skip_locked=True)` |
| `schedules/dispatch.ts` | `runtime/dispatch.py` — task Celery ogni minuto |
| `lib/run-state.ts`, `lib/run-runtime.ts` | `runtime/runner.py` |
| `lib/approval.ts` | `governance/approvals.py` |
| `hooks/audit.ts` | `governance/audit.py` — scrive nel log evento di Indico |
| `skills/*.md` | `skills/*.md` (4 portate + 2 ECM) |
| `tools/*.ts` | `tools/` con `tools/base.py` come registro |
| `sandbox/` | previsto, non ancora implementato |

## Invariante

`governance/policy_rules.py` è la tabella dei permessi, in un solo file leggibile
senza avviare l'applicazione. Assegnare crediti, emettere attestati e
rettificare presenze non sono permessi di alto livello: sono assenti dalla
tabella ed elencati come vietati, a qualsiasi livello di autonomia.

## Test

```bash
cd plugins/indico_agents && PYTHONPATH=. python -m pytest indico_agents -q -c /dev/null -p no:indico
```
