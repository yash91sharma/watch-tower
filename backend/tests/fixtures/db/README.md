# DB dumps

One SQL dump per release: `<version>.sql` (for example `0.0.0.sql`). Make it from a DB with data of all tables:

```
sqlite3 wt.db .dump > tests/fixtures/db/<version>.sql
```

Or load the newest dump, upgrade it (`open_db`), add fake rows to the new tables, and dump it again (`0.5.0.sql` was made this way).

`tests/unit/db/test_dumps.py` loads each dump and upgrades it to the newest revision. Use only fake data. No secrets.
