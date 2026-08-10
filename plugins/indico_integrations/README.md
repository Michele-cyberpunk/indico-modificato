# indico_integrations

Outbox transazionale e adapter verso sistemi esterni.

Schema PostgreSQL: `plugin_integrations`.

`models/outbox.py` + `sync/outbox.py` implementano il transactional outbox: la
riga viene scritta nella stessa transazione della modifica che descrive, quindi
un sistema esterno non viene mai informato di qualcosa che il database ha poi
annullato. Stessa idea del plugin `livesync` di Indico, applicata a CRM ed ECM.

Gli adapter concreti (Gmail, Calendar, webinar, firma, contabilità) si
registrano con `@handler('<target>')`.
