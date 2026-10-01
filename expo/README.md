# Classio Expo application

This directory contains the Expo Router replacement frontend for Classio. It is linked to the EAS project `@classio/classio`.

## Local validation

```bash
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm export:web
```

Copy `.env.example` to `.env.local` for local development. Use only a Supabase publishable or anonymous key. Never put a service-role key or provider secret in an `EXPO_PUBLIC_` variable.

## EAS Hosting

```bash
pnpm deploy:classio
```

This deploys to `https://classio.expo.app`. The project currently stores its deployment variables in EAS `preview` (EAS `production` has none), so the command pulls `preview` variables before a clean export and publishes that build to the production hostname. Move the variables to EAS `production` before changing the environment flag.

Promote to production only after the migration gates in the repository's `MIGRATION.md` are satisfied. EAS Hosting deploys the web app; iOS and Android store distribution require separate EAS Build and Submit configuration.
