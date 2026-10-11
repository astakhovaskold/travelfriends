# Travel Friends Railway infrastructure

`railway.ts` manages the two existing production services in `travel-friends`.
The Neon database stays external; database URLs and Telegram secrets use `preserve()`.

```sh
npm --prefix .railway ci
.railway/node_modules/.bin/railway link --project travel-friends --environment production
npm --prefix .railway run plan
npm --prefix .railway run apply
```

Review plan before apply. Then deploy the changed application code using GitHub or Railway CLI.
IaC edits are not read from GitHub during application deploys: run plan/apply explicitly.
Use the project-local CLI (5.64.2); the global CLI may be older.
Do not commit decrypted variables or plan artifacts.

Backend uses /backend and backend/Dockerfile, direct Neon migrations in pre-deploy,
and schema-aware `/health`. Frontend uses `/frontend`, its Dockerfile, and Caddy.
The backend pre-deploy command is `alembic -c alembic.ini upgrade head`.
Both listen on `$PORT` (8080). Generated public domains remain owned by Railway.
