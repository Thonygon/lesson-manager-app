# Classio

For an academic overview of the system, evidence, and limitations, see the [TFM repository guide](docs/TFM_REPOSITORY_GUIDE.md).

Classio is migrating from a Streamlit application to a universal Expo Router application. The repository deliberately keeps both deployments available until feature parity, security review, and production validation are complete.

## Applications

- [`streamlit/`](streamlit/) is the stable Python/Streamlit application and rollback path.
- [`expo/`](expo/) is the new React Native and web application linked to EAS project `@classio/classio`.

The two applications use the same Supabase project and data model. Browser-safe operations can move directly to the Expo application under Row Level Security. Operations that require provider secrets, privileged database access, Python document generation, or ML workloads stay on a protected server boundary until they are deliberately rewritten.

## Run the Streamlit application

Streamlit Cloud can launch the root `app.py`; it delegates to
`streamlit/app.py` and installs the same dependencies through the root
`requirements.txt`. The original local workflow remains:

```bash
cd streamlit
python -m pip install --requirement requirements.lock.txt
streamlit run app.py
```

The local secrets file remains at `streamlit/.streamlit/secrets.toml` and is ignored by Git.

## Run the Expo application

```bash
cd expo
cp .env.example .env.local
pnpm install
pnpm run web
```

Only the Supabase URL and anonymous/publishable key may use the `EXPO_PUBLIC_` prefix. Never place service-role, AI provider, Stripe secret, or Google OAuth client-secret values in Expo environment variables.

## Validation

```bash
cd streamlit
python -m compileall -q app.py app_pages auth core helpers services styles
python scripts/check_migrations.py
python -m unittest discover -s tests

cd ../expo
pnpm run typecheck
pnpm run lint
pnpm run export:web
```

See [`MIGRATION.md`](MIGRATION.md) for the architecture, security boundaries, parity status, and rollout rules.
