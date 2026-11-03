# DB dumps

One SQL dump per release: `<version>.sql` (for example `0.0.0.sql`). Make it from a DB with data of all tables:

```
sqlite3 wt.db .dump > tests/fixtures/db/<version>.sql
```

`tests/unit/db/test_dumps.py` loads each dump and upgrades it to the newest revision. Use only fake data. No secrets.
