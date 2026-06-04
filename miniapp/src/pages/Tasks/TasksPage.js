import React, { useState, useEffect, useCallback } from 'react';
import { tasksApi, staffApi } from '../../api';
import Badge from '../../components/Badge';
import Card from '../../components/Card';
import Modal from '../../components/Modal';
import Loader from '../../components/Loader';
import EmptyState from '../../components/EmptyState';
import styles from './TasksPage.module.css';

const PRIORITY_VARIANT = { high: 'danger', medium: 'warning', low: 'success' };
const PRIORITY_LABEL = { high: 'Высокий', medium: 'Средний', low: 'Низкий' };
const STATUS_VARIANT = { new: 'primary', in_progress: 'warning', done: 'success', overdue: 'danger' };
const STATUS_LABEL = { new: 'Новая', in_progress: 'В работе', done: 'Выполнена', overdue: 'Просрочена' };

const FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'new', label: 'Новые' },
  { id: 'in_progress', label: 'В работе' },
  { id: 'overdue', label: 'Просрочены' },
  { id: 'done', label: 'Выполнены' },
];

function fmtDeadline(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const inputStyle = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '10px 12px',
  borderRadius: 'var(--radius-sm)',
  border: '1.5px solid var(--color-border)',
  fontSize: 14,
  color: 'var(--color-text)',
  background: 'var(--color-bg)',
  marginBottom: 12,
};

const labelStyle = {
  display: 'block',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--color-text-secondary)',
  marginBottom: 4,
};

const pillGroupStyle = { display: 'flex', gap: 8, marginBottom: 12 };

const pillStyle = (active) => ({
  padding: '6px 14px',
  borderRadius: 20,
  border: `1.5px solid ${active ? 'var(--color-primary)' : 'var(--color-border)'}`,
  background: active ? 'var(--color-primary)' : 'var(--color-surface)',
  color: active ? '#fff' : 'var(--color-text-secondary)',
  fontWeight: 600,
  fontSize: 13,
});

const primaryBtnStyle = {
  width: '100%',
  padding: '12px',
  borderRadius: 'var(--radius-md)',
  background: 'var(--color-primary)',
  color: '#fff',
  border: 'none',
  fontWeight: 600,
  fontSize: 15,
  marginTop: 4,
};

const actionBtnStyle = (color) => ({
  flex: 1,
  padding: '10px 8px',
  borderRadius: 'var(--radius-sm)',
  background: color + '20',
  color: color,
  border: `1.5px solid ${color}40`,
  fontWeight: 600,
  fontSize: 13,
});

const detailFieldStyle = {
  fontSize: 13,
  color: 'var(--color-text-secondary)',
  marginBottom: 6,
};

