# Classio Python inference service

This service exposes the existing Python student recommendation fit and the
approved resource affinity representation to Expo. It does not retrain or
publish experiment runs. Supabase Auth validates every request; resource reads
use the caller's JWT and Row Level Security.

Set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and
`CLASSIO_RESOURCE_AFFINITY_RUN_ID` to an approved run whose artifact files are
available under `streamlit/reports/ml_architecture/resource_affinity_unsupervised/runs`.
The runtime verifies representation checksums before unpickling. Set
`PYTHONPATH=streamlit` and launch `uvicorn python_api.app:app` from the repository
root. Do not include service role credentials or model artifacts in Expo.
Set `CLASSIO_EXPO_ORIGINS` to the comma separated Expo web origins allowed to
call the service; it defaults to `https://classio.expo.app`. Configure Expo's
`EXPO_PUBLIC_CLASSIO_API_URL` to the HTTPS address of this service.

The Expo client may call `GET /v1/models/resource-affinity`,
`POST /v1/resource-affinity/score`, and
`POST /v1/student-recommendations/score`, and
`GET /v1/program-topics/{program_id}/{topic_id}/recommendations` with a Supabase bearer token. The
student score endpoint accepts bounded, caller supplied features and samples;
it does not fetch history on behalf of another user. Live rollout requires
authenticated staging acceptance and a pinned model run.
The resource affinity endpoint accepts lesson plans, worksheets, exams, and
videos. The teacher recommendation view uses this trained affinity score when
the Python service is configured and reachable; its local feature ranker
continues to serve recommendations if that service is unavailable.
