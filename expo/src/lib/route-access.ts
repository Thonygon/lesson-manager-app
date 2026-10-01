import type { ClassioProfile } from '@/types/auth';

const STUDENT_ROUTES = ['/student-home', '/student-practice', '/student-study-plan', '/student-assignments', '/student-find-teacher'];
const TEACHER_ROUTES = ['/home', '/dashboard', '/students', '/student-delete', '/lessons', '/payments', '/calendar', '/resources', '/smart-tools', '/analytics', '/community', '/billing', '/assignments'];
const SHARED_ROUTES = ['/profile', '/account'];
const ADMIN_ROUTES = ['/admin'];
const DEVELOPER_ROUTES = ['/developer-workspace'];

function matches(pathname: string, routes: string[]) {
  return routes.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export function activeFace(profile: ClassioProfile | null) {
  const role = profile?.last_active_mode ?? profile?.primary_role ?? profile?.role;
  return role === 'student' ? 'student' : 'teacher';
}

export function authorizedDestination(pathname: string, profile: ClassioProfile | null, access?: { loading: boolean; isAdmin: boolean; canUseDeveloperWorkspace: boolean }) {
  if (!profile || matches(pathname, SHARED_ROUTES)) return null;
  if (matches(pathname, ADMIN_ROUTES)) {
    if (access?.loading) return null;
    return access?.isAdmin ? null : (activeFace(profile) === 'student' ? '/student-home' : '/home');
  }
  if (matches(pathname, DEVELOPER_ROUTES)) {
    if (access?.loading) return null;
    return access?.canUseDeveloperWorkspace ? null : (activeFace(profile) === 'student' ? '/student-home' : '/home');
  }
  const face = activeFace(profile);
  if (matches(pathname, STUDENT_ROUTES) && face !== 'student') return '/home' as const;
  if (matches(pathname, TEACHER_ROUTES) && face === 'student') return '/student-home' as const;
  return null;
}
