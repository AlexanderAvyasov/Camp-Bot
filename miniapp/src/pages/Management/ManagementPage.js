import React, { useCallback, useEffect, useState } from 'react';
import { staffApi, squadsApi, announcementsApi, incidentsApi, dutiesApi } from '../../api';
import styles from './ManagementPage.module.css';

const ROLE_LABELS = {
  admin: 'Администратор', senior_counselor: 'Ст. вожатый',
  counselor: 'Вожатый', educator: 'Воспитатель',
  coach: 'Тренер', swim_coach: 'Тренер по плаванию',
  music: 'Муз. руководитель', circle_leader: 'Рук. кружка',
};
const DUTY_TYPES = { dining: '🍽 Столовая', territory: '🌿 Территория', dormitory: '🏠 Корпус', night: '🌙 Ночное' };
const DUTY_COLORS = { scheduled: '#999', active: '#2563EB', completed: '#16A34A' };
const INCIDENT_TYPES = { medical: '🩺 Медицинский', disciplinary: '⚠️ Дисциплинарный', property: '🔧 Имущество', other: '❓ Прочее' };

function initials(name) {
  if (!name) return '?';
  const p = name.trim().split(/\s+/);
  return (p[0]?.[0] || '') + (p[1]?.[0] || '');
}

const MENU = [
  { id: 'staff', icon: '👥', label: 'Сотрудники' },
  { id: 'squads', icon: '🏕', label: 'Отряды' },
  { id: 'duties', icon: '🔄', label: 'Дежурства' },
  { id: 'announcements', icon: '📣', label: 'Объявления' },
  { id: 'incidents', icon: '🚨', label: 'Инциденты' },
];

