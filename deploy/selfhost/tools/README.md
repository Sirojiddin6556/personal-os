# backup.sh

Daily database dump (`pg_dump -Fc`, verified with `pg_restore --list`) plus a tarball of
uploaded files, kept for 14 days in `/opt/personal-os/db-backups` (manual `pre-*.dump`
copies are never rotated). Install once:

```bash
( crontab -l 2>/dev/null; echo '30 3 * * * /opt/personal-os/app/deploy/selfhost/tools/backup.sh >> /opt/personal-os/db-backups/backup.log 2>&1' ) | crontab -
```

Restore commands are in the script header. The copies live on the same disk as the
database, so also pull them to another machine from time to time.

# e2e_audit.py

End-to-end check of a running stack: registers two throwaway users and exercises
every section (tasks, projects, calendar, finance, notes, planner, AI, integrations),
verifies read-after-write persistence and that user B cannot touch user A's data.

Run it against a **separate** stack, not production (it creates users and data):

```bash
cp -r /opt/personal-os/app /opt/personal-os/e2e-app && cd /opt/personal-os/e2e-app/deploy/selfhost
cp .env.example .env   # fill secrets, GATEWAY_PORT=18091, QUICK_TUNNEL_METRICS_URL=, ALLOW_REGISTRATION=true
docker compose -p pos-e2e up -d --build
docker compose -p pos-e2e exec -T api python - http://127.0.0.1:8000/v1 http://gateway < tools/e2e_audit.py
docker compose -p pos-e2e down -v && rm -rf /opt/personal-os/e2e-app
```

The compose network is project-scoped, so `-p pos-e2e` gets its own network and
its `db`/`redis` never resolve inside production (and vice versa). Check with
`docker network inspect pos-e2e_internal` before running anything.

# bank_e2e.py

Telegram bank-notice flow (forwarded HUMO/Uzcard notices, card routing, category
learning, auto-save, undo, isolation) against the same throwaway stack; Telegram
calls are mocked:

```bash
docker compose -p pos-e2e exec -T -w /app api python - http://127.0.0.1:8000/v1 < tools/bank_e2e.py
```
