export interface Student {
  id: string;
  name: string;
  avatar: string;
  color: string;
}

export interface Lesson {
  id: string;
  studentId: string;
  studentName: string;
  avatar: string;
  subject: string;
  startTime: string;
  endTime: string;
  duration: number;
  status: 'upcoming' | 'in-progress' | 'completed' | 'cancelled';
  zoomLink?: string;
  color: string;
}

export interface Payment {
  id: string;
  studentId: string;
  studentName: string;
  amount: number;
  currency: string;
  units: number;
  usedUnits: number;
  startDate: string;
  expiryDate: string;
}

export interface ScheduleDay {
  day: string;
  date: number;
  isToday: boolean;
  dotCount: number;
}

export const students: Student[] = [
  { id: '1', name: 'Alexander Thompson-Vanderbilt', avatar: '👨‍🎨', color: '#D4A574' },
  { id: '2', name: 'Isabella Rodriguez', avatar: '👩‍🎨', color: '#8B9DC3' },
  { id: '3', name: 'Marcus Chen-Li', avatar: '🧑‍🎨', color: '#A8D5BA' },
  { id: '4', name: 'Julianna Smith', avatar: '👩‍🎤', color: '#C9A0DC' },
  { id: '5', name: 'Elena Rossi', avatar: '👩‍🏫', color: '#F4A7BB' },
  { id: '6', name: 'Marcus Thorne', avatar: '🧑‍💻', color: '#95C8D8' },
];

export const todayLessons: Lesson[] = [
  {
    id: '1',
    studentId: '1',
    studentName: 'Alexander Thompson-Vanderbilt',
    avatar: '👨‍🎨',
    subject: 'Advanced Music Theory',
    startTime: '10:00 AM',
    endTime: '11:30 AM',
    duration: 90,
    status: 'upcoming',
    zoomLink: 'https://zoom.us/j/example1',
    color: '#D4A574',
  },
  {
    id: '2',
    studentId: '2',
    studentName: 'Isabella Rodriguez',
    avatar: '👩‍🎨',
    subject: 'Color Composition',
    startTime: '2:00 PM',
    endTime: '3:00 PM',
    duration: 60,
    status: 'upcoming',
    zoomLink: 'https://zoom.us/j/example2',
    color: '#8B9DC3',
  },
  {
    id: '3',
    studentId: '3',
    studentName: 'Marcus Chen-Li',
    avatar: '🧑‍🎨',
    subject: 'Narrative Structuring',
    startTime: '4:30 PM',
    endTime: '5:30 PM',
    duration: 60,
    status: 'upcoming',
    color: '#A8D5BA',
  },
];

export const weekSchedule: ScheduleDay[] = [
  { day: 'MON', date: 14, isToday: false, dotCount: 1 },
  { day: 'TUE', date: 15, isToday: false, dotCount: 0 },
  { day: 'WED', date: 16, isToday: true, dotCount: 3 },
  { day: 'THU', date: 17, isToday: false, dotCount: 0 },
  { day: 'FRI', date: 18, isToday: false, dotCount: 2 },
  { day: 'SAT', date: 19, isToday: false, dotCount: 0 },
  { day: 'SUN', date: 20, isToday: false, dotCount: 0 },
];

export const quickActions = [
  { id: 'assignment', label: 'Add Assignment', icon: 'assignment' },
  { id: 'emails', label: 'Parent Emails', icon: 'email' },
  { id: 'report', label: 'Monthly Report', icon: 'report' },
  { id: 'archived', label: 'Archived Plans', icon: 'archive' },
];

export const educatorFocus = {
  title: 'Curriculum Review Week',
  description:
    'This week is dedicated to refining your "Advanced Composition" modules. 4 students are currently awaiting their feedback reports.',
  reviewProgress: 65,
};

export const studioCapacity = {
  current: 24,
  total: 30,
};
