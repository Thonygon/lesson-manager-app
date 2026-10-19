import { Redirect } from 'expo-router';

// Keep old bookmarks working while Profile owns account settings.
export default function AccountRedirect() {
  return <Redirect href="/profile" />;
}
