# Migrazioni

Le revisioni Alembic si generano dai modelli, che sono la fonte di verità:

```bash
indico db --plugin crm migrate -m 'initial crm schema'
indico db --plugin crm upgrade
```

Prima di applicare una revisione autogenerata va controllata a mano: gli indici
parziali (`postgresql_where`) e i vincoli `CheckConstraint` vanno verificati,
perché Alembic non sempre li rileva correttamente.
