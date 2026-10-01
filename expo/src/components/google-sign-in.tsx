import { Button } from '@/components/ui';

export function GoogleSignIn({ disabled, label, onPress }: { disabled: boolean; label: string; onPress: () => void; onCredential?: (token: string, nonce: string) => void; onError?: (message: string) => void }) {
  return <Button secondary disabled={disabled} onPress={onPress}>G  {label}</Button>;
}
