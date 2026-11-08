-- Hold destructive erasure for verified, scoped service handling. The Expo
-- account screen now opens a privacy-rights ticket instead of this RPC.
-- Existing classes, profiles and teacher payment records are untouched.
revoke execute on function public.classio_delete_account_data(text)
  from public, anon, authenticated;
grant execute on function public.classio_delete_account_data(text) to service_role;
