import React, { useState, useEffect, lazy, Suspense } from 'react';
import TabBar from './components/TabBar';
import { ToastProvider } from './components/Toast';
import { useAuth } from './hooks/useAuth';
import HomePage from './pages/Home/HomePage';
import TasksPage from './pages/Tasks/TasksPage';
import CalendarPage from './pages/Calendar/CalendarPage';
import ChildrenPage from './pages/Children/ChildrenPage';
import ManagementPage from './pages/Management/ManagementPage';
import styles from './App.module.css';
import Loader from './components/Loader';

const DutiesPage = lazy(() => import('./pages/Duties/DutiesPage').catch(() => ({ default: () => <div style={{ padding: 20 }}>Дежурства — страница в разработке</div> })));
const CirclesPage = lazy(() => import('./pages/Circles/CirclesPage').catch(() => ({ default: () => <div style={{ padding: 20 }}>Кружки — страница в разработке</div> })));
const AnnouncementsPage = lazy(() => import('./pages/Announcements/AnnouncementsPage'));
const IncidentsPage = lazy(() => import('./pages/Incidents/IncidentsPage'));
const AnalyticsPage = lazy(() => import('./pages/Analytics/AnalyticsPage'));

const tg = window.Telegram?.WebApp;

function getTabsForRole(role) {
  const adminTabs = [
    { id: 'home', label: 'Главная', icon: '🏠' },
    { id: 'tasks', label: 'Задачи', icon: '📋' },
    { id: 'calendar', label: 'Календарь', icon: '📅' },
    { id: 'children', label: 'Дети', icon: '👦' },
    { id: 'management', label: 'Управление', icon: '⚙️' },
    { id: 'analytics', label: 'Аналитика', icon: '📊' },
  ];
  const counselorTabs = [
    { id: 'home', label: 'Главная', icon: '🏠' },
    { id: 'tasks', label: 'Задачи', icon: '📋' },
    { id: 'calendar', label: 'Календарь', icon: '📅' },
    { id: 'children', label: 'Дети', icon: '👦' },
    { id: 'duties', label: 'Дежурство', icon: '🔄' },
  ];
  const coachTabs = [
    { id: 'home', label: 'Главная', icon: '🏠' },
    { id: 'tasks', label: 'Задачи', icon: '📋' },
    { id: 'calendar', label: 'Календарь', icon: '📅' },
    { id: 'incidents', label: 'Инциденты', icon: '🚨' },
    { id: 'announcements', label: 'Объявления', icon: '📣' },
  ];
  const circleLeaderTabs = [
    { id: 'home', label: 'Главная', icon: '🏠' },
    { id: 'tasks', label: 'Задачи', icon: '📋' },
    { id: 'circles', label: 'Кружок', icon: '🧩' },
    { id: 'attendance', label: 'Посещ.', icon: '✅' },
    { id: 'calendar', label: 'Календарь', icon: '📅' },
  ];
  if (!role || role === 'admin' || role === 'senior_counselor') return adminTabs;
  if (role === 'counselor' || role === 'educator') return counselorTabs;
  if (role === 'coach' || role === 'swim_coach' || role === 'music') return coachTabs;
  if (role === 'circle_leader') return circleLeaderTabs;
  return adminTabs;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const { staff, loading: authLoading } = useAuth();

  useEffect(() => {
    if (tg?.colorScheme === 'dark') {
      document.documentElement.classList.add('dark');
    }
  }, []);

  const tabs = getTabsForRole(staff?.role);

  const renderPage = () => {
    switch (activeTab) {
      case 'home':
        return <HomePage staff={staff} />;
      case 'tasks':
        return <TasksPage staff={staff} />;
      case 'calendar':
        return <CalendarPage staff={staff} />;
      case 'children':
        return <ChildrenPage staff={staff} />;
      case 'management':
        return <ManagementPage staff={staff} />;
      case 'duties':
        return (
          <Suspense fallback={<Loader center />}>
            <DutiesPage staff={staff} />
          </Suspense>
        );
      case 'circles':
      case 'attendance':
        return (
          <Suspense fallback={<Loader center />}>
            <CirclesPage staff={staff} />
          </Suspense>
        );
      case 'incidents':
        return (
          <Suspense fallback={<Loader center />}>
            <IncidentsPage staff={staff} />
          </Suspense>
        );
      case 'announcements':
        return (
          <Suspense fallback={<Loader center />}>
            <AnnouncementsPage staff={staff} />
          </Suspense>
        );
      case 'analytics':
        return (
          <Suspense fallback={<Loader center />}>
            <AnalyticsPage staff={staff} />
          </Suspense>
        );
      default:
        return <HomePage staff={staff} />;
    }
  };

  if (authLoading) {
    return (
      <div className={`app ${styles.app}`}>
        <Loader center />
      </div>
    );
  }

  return (
    <ToastProvider>
      <div className={`app ${styles.app}`}>
        {renderPage()}
        <TabBar tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
      </div>
    </ToastProvider>
  );
}
