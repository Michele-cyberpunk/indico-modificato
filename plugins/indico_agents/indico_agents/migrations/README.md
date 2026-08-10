# Migrazioni

```bash
indico db --plugin agents migrate -m 'initial agents schema'
indico db --plugin agents upgrade
```

Verificare a mano l'indice parziale su `agent_tasks` (un solo task attivo per
`kind` + soggetto) e l'indice `ix_agent_tasks_claimable`: è quello che regge il
`FOR UPDATE SKIP LOCKED` del dispatcher.
