import React, { useState, useEffect, useCallback } from 'react';
import { eventsApi, tasksApi, announcementsApi } from '../../api';
import Badge from '../../components/Badge';
import Card from '../../components/Card';
import Loader from '../../components/Loader';
import styles from './HomePage.module.css';

const PRIORITY_VARIANT = { high: 'danger', medium: 'warning', low: 'success' };
const PRIORITY_LABEL = { high: 'Высокий', medium: 'Средний', low: 'Низкий' };
const STATUS_VARIANT = { new: 'primary', in_progress: 'warning', done: 'success', overdue: 'danger' };
const STATUS_LABEL = { new: 'Новая', in_progress: 'В работе', done: 'Выполнена', overdue: 'Просрочена' };

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Доброе утро';
  if (h < 17) return 'Добрый день';
  return 'Добрый вечер';
}

function fmtDate() {
  return new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
}

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

function fmtDeadline(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function isToday(iso) {
  if (!iso) return false;
  const d = new Date(iso);
  const n = new Date();
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
}

function firstName(name) {
  if (!name) return '';
  return name.trim().split(/\s+/)[1] || name.trim().split(/\s+/)[0] || '';
}

export default function HomePage({ staff }) {
  const [events, setEvents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [markingRead, setMarkingRead] = useState(null);

  const isAdmin = staff?.role === 'admin' || staff?.role === 'senior_counselor';

  const load = useCallback((isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    const taskParams = isAdmin ? {} : { assigned_to: staff?.id };
    Promise.all([
      eventsApi.list(),
      tasksApi.list(taskParams),
      announcementsApi.list(),
    ])
      .then(([evData, taskData, annData]) => {
        setEvents(evData.items || evData);
        setTasks(taskData.items || taskData);
        setAnnouncements(annData.items || annData);
      })
      .catch(() => {})
      .finally(() => { setLoading(false); setRefreshing(false); });
  }, [isAdmin, staff?.id]);

  useEffect(() => { load(); }, [load]);

  const handleMarkRead = (id) => {
    setMarkingRead(id);
    announcementsApi.markRead(id)
      .then(() => load(true))
      .catch(() => {})
      .finally(() => setMarkingRead(null));
  };

  const todayEvents = events
    .filter(e => isToday(e.start_time || e.date))
    .sort((a, b) => new Date(a.start_time || a.date) - new Date(b.start_time || b.date))
    .slice(0, 3);

  const myTasks = tasks
    .filter(t => t.status !== 'done')
    .slice(0, 3);

  const unreadAnnouncements = announcements.filter(a => !a.is_read).slice(0, 3);

  const role = staff?.role;
  let stats;
  if (isAdmin) {
    stats = [
      { icon: '📋', num: tasks.filter(t => isToday(t.deadline) || t.status === 'new').length, label: 'Задач' },
      { icon: '📅', num: todayEvents.length, label: 'Мероприятий' },
      { icon: '🔔', num: unreadAnnouncements.length, label: 'Непрочитанных' },
    ];
  } else if (role === 'counselor' || role === 'educator') {
    stats = [
      { icon: '📋', num: tasks.filter(t => t.assigned_to === staff?.id && t.status !== 'done').length, label: 'Мои задачи' },
      { icon: '📅', num: todayEvents.length, label: 'Сегодня' },
      { icon: '🎂', num: 0, label: 'Именинников' },
    ];
  } else {
    stats = [
      { icon: '📋', num: tasks.filter(t => t.status !== 'done').length, label: 'Задач' },
      { icon: '📅', num: todayEvents.length, label: 'Сегодня' },
      { icon: '🔔', num: unreadAnnouncements.length, label: 'Объявлений' },
    ];
  }

  const statBg = [
    'var(--color-primary-light)',
    'var(--color-success-light)',
    'var(--color-warning-light)',
  ];

  if (loading) return <Loader center />;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.greeting}>
            {greeting()}{staff?.full_name ? `, ${firstName(staff.full_name)}` : ''}!
          </div>
          <div className={styles.date}>{fmtDate()}</div>
        </div>
        <button
          className={styles.refreshBtn}
          onClick={() => load(true)}
          disabled={refreshing}
          title="Обновить"
        >
          {refreshing ? '⏳' : '🔄'}
        </button>
      </div>

      <div className={styles.statsRow}>
        {stats.map((s, i) => (
          <div key={i} className={styles.statCard} style={{ background: statBg[i] }}>
            <span className={styles.statIcon}>{s.icon}</span>
            <span className={styles.statNum}>{s.num}</span>
            <span className={styles.statLabel}>{s.label}</span>
          </div>
        ))}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Ближайшие события</div>
        {todayEvents.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>Сегодня нет мероприятий</div>
        ) : (
          <div className={styles.list}>
            {todayEvents.map(ev => (
              <Card key={ev.id}>
                <div className={styles.eventRow}>
                  <span className={styles.eventTime}>{fmtTime(ev.start_time)}</span>
                  <span className={styles.eventTitle}>{ev.title}</span>
                </div>
                {ev.location && <div className={styles.eventLoc}>📍 {ev.location}</div>}
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Мои задачи</div>
        {myTasks.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>Нет активных задач</div>
        ) : (
          <div className={styles.list}>
            {myTasks.map(task => (
              <Card key={task.id}>
                <div className={styles.taskRow}>
                  <div className={styles.taskTop}>
                    <Badge variant={PRIORITY_VARIANT[task.priority] || 'default'}>
                      {PRIORITY_LABEL[task.priority] || task.priority || 'Обычный'}
                    </Badge>
                    {task.deadline && (
                      <span className={styles.taskDeadline}>⏰ {fmtDeadline(task.deadline)}</span>
                    )}
                  </div>
                  <div className={styles.taskTitle}>{task.title}</div>
                  <Badge variant={STATUS_VARIANT[task.status] || 'default'}>
                    {STATUS_LABEL[task.status] || task.status}
                  </Badge>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {unreadAnnouncements.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Объявления</div>
          <div className={styles.list}>
            {unreadAnnouncements.map(ann => (
              <Card key={ann.id}>
                <div className={styles.taskRow}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text)' }}>
                    {ann.title}
                  </div>
                  {ann.text && (
                    <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                      {ann.text}
                    </div>
                  )}
                  <button
                    style={{ alignSelf: 'flex-start', marginTop: 4, padding: '6px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--color-success-light)', color: 'var(--color-success)', border: 'none', fontWeight: 600, fontSize: 13 }}
                    disabled={markingRead === ann.id}
                    onClick={() => handleMarkRead(ann.id)}
                  >
                    {markingRead === ann.id ? '...' : '✅ Прочитано'}
                  </button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
