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

export interface ScheduleDay {
  day: string;
  date: number;
  isToday: boolean;
  dotCount: number;
}

export const students: Student[] = [
  { id: '1', name: 'Julianna Smith', avatar: '👩‍🎤', color: '#8B9DC3' },
  { id: '2', name: 'Marcus Thorne', avatar: '🧑‍💻', color: '#95C8D8' },
  { id: '3', name: 'Elena Rossi', avatar: '👩‍🏫', color: '#F4A7BB' },
  { id: '4', name: 'Alexander Thompson', avatar: '👨‍🎨', color: '#D4A574' },
  { id: '5', name: 'Isabella Rodriguez', avatar: '👩‍🎨', color: '#A8D5BA' },
  { id: '6', name: 'Marcus Chen-Li', avatar: '🧑‍🎨', color: '#C9A0DC' },
];

export const todayLessons: Lesson[] = [
  {
    id: '1',
    studentId: '1',
    studentName: 'Julianna Smith',
    avatar: '👩‍🎤',
    subject: 'Composition Mastery',
    startTime: '10:30 AM',
    endTime: '11:30 AM',
    duration: 60,
    status: 'upcoming',
    zoomLink: 'https://zoom.us/j/example1',
    color: '#8B9DC3',
  },
  {
    id: '2',
    studentId: '2',
    studentName: 'Marcus Thorne',
    avatar: '🧑‍💻',
    subject: 'Foundations of Oil Painting',
    startTime: '01:00 PM',
    endTime: '02:30 PM',
    duration: 90,
    status: 'upcoming',
    color: '#95C8D8',
  },
  {
    id: '3',
    studentId: '3',
    studentName: 'Elena Rossi',
    avatar: '👩‍🏫',
    subject: 'Art History: Renaissance',
    startTime: '03:30 PM',
    endTime: '04:15 PM',
    duration: 45,
    status: 'upcoming',
    color: '#F4A7BB',
  },
];

export const weekSchedule: ScheduleDay[] = [
  { day: 'MON', date: 12, isToday: false, dotCount: 1 },
  { day: 'TUE', date: 13, isToday: false, dotCount: 0 },
  { day: 'WED', date: 14, isToday: true, dotCount: 3 },
  { day: 'THU', date: 15, isToday: false, dotCount: 0 },
  { day: 'FRI', date: 16, isToday: false, dotCount: 1 },
];

export const upcomingFocus = {
  label: 'NEXT SESSION',
  title: 'Advanced Color Theory',
  startsIn: 'Starts in 45 minutes',
  preparationComplete: 75,
};
