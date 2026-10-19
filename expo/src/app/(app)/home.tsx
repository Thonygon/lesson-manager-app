import { Redirect } from 'expo-router';
import { useAuth } from '@/providers/auth-provider';

export default function TeacherHomeRedirect() {
  const { profile } = useAuth();
  return <Redirect href={profile?.last_active_mode === 'student' ? '/student-home' : '/dashboard'} />;
}
