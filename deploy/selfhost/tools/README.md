# e2e_audit.py

End-to-end check of a running stack: registers two throwaway users and exercises
every section (tasks, projects, calendar, finance, notes, planner, AI, integrations),
verifies read-after-write persistence and that user B cannot touch user A's data.

Run it against a **separate** stack, not production (it creates users and data):

```bash
cp -r /opt/personal-os/app /opt/personal-os/e2e-app && cd /opt/personal-os/e2e-app/deploy/selfhost
cp .env.example .env   # fill secrets, GATEWAY_PORT=18091, QUICK_TUNNEL_METRICS_URL=
sed -i 's/name: personal-os-internal/name: pos-e2e-internal/' docker-compose.yml
docker compose -p pos-e2e up -d --build
docker compose -p pos-e2e exec -T api python - http://127.0.0.1:8000/v1 http://gateway < tools/e2e_audit.py
docker compose -p pos-e2e down -v && rm -rf /opt/personal-os/e2e-app
```
