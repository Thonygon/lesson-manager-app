import { Redirect } from 'expo-router';
import { activeFace } from '@/lib/route-access';
import { useAuth } from '@/providers/auth-provider';

export default function TeacherHomeRedirect() {
  const { profile } = useAuth();
  return <Redirect href={activeFace(profile) === 'student' ? '/student-home' : '/dashboard'} />;
}