export default function TasksPage({ staff }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [staffList, setStaffList] = useState([]);

  const [form, setForm] = useState({ title: '', assigned_to: '', priority: 'medium', deadline: '' });

  const isAdmin = staff?.role === 'admin' || staff?.role === 'senior_counselor';

  const load = useCallback(() => {
    setLoading(true);
    const params = isAdmin ? {} : { assigned_to: staff?.id };
    tasksApi.list(params)
      .then(data => setTasks(data.items || data))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, [isAdmin, staff?.id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (isAdmin) {
      staffApi.list()
        .then(data => setStaffList(data.items || data))
        .catch(() => {});
    }
  }, [isAdmin]);

  const filtered = tasks.filter(t => {
    if (filter === 'all') return true;
    return t.status === filter;
  });

  const staffName = (id) => {
    const s = staffList.find(s => s.id === id || s.id === Number(id));
    return s ? (s.full_name || s.name || `#${id}`) : `#${id}`;
  };

  const handleAction = (action) => {
    if (!selected) return;
    setActionLoading(true);
    let newStatus;
    if (action === 'start') newStatus = 'in_progress';
    if (action === 'done') newStatus = 'done';
    tasksApi.update(selected.id, { status: newStatus })
      .then(() => { load(); setSelected(null); })
      .catch(() => {})
      .finally(() => setActionLoading(false));
  };

  const handleDelete = () => {
    if (!selected) return;
    setActionLoading(true);
    tasksApi.delete(selected.id)
      .then(() => { load(); setSelected(null); })
      .catch(() => {})
      .finally(() => setActionLoading(false));
  };

  const handleCreate = () => {
    if (!form.title.trim()) return;
    setActionLoading(true);
    tasksApi.create({
      title: form.title.trim(),
      assigned_to: form.assigned_to ? Number(form.assigned_to) : undefined,
      priority: form.priority,
      deadline: form.deadline || undefined,
    })
      .then(() => {
        load();
        setShowCreate(false);
        setForm({ title: '', assigned_to: '', priority: 'medium', deadline: '' });
      })
      .catch(() => {})
      .finally(() => setActionLoading(false));
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Задачи</div>
      </div>

      <div className={styles.filters}>
        {FILTERS.map(f => (
          <button
            key={f.id}
            className={`${styles.filterTab}${filter === f.id ? ' ' + styles.active : ''}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loader center />
      ) : filtered.length === 0 ? (
        <EmptyState icon="📋" title="Нет задач" subtitle="По выбранному фильтру задач нет" />
      ) : (
        <div className={styles.list}>
          {filtered.map(task => (
            <Card key={task.id} onClick={() => setSelected(task)}>
              <div className={styles.taskCard}>
                <div className={styles.taskTop}>
                  <Badge variant={PRIORITY_VARIANT[task.priority] || 'default'}>
                    {PRIORITY_LABEL[task.priority] || task.priority || '—'}
                  </Badge>
                  <span className={styles.taskId}>#{task.id}</span>
                </div>
                <div className={styles.taskTitle}>{task.title}</div>
                <div className={styles.taskBottom}>
                  {task.assigned_to && (
                    <span className={styles.assignee}>
                      👤 {isAdmin ? staffName(task.assigned_to) : (staff?.full_name || `#${task.assigned_to}`)}
                    </span>
                  )}
                  {task.deadline && (
                    <span className={styles.deadline}>⏰ {fmtDeadline(task.deadline)}</span>
                  )}
                  <Badge variant={STATUS_VARIANT[task.status] || 'default'}>
                    {STATUS_LABEL[task.status] || task.status}
                  </Badge>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {isAdmin && (
        <button className={styles.fab} onClick={() => setShowCreate(true)}>➕</button>
      )}

      {selected && (
        <Modal title={`Задача #${selected.id}`} onClose={() => setSelected(null)} fullHeight>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--color-text)', marginBottom: 8 }}>
              {selected.title}
            </div>
            <div style={detailFieldStyle}>
              Приоритет: <Badge variant={PRIORITY_VARIANT[selected.priority] || 'default'}>
                {PRIORITY_LABEL[selected.priority] || selected.priority || '—'}
              </Badge>
            </div>
            <div style={detailFieldStyle}>
              Статус: <Badge variant={STATUS_VARIANT[selected.status] || 'default'}>
                {STATUS_LABEL[selected.status] || selected.status}
              </Badge>
            </div>
            {selected.assigned_to && (
              <div style={detailFieldStyle}>
                Исполнитель: {isAdmin ? staffName(selected.assigned_to) : (staff?.full_name || `#${selected.assigned_to}`)}
              </div>
            )}
            {selected.deadline && (
              <div style={detailFieldStyle}>Дедлайн: {fmtDeadline(selected.deadline)}</div>
            )}
            {selected.description && (
              <div style={{ fontSize: 14, color: 'var(--color-text)', lineHeight: 1.5, marginTop: 4 }}>
                {selected.description}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
              {selected.assigned_to === staff?.id && selected.status === 'new' && (
                <button
                  style={actionBtnStyle('var(--color-warning)')}
                  disabled={actionLoading}
                  onClick={() => handleAction('start')}
                >
                  🔄 В работу
                </button>
              )}
              {selected.assigned_to === staff?.id && selected.status !== 'done' && (
                <button
                  style={actionBtnStyle('var(--color-success)')}
                  disabled={actionLoading}
                  onClick={() => handleAction('done')}
                >
                  ✅ Выполнить
                </button>
              )}
              {isAdmin && (
                <button
                  style={actionBtnStyle('var(--color-danger)')}
                  disabled={actionLoading}
                  onClick={handleDelete}
                >
                  🗑 Удалить
                </button>
              )}
            </div>
          </div>
        </Modal>
      )}

      {showCreate && (
        <Modal title="Новая задача" onClose={() => setShowCreate(false)}>
          <label style={labelStyle}>Название</label>
          <input
            style={inputStyle}
            placeholder="Введите название задачи"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
          />
          <label style={labelStyle}>ID сотрудника</label>
          <input
            style={inputStyle}
            placeholder="ID сотрудника"
            type="number"
            value={form.assigned_to}
            onChange={e => setForm(f => ({ ...f, assigned_to: e.target.value }))}
          />
          <label style={labelStyle}>Приоритет</label>
          <div style={pillGroupStyle}>
            {[['low', '🟢 Низкий'], ['medium', '🟡 Средний'], ['high', '🔴 Высокий']].map(([val, lbl]) => (
              <button
                key={val}
                style={pillStyle(form.priority === val)}
                onClick={() => setForm(f => ({ ...f, priority: val }))}
              >
                {lbl}
              </button>
            ))}
          </div>
          <label style={labelStyle}>Дедлайн</label>
          <input
            style={inputStyle}
            type="datetime-local"
            value={form.deadline}
            onChange={e => setForm(f => ({ ...f, deadline: e.target.value }))}
          />
          <button
            style={primaryBtnStyle}
            disabled={!form.title.trim() || actionLoading}
            onClick={handleCreate}
          >
            {actionLoading ? 'Создание...' : 'Создать задачу'}
          </button>
        </Modal>
      )}
    </div>
  );
}
