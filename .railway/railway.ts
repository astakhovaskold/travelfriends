import {defineRailway, github, preserve, project, service} from "railway/iac";

export default defineRailway(() => {
    const frontendOrigin = "https://travelfriends-web-production.up.railway.app";
    const apiOrigin = "https://travelfriends-api-production.up.railway.app";

    const web = service("travelfriends-web", {
        source: github("astakhovaskold/travelfriends", {
            branch: "main",
            checkSuites: false,
            rootDirectory: "/frontend",
        }),
        build: {
            buildEnvironment: "V3",
            builder: "DOCKERFILE",
            dockerfilePath: "Dockerfile",
            watchPatterns: ["/frontend/**"],
        },
        start: "caddy run --config /etc/caddy/Caddyfile --adapter caddyfile",
        healthcheck: "/health",
        healthcheckTimeout: 120,
        replicas: {"europe-west4-drams3a": 1},
        deploy: {preDeployCommand: []},
        networking: {privateNetworkEndpoint: "travelfriends-fe"},
        env: {VITE_API_URL: apiOrigin, PORT: "8080"},
    });

    const api = service("travelfriends-api", {
        source: github("astakhovaskold/travelfriends", {
            branch: "main",
            checkSuites: false,
            rootDirectory: "/backend",
        }),
        build: {
            buildEnvironment: "V3",
            builder: "DOCKERFILE",
            dockerfilePath: "Dockerfile",
            watchPatterns: ["/backend/**"],
        },
        start: 'sh -c "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"',
        preDeploy: "alembic -c alembic.ini upgrade head",
        healthcheck: "/health",
        healthcheckTimeout: 120,
        replicas: {"europe-west4-drams3a": 1},
        networking: {privateNetworkEndpoint: "travelfriends"},
        env: {
            DATABASE_URL: preserve(),
            MIGRATION_DATABASE_URL: preserve(),
            BOT_TOKEN: preserve(),
            BOT_USERNAME: preserve(),
            ADMIN_ID: preserve(),
            BOOST_STARS: preserve(),
            POSTGRES_PASSWORD: preserve(),
            SESSION_TTL: "2592000",
            WEBAPP_URL: frontendOrigin,
            CORS_ORIGINS: frontendOrigin,
            PORT: "8080",
        },
    });

    return project("travel-friends", {
        variables: {managed: true},
        resources: [web, api],
    });
});
