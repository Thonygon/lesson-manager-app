-- Publish the audio-related terms as a new immutable legal version.
-- Apply only when the corresponding website pages and Expo release are ready.
begin;
update public.classio_legal_publications set active=false
  where slug in ('terms','teacher-data') and active=true;
insert into public.classio_legal_publications(slug,language,version,sha256,effective_date) values
  ('terms','en','2026-11-21.1','db4072e9f64d55e5e2fb414f12e569789e01ebe49a4d935f9f48a2d1d51c6ff8','2026-11-21'),
  ('terms','es','2026-11-21.1','96b3255f27e8b4c63a16df60303a7f6c1bf489d18ac13a3b3f2b327f8d357b73','2026-11-21'),
  ('terms','tr','2026-11-21.1','fb74b57a8941177404d892c15ef75587b79a10952b0219044a8af8825c809772','2026-11-21'),
  ('teacher-data','en','2026-11-21.1','20a9b12825d9b01f37acce65c61fd59a0bfb4597f8d45ef50b658cab23e0c6bd','2026-11-21'),
  ('teacher-data','es','2026-11-21.1','af4d7d98d9ec2a9b497e1ea06d3f2c665b4b5c7878be74be0d288c4f3b86f0e9','2026-11-21'),
  ('teacher-data','tr','2026-11-21.1','30d1a46c26fdf105cefd59177214738b4b95660a5a5e9b0e41a7545e64610769','2026-11-21')
on conflict (slug,language,version) do nothing;
commit;
