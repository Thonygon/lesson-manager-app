import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { colors } from '../styles/theme';
import { DashboardScreen } from '../screens/DashboardScreen';
import { StudentsScreen } from '../screens/StudentsScreen';
import { LessonsScreen } from '../screens/LessonsScreen';
import { PaymentsScreen } from '../screens/PaymentsScreen';
import { SearchScreen } from '../screens/SearchScreen';
import { Text } from 'react-native';

const Tab = createBottomTabNavigator();

const tabIcons: Record<string, string> = {
  Dashboard: '⊞',
  Students: '👥',
  Lessons: '📅',
  Payments: '💳',
  Search: '🔍',
};

export const TabNavigator: React.FC = () => {
  return (
    <Tab.Navigator
      initialRouteName="Lessons"
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.tabBg,
          borderTopWidth: 0,
          height: 80,
          paddingBottom: 20,
          paddingTop: 10,
        },
        tabBarActiveTintColor: colors.tabActive,
        tabBarInactiveTintColor: colors.tabInactive,
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '600',
          marginTop: 4,
        },
        tabBarIcon: ({ color }) => (
          <Text style={{ fontSize: 20, color }}>{tabIcons[route.name]}</Text>
        ),
      })}
    >
      <Tab.Screen name="Dashboard" component={DashboardScreen} />
      <Tab.Screen name="Students" component={StudentsScreen} />
      <Tab.Screen name="Lessons" component={LessonsScreen} />
      <Tab.Screen name="Payments" component={PaymentsScreen} />
      <Tab.Screen name="Search" component={SearchScreen} />
    </Tab.Navigator>
  );
};