export default function ManagementPage({ staff }) {
  const [section, setSection] = useState(null);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [incidentType, setIncidentType] = useState('');
  const [editTarget, setEditTarget] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [squads, setSquads] = useState([]);
  const [saving, setSaving] = useState(false);
  const [weekDays, setWeekDays] = useState([]);

  useEffect(() => {
    squadsApi.list().then(setSquads).catch(() => {});
    const today = new Date();
    const mon = new Date(today);
    mon.setDate(today.getDate() - ((today.getDay() + 6) % 7));
    setWeekDays(Array.from({ length: 7 }, (_, i) => { const d = new Date(mon); d.setDate(mon.getDate() + i); return d; }));
  }, []);

  const loadSection = useCallback(async (s) => {
    setSection(s);
    setData([]);
    setSearch('');
    setLoading(true);
    try {
      if (s === 'staff') setData(await staffApi.list().then(r => r.items || r));
      else if (s === 'squads') setData(await squadsApi.list());
      else if (s === 'duties') setData(await dutiesApi.list({ week: true }));
      else if (s === 'announcements') setData(await announcementsApi.list({ limit: 30 }));
      else if (s === 'incidents') setData(await incidentsApi.list({ page_size: 30 }));
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, []);

  async function saveEdit() {
    setSaving(true);
    try {
      await staffApi.update(editTarget.id, {
        role: editForm.role,
        squad_id: editForm.squad_id ? Number(editForm.squad_id) : null,
        is_active: editForm.is_active,
      });
      setData(prev => prev.map(s => s.id === editTarget.id ? { ...s, ...editForm } : s));
      setEditTarget(null);
    } catch (e) { console.error(e); } finally { setSaving(false); }
  }

  const filtered = section === 'staff'
    ? data.filter(s => !search || s.full_name.toLowerCase().includes(search.toLowerCase()))
    : section === 'incidents' && incidentType
      ? data.filter(i => i.type === incidentType)
      : data;

  function renderStaff() {
    return (
      <>
        <div className={styles.sectionSearch}>
          <input className={styles.searchInput} placeholder="🔍 Поиск…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className={styles.staffList}>
          {filtered.map(s => (
            <div key={s.id} className={`${styles.staffRow} ${!s.is_active ? styles.staffInactive : ''}`}
              onClick={() => { setEditTarget(s); setEditForm({ role: s.role, squad_id: s.squad_id || '', is_active: s.is_active }); }}>
              <div className={styles.staffAvatar}>{initials(s.full_name).toUpperCase()}</div>
              <div className={styles.staffInfo}>
                <div className={styles.staffName}>{s.full_name}</div>
                <div className={styles.staffMeta}>
                  <span className={styles.roleBadge}>{ROLE_LABELS[s.role] || s.role}</span>
                  {s.squad_id && <span className={styles.squadBadge}>Отряд</span>}
                </div>
              </div>
              <span className={styles.staffStatus}>{s.is_active ? '🟢' : '🔴'}</span>
            </div>
          ))}
        </div>
      </>
    );
  }

  function renderSquads() {
    return (
      <div className={styles.squadsGrid}>
        {filtered.map(sq => (
          <div key={sq.id} className={styles.squadCard}>
            <div className={styles.squadName}>Отряд {sq.name}</div>
            {sq.counselor && <div className={styles.squadMeta}>🧑 {sq.counselor.full_name}</div>}
            {sq.educator && <div className={styles.squadMeta}>👩 {sq.educator.full_name}</div>}
          </div>
        ))}
      </div>
    );
  }

  function renderDuties() {
    const types = Object.keys(DUTY_TYPES);
    return (
      <div style={{ overflowX: 'auto', padding: '0 16px 80px' }}>
        <table className={styles.dutiesTable}>
          <thead>
            <tr>
              <th className={styles.dutiesTypeCol}>Тип</th>
              {weekDays.map(d => <th key={d.toISOString()}>{d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric' })}</th>)}
            </tr>
          </thead>
          <tbody>
            {types.map(type => (
              <tr key={type}>
                <td className={`${styles.dutiesCell} ${styles.dutiesTypeCol}`}>{DUTY_TYPES[type]}</td>
                {weekDays.map(day => {
                  const duty = filtered.find(d => d.type === type && new Date(d.date).toDateString() === day.toDateString());
                  return (
                    <td key={day.toISOString()} className={styles.dutiesCell}>
                      {duty && (
                        <div className={styles.dutiesPill} style={{ color: DUTY_COLORS[duty.status] }}>
                          {duty.staff?.full_name?.split(' ')[0] || '—'}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  function renderAnnouncements() {
    return (
      <div>
        {filtered.map(a => (
          <div key={a.id} className={styles.announcementRow}>
            <div className={styles.announcementTitle}>{a.text.slice(0, 80)}{a.text.length > 80 ? '…' : ''}</div>
            <div className={styles.announcementMeta}>{new Date(a.created_at).toLocaleDateString('ru-RU')}</div>
            {a.read_count !== undefined && (
              <div className={styles.progressBarWrap}>
                <div className={styles.progressBar} style={{ width: `${Math.min(100, (a.read_count / (a.total_staff || 1)) * 100)}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  function renderIncidents() {
    const typeChips = [{ id: '', label: 'Все' }, ...Object.entries(INCIDENT_TYPES).map(([id, label]) => ({ id, label }))];
    return (
      <>
        <div className={styles.filters}>
          {typeChips.map(c => (
            <button key={c.id} className={`${styles.chip} ${incidentType === c.id ? styles.chipActive : ''}`}
              onClick={() => setIncidentType(c.id)}>{c.label}</button>
          ))}
        </div>
        <div>
          {filtered.map(inc => (
            <div key={inc.id} className={styles.incidentRow}>
              <div className={styles.incidentHeader}>
                <span className={styles.incidentBadge}>{INCIDENT_TYPES[inc.type] || inc.type}</span>
                <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                  {new Date(inc.created_at).toLocaleDateString('ru-RU')}
                </span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--color-text)' }}>{inc.description.slice(0, 100)}</div>
              {inc.reporter && <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4 }}>👤 {inc.reporter.full_name}</div>}
            </div>
          ))}
        </div>
      </>
    );
  }

  if (!section) {
    return (
      <div className={styles.page}>
        <div className={styles.header}><span className={styles.headerTitle}>⚙️ Управление</span></div>
        <div className={styles.menuList}>
          {MENU.map(item => (
            <button key={item.id} className={styles.menuRow} onClick={() => loadSection(item.id)}>
              <span className={styles.menuIcon}>{item.icon}</span>
              <span className={styles.menuLabel}>{item.label}</span>
              <span className={styles.menuChevron}>›</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  const current = MENU.find(m => m.id === section);
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={() => setSection(null)}>‹</button>
        <span className={styles.headerTitle}>{current?.icon} {current?.label}</span>
      </div>
      <div className={styles.sectionContent}>
        {loading
          ? <div className={styles.loaderWrap}><div className={styles.loader} /></div>
          : filtered.length === 0 && section !== 'duties'
            ? <div className={styles.emptyState}><span className={styles.emptyIcon}>{current?.icon}</span><span className={styles.emptyTitle}>Нет данных</span></div>
            : section === 'staff' ? renderStaff()
              : section === 'squads' ? renderSquads()
                : section === 'duties' ? renderDuties()
                  : section === 'announcements' ? renderAnnouncements()
                    : section === 'incidents' ? renderIncidents()
                      : null}
      </div>

      {editTarget && (
        <div className={styles.overlay} onClick={() => setEditTarget(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>{editTarget.full_name}</h3>
              <button className={styles.closeBtn} onClick={() => setEditTarget(null)}>✕</button>
            </div>
            <div className={styles.modalBody}>
              <label className={styles.fieldLabel}>Роль
                <select className={styles.fieldSelect} value={editForm.role} onChange={e => setEditForm(f => ({ ...f, role: e.target.value }))}>
                  {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className={styles.fieldLabel}>Отряд
                <select className={styles.fieldSelect} value={editForm.squad_id} onChange={e => setEditForm(f => ({ ...f, squad_id: e.target.value }))}>
                  <option value="">Без отряда</option>
                  {squads.map(s => <option key={s.id} value={s.id}>Отряд {s.name}</option>)}
                </select>
              </label>
              <label className={styles.checkboxLabel}>
                <input type="checkbox" checked={!!editForm.is_active} onChange={e => setEditForm(f => ({ ...f, is_active: e.target.checked }))} />
                Активен
              </label>
              <div className={styles.modalActions}>
                <button className={styles.btnCancel} onClick={() => setEditTarget(null)}>Отмена</button>
                <button className={styles.btnSave} disabled={saving} onClick={saveEdit}>{saving ? '…' : 'Сохранить'}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
