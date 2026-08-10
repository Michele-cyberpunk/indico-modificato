# Migrazioni

```bash
indico db --plugin ecm migrate -m 'initial ecm schema'
indico db --plugin ecm upgrade
```

Controllare a mano l'indice parziale su `credit_assignments` (una sola
assegnazione non revocata per iscrizione) e i `CheckConstraint` su presenze e
punteggi: Alembic non li rileva sempre.
