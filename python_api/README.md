# Classio Python inference service

This service exposes the existing Python student recommendation fit and the
approved resource affinity representation to Expo. It does not retrain or
approve experiment runs. Supabase Auth validates every request; resource reads
use the caller's JWT and Row Level Security.

Set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and
`CLASSIO_RESOURCE_AFFINITY_RUN_ID` to the active `PRODUCTION_RUNTIME` run approved
in Streamlit. Set `SUPABASE_SECRET_KEY` (or the legacy
`SUPABASE_SERVICE_ROLE_KEY`) **only on the Python server** so it can verify the
approval record and fetch the private model bundle. The runtime verifies bundle
and representation checksums before unpickling. Set
`PYTHONPATH=streamlit` and launch `uvicorn python_api.app:app` from the repository
root. Never include the server key or private model bundle in Expo or Git.
Set `CLASSIO_EXPO_ORIGINS` to the comma separated Expo web origins allowed to
call the service; it defaults to `https://classio.expo.app`. Configure Expo's
`EXPO_PUBLIC_CLASSIO_API_URL` to the HTTPS address of this service.

The Expo client may call `GET /v1/models/resource-affinity`,
`POST /v1/resource-affinity/score`, and
`POST /v1/student-recommendations/score`, and
`GET /v1/program-topics/{program_id}/{topic_id}/recommendations` with a Supabase bearer token. The
student score endpoint accepts bounded, caller supplied features and samples;
it does not fetch history on behalf of another user. Live rollout requires
authenticated staging acceptance and a pinned model run. Use
`GET /v1/auth/check` with the signed-in Supabase bearer token to verify the
Expo-to-Python identity boundary separately from model readiness. The Expo
Developer ML Lab has a control that checks both authentication and the active
model without exposing credentials.

For newly validated resource affinity runs, Streamlit backs up the runtime
representation to a private staging path in Supabase Storage while the run
files are still present. This backup is not available to inference before
human approval. After an authorized data scientist activates a validated run, use
**Publish approved model files for the Python API** in Streamlit's Developer
Workspace. This copies the minimal runtime representation to the private
`ml-runtime-artifacts` Supabase Storage bucket with an immutable manifest. The
button can also publish from the verified private backup after a Streamlit
restart. Runs made before this backup existed cannot be restored from database
metadata alone if their local files have disappeared; they need a fresh
evaluation and human review. The
Python API downloads the bundle on first use, verifies the approval in
`ml_experiment_runs`, checks file hashes and then loads the frozen estimator.
Render's ephemeral disk may clear between restarts; the bundle is downloaded
again when needed. A different run becomes active only after its own bundle is
published and `CLASSIO_RESOURCE_AFFINITY_RUN_ID` is changed on Render. If the
pin is revoked or its artifact is absent, scoring fails closed and Expo keeps
its local ranker.
The resource affinity endpoint accepts lesson plans, worksheets, exams, and
videos. The teacher recommendation view uses this trained affinity score when
the Python service is configured and reachable; its local feature ranker
continues to serve recommendations if that service is unavailable.
