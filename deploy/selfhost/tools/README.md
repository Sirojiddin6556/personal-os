# e2e_audit.py

End-to-end check of a running stack: registers two throwaway users and exercises
every section (tasks, projects, calendar, finance, notes, planner, AI, integrations),
verifies read-after-write persistence and that user B cannot touch user A's data.

Run it against a **separate** stack, not production (it creates users and data):

```bash
cp -r /opt/personal-os/app /opt/personal-os/e2e-app && cd /opt/personal-os/e2e-app/deploy/selfhost
cp .env.example .env   # fill secrets, GATEWAY_PORT=18091, QUICK_TUNNEL_METRICS_URL=
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
