import { Redirect } from 'expo-router';

// Billing becomes visible after a payment provider is configured.
export default function BillingScreen() {
  return <Redirect href="/dashboard" />;
}
