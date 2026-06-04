import React, { useState, useEffect } from 'react';
import Card from '../../components/Card';
import Loader from '../../components/Loader';
import EmptyState from '../../components/EmptyState';
import { eventsApi, tasksApi } from '../../api';
import { PRIORITY_LABELS, STATUS_LABELS, STATUS_BADGE_TYPE, PRIORITY_BADGE_TYPE } from '../../constants';
import Badge from '../../components/Badge';
import styles from './HomePage.module.css';

export default function HomePage() {
  const [events, setEvents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const tg = window.Telegram?.WebApp;
  const user = tg?.initDataUnsafe?.user;
  const firstName = user?.first_name || 'Пользователь';

  const fetchData = (setLoadState) => {
    setLoadState(true);
    const today = new Date().toISOString().split('T')[0];
    return Promise.all([
      eventsApi.list({ date: today, limit: 3 }).catch(() => []),
      tasksApi.list({ limit: 3, status: 'new,in_progress' }).catch(() => []),
    ]).then(([ev, tk]) => {
      setEvents(Array.isArray(ev) ? ev : (ev.items || []));
      setTasks(Array.isArray(tk) ? tk : (tk.items || []));
    }).finally(() => setLoadState(false));
  };

  useEffect(() => { fetchData(setLoading); }, []);

  const handleRefresh = () => fetchData(setRefreshing);

  const today = new Date();
  const dateStr = today.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });

  if (loading) return <Loader text="Загрузка..." />;

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.greeting}>Добрый день, {firstName} 👋</h1>
          <p className={styles.date}>{dateStr}</p>
        </div>
        <button className={styles.refreshBtn} onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '⏳' : '🔄'}
        </button>
      </div>

      {/* Stats row */}
      <div className={styles.statsRow}>
        <div className={styles.statCard} style={{ background: 'var(--color-primary-light)' }}>
          <span className={styles.statIcon}>📋</span>
          <span className={styles.statNum}>{tasks.length}</span>
          <span className={styles.statLabel}>задач</span>
        </div>
        <div className={styles.statCard} style={{ background: 'var(--color-success-light)' }}>
          <span className={styles.statIcon}>🎉</span>
          <span className={styles.statNum}>{events.length}</span>
          <span className={styles.statLabel}>событий</span>
        </div>
        <div className={styles.statCard} style={{ background: 'var(--color-warning-light)' }}>
          <span className={styles.statIcon}>📣</span>
          <span className={styles.statNum}>—</span>
          <span className={styles.statLabel}>объявл.</span>
        </div>
      </div>

      {/* Events section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>📅 Ближайшие события</h2>
        {events.length === 0 ? (
          <EmptyState icon="📅" title="Событий нет" />
        ) : (
          <div className={styles.list}>
            {events.map(ev => (
              <Card key={ev.id} className={styles.eventRow}>
                <span className={styles.eventTime}>
                  🕐{' '}
                  {ev.start_time
                    ? new Date(ev.start_time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
                    : '—'}
                </span>
                <span className={styles.eventTitle}>{ev.title}</span>
                {ev.location && <span className={styles.eventLoc}>📍 {ev.location}</span>}
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Tasks section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>📋 Мои задачи</h2>
        {tasks.length === 0 ? (
          <EmptyState icon="✅" title="Задач нет" />
        ) : (
          <div className={styles.list}>
            {tasks.map(t => (
              <Card key={t.id} className={styles.taskRow}>
                <div className={styles.taskTop}>
                  <Badge
                    type={PRIORITY_BADGE_TYPE[t.priority] || 'default'}
                    text={PRIORITY_LABELS[t.priority] || t.priority}
                  />
                  <span className={styles.taskDeadline}>
                    {t.deadline
                      ? '⏰ ' + new Date(t.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                      : ''}
                  </span>
                </div>
                <p className={styles.taskTitle}>{t.title}</p>
                <Badge
                  type={STATUS_BADGE_TYPE[t.status] || 'default'}
                  text={STATUS_LABELS[t.status] || t.status}
                />
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
