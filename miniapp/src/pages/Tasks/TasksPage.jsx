import React, { useState, useEffect } from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import Loader from '../../components/Loader';
import EmptyState from '../../components/EmptyState';
import { tasksApi } from '../../api';
import { PRIORITY_LABELS, STATUS_LABELS, STATUS_BADGE_TYPE, PRIORITY_BADGE_TYPE } from '../../constants';
import styles from './TasksPage.module.css';

const FILTERS = [
  { key: 'all', label: 'Все' },
  { key: 'new', label: 'Новые' },
  { key: 'in_progress', label: 'В работе' },
  { key: 'overdue', label: 'Просрочены' },
  { key: 'done', label: 'Выполнены' },
];

export default function TasksPage() {
  const [filter, setFilter] = useState('all');
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  const tg = window.Telegram?.WebApp;
  const user = tg?.initDataUnsafe?.user;
  const isAdmin = user?.is_admin; // placeholder; real check should come from backend

  const load = (f) => {
    setLoading(true);
    const params = f !== 'all' ? { status: f } : {};
    tasksApi.list(params)
      .then(data => setTasks(Array.isArray(data) ? data : (data.items || [])))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(filter); }, [filter]);

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <h1 className={styles.title}>📋 Задачи</h1>
      </div>

      {/* Filter tabs */}
      <div className={styles.filters}>
        {FILTERS.map(f => (
          <button
            key={f.key}
            className={`${styles.filterTab} ${filter === f.key ? styles.active : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <Loader />
      ) : tasks.length === 0 ? (
        <EmptyState icon="📋" title="Задач нет" subtitle="Здесь появятся ваши задачи" />
      ) : (
        <div className={styles.list}>
          {tasks.map(task => (
            <Card key={task.id} className={styles.taskCard}>
              <div className={styles.taskTop}>
                <Badge
                  type={PRIORITY_BADGE_TYPE[task.priority] || 'default'}
                  text={PRIORITY_LABELS[task.priority] || task.priority}
                />
                <span className={styles.taskId}>#{task.id}</span>
              </div>
              <p className={styles.taskTitle}>{task.title}</p>
              <div className={styles.taskBottom}>
                {task.assignee_name && (
                  <span className={styles.assignee}>👤 {task.assignee_name}</span>
                )}
                {task.deadline && (
                  <span className={styles.deadline}>
                    ⏰{' '}
                    {new Date(task.deadline).toLocaleDateString('ru-RU', {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </span>
                )}
                <Badge
                  type={STATUS_BADGE_TYPE[task.status] || 'default'}
                  text={STATUS_LABELS[task.status] || task.status}
                />
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* FAB for admin */}
      {isAdmin && (
        <button className={styles.fab} title="Создать задачу">
          ➕
        </button>
      )}
    </div>
  );
}
