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

## Google sign-in on the hosted web app

Set `EXPO_PUBLIC_GOOGLE_CLIENT_ID` to the Google OAuth web client ID. In Google Cloud, add `https://classio.expo.app` as an authorized JavaScript origin for that client. The web sign-in page uses Google Identity Services to obtain an ID token on the Classio origin, then exchanges it for a Supabase session with a nonce. The Google account chooser should identify the Classio origin instead of the Supabase project hostname. This does not change the native app's OAuth redirect flow.

The client ID is public. Keep the client secret in the existing Supabase Google provider configuration; never put it in an `EXPO_PUBLIC_` variable. If the Google client is in Testing mode, only configured test users can sign in.

## EAS Hosting

```bash
pnpm deploy:classio
```

This deploys to `https://classio.expo.app`. The project currently stores its deployment variables in EAS `preview` (EAS `production` has none), so the command pulls `preview` variables before a clean export and publishes that build to the production hostname. Move the variables to EAS `production` before changing the environment flag.

Promote to production only after the migration gates in the repository's `docs/MIGRATION.md` are satisfied. EAS Hosting deploys the web app; iOS and Android store distribution require separate EAS Build and Submit configuration.
