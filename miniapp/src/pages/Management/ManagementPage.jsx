import React, { useCallback, useEffect, useRef, useState } from 'react';
import { staffApi, squadsApi, dutiesApi, announcementsApi, incidentsApi } from '../../api';
import { ROLE_LABELS, ROLES, DUTY_TYPE_LABELS, DUTY_STATUS_COLORS } from '../../constants';
import styles from './ManagementPage.module.css';

// ─── Staff section ────────────────────────────────────────────────────────────

function StaffSection() {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editTarget, setEditTarget] = useState(null);
  const [squads, setSquads] = useState([]);
  const searchTimeout = useRef();

  useEffect(() => {
    squadsApi.list().then(setSquads).catch(() => {});
    loadStaff();
  }, []); // eslint-disable-next-line

  async function loadStaff() {
    setLoading(true);
    try {
      const data = await staffApi.list();
      setStaff(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function handleSearchInput(e) {
    const val = e.target.value;
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => setSearchQuery(val), 300);
  }

  const filtered = staff.filter(
    (s) =>
      !searchQuery ||
      s.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    return parts.length >= 2
      ? parts[0][0] + parts[1][0]
      : parts[0].substring(0, 2);
  }

  function handleSaved(updated) {
    setStaff((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setEditTarget(null);
  }

  return (
    <div className={styles.sectionContent}>
      <div className={styles.sectionSearch}>
        <input
          className={styles.searchInput}
          placeholder="🔍 Поиск сотрудника..."
          onChange={handleSearchInput}
        />
      </div>

      {loading ? (
        <div className={styles.loaderWrap}>
          <div className={styles.loader} />
          <span>Загрузка…</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>👥</div>
          <div className={styles.emptyTitle}>Сотрудники не найдены</div>
        </div>
      ) : (
        <div className={styles.staffList}>
          {filtered.map((s) => (
            <div
              key={s.id}
              className={`${styles.staffRow} ${!s.is_active ? styles.staffInactive : ''}`}
              onClick={() => setEditTarget(s)}
            >
              <div className={styles.staffAvatar}>
                {getInitials(s.full_name)}
              </div>
              <div className={styles.staffInfo}>
                <div className={styles.staffName}>{s.full_name}</div>
                <div className={styles.staffMeta}>
                  <span className={styles.roleBadge}>
                    {ROLE_LABELS[s.role] ?? s.role}
                  </span>
                  {s.squad?.name && (
                    <span className={styles.squadBadge}>
                      Отряд {s.squad.name}
                    </span>
                  )}
                </div>
              </div>
              <div className={styles.staffStatus}>
                {s.is_active ? '✅' : '❌'}
              </div>
            </div>
          ))}
        </div>
      )}

      {editTarget && (
        <EditStaffModal
          staff={editTarget}
          squads={squads}
          onClose={() => setEditTarget(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

// ─── Edit Staff Modal ─────────────────────────────────────────────────────────

function EditStaffModal({ staff, squads, onClose, onSaved }) {
  const [role, setRole] = useState(staff.role);
  const [squadId, setSquadId] = useState(staff.squad_id ?? '');
  const [isActive, setIsActive] = useState(staff.is_active);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSave() {
    setLoading(true);
    setError(null);
    try {
      const updated = await staffApi.update(staff.id, {
        role,
        squad_id: squadId === '' ? null : Number(squadId),
        is_active: isActive,
      });
      onSaved(updated);
    } catch (e) {
      setError(e.message || 'Ошибка сохранения');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>{staff.full_name}</h2>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.modalBody}>
          <label className={styles.fieldLabel}>
            Роль
            <select
              className={styles.fieldSelect}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.fieldLabel}>
            Отряд
            <select
              className={styles.fieldSelect}
              value={squadId}
              onChange={(e) => setSquadId(e.target.value)}
            >
              <option value="">— Не назначен —</option>
              {squads.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Активен
          </label>

          {error && <p className={styles.errorMsg}>{error}</p>}

          <div className={styles.modalActions}>
            <button className={styles.btnCancel} onClick={onClose} disabled={loading}>
              Отмена
            </button>
            <button className={styles.btnSave} onClick={handleSave} disabled={loading}>
              {loading ? 'Сохранение…' : 'Сохранить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Squads section ───────────────────────────────────────────────────────────

function SquadsSection() {
  const [squads, setSquads] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    squadsApi.list()
      .then(data => setSquads(Array.isArray(data) ? data : data.items || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className={styles.sectionContent}>
      {loading ? (
        <div className={styles.loaderWrap}><div className={styles.loader} /></div>
      ) : squads.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>🏕</div>
          <div className={styles.emptyTitle}>Отряды не найдены</div>
        </div>
      ) : (
        <div className={styles.squadsGrid}>
          {squads.map(s => (
            <div key={s.id} className={styles.squadCard}>
              <div className={styles.squadName}>Отряд {s.name}</div>
              {s.counselor && (
                <div className={styles.squadMeta}>Вожатый: {s.counselor}</div>
              )}
              {s.educator && (
                <div className={styles.squadMeta}>Воспитатель: {s.educator}</div>
              )}
              {s.children_count !== undefined && (
                <div className={styles.squadMeta}>Детей: {s.children_count}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Duties section ───────────────────────────────────────────────────────────

const WEEK_DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function DutiesSection() {
  const [duties, setDuties] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await dutiesApi.list();
      setDuties(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Group duties by type × weekday for a week grid
  const dutyTypes = [...new Set(duties.map(d => d.duty_type || d.type).filter(Boolean))];

  function dutiesForCell(type, dow) {
    return duties.filter(d => {
      const t = d.duty_type || d.type;
      if (t !== type) return false;
      const date = new Date(d.date || d.start_time);
      return (date.getDay() + 6) % 7 === dow;
    });
  }

  function cellColor(status) {
    return DUTY_STATUS_COLORS[status] || '#64748B';
  }

  return (
    <div className={styles.sectionContent}>
      {loading ? (
        <div className={styles.loaderWrap}><div className={styles.loader} /></div>
      ) : duties.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>🔄</div>
          <div className={styles.emptyTitle}>Дежурства не назначены</div>
        </div>
      ) : (
        <div style={{ overflowX: 'auto', padding: '12px 0' }}>
          <table className={styles.dutiesTable}>
            <thead>
              <tr>
                <th className={styles.dutiesTypeCol}>Тип</th>
                {WEEK_DAYS.map(d => <th key={d}>{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {dutyTypes.map(type => (
                <tr key={type}>
                  <td className={styles.dutiesTypeCol}>
                    {DUTY_TYPE_LABELS[type] || type}
                  </td>
                  {WEEK_DAYS.map((_, dow) => {
                    const cell = dutiesForCell(type, dow);
                    return (
                      <td key={dow} className={styles.dutiesCell}>
                        {cell.map(d => (
                          <div
                            key={d.id}
                            className={styles.dutiesPill}
                            style={{ color: cellColor(d.status) }}
                          >
                            {d.staff_name || d.staff?.full_name || '—'}
                          </div>
                        ))}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Announcements section ────────────────────────────────────────────────────

function AnnouncementsSection() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    announcementsApi.list()
      .then(data => setItems(Array.isArray(data) ? data : data.items || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function readPercent(item) {
    if (!item.total_recipients || item.total_recipients === 0) return 0;
    return Math.round((item.read_count || 0) / item.total_recipients * 100);
  }

  return (
    <div className={styles.sectionContent}>
      {loading ? (
        <div className={styles.loaderWrap}><div className={styles.loader} /></div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>📣</div>
          <div className={styles.emptyTitle}>Объявлений нет</div>
        </div>
      ) : (
        <div className={styles.staffList}>
          {items.map(item => {
            const pct = readPercent(item);
            return (
              <div key={item.id} className={styles.announcementRow}>
                <div className={styles.announcementTitle}>{item.title || item.text?.slice(0, 40)}</div>
                <div className={styles.announcementMeta}>
                  {item.created_at && new Date(item.created_at).toLocaleDateString('ru-RU')}
                </div>
                <div className={styles.progressBarWrap}>
                  <div
                    className={styles.progressBar}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className={styles.announcementMeta}>{pct}% прочитано</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Incidents section ────────────────────────────────────────────────────────

const INCIDENT_TYPES = [
  { id: null, label: 'Все' },
  { id: 'medical', label: '🏥 Мед.' },
  { id: 'behavior', label: '⚠️ Поведение' },
  { id: 'property', label: '🔧 Имущество' },
];

const INCIDENT_SEVERITY = {
  low: { label: 'Низкая', color: '#16A34A' },
  medium: { label: 'Средняя', color: '#D97706' },
  high: { label: 'Высокая', color: '#DC2626' },
};

function IncidentsSection() {
  const [items, setItems] = useState([]);
  const [typeFilter, setTypeFilter] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = typeFilter ? { type: typeFilter } : {};
      const data = await incidentsApi.list(params);
      setItems(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [typeFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className={styles.sectionContent}>
      <div className={styles.filters}>
        {INCIDENT_TYPES.map(t => (
          <button
            key={String(t.id)}
            className={`${styles.chip} ${typeFilter === t.id ? styles.chipActive : ''}`}
            onClick={() => setTypeFilter(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {loading ? (
        <div className={styles.loaderWrap}><div className={styles.loader} /></div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>🚨</div>
          <div className={styles.emptyTitle}>Инцидентов нет</div>
        </div>
      ) : (
        <div className={styles.staffList}>
          {items.map(inc => {
            const sev = INCIDENT_SEVERITY[inc.severity] || {};
            return (
              <div key={inc.id} className={styles.incidentRow}>
                <div className={styles.incidentHeader}>
                  <span className={styles.staffName}>{inc.title || inc.description?.slice(0, 40) || '—'}</span>
                  {sev.label && (
                    <span className={styles.incidentBadge} style={{ color: sev.color }}>
                      {sev.label}
                    </span>
                  )}
                </div>
                <div className={styles.staffMeta}>
                  <span className={styles.roleBadge}>{inc.type || '—'}</span>
                  {inc.created_at && (
                    <span className={styles.squadBadge}>
                      {new Date(inc.created_at).toLocaleDateString('ru-RU')}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Analytics section ────────────────────────────────────────────────────────

function AnalyticsSection() {
  return (
    <div className={styles.sectionContent}>
      <div className={styles.placeholder}>
        <div className={styles.emptyIcon}>📊</div>
        <div className={styles.emptyTitle}>Аналитика</div>
        <div className={styles.emptySubtitle}>Данные загружаются из модулей задач, событий и сотрудников</div>
      </div>
    </div>
  );
}

// ─── Section definitions ──────────────────────────────────────────────────────

const SECTIONS = [
  { key: 'staff',         icon: '👥', label: 'Сотрудники'   },
  { key: 'squads',        icon: '🏕',  label: 'Отряды'       },
  { key: 'duties',        icon: '🔄', label: 'Дежурства'    },
  { key: 'announcements', icon: '📣', label: 'Объявления'   },
  { key: 'incidents',     icon: '🚨', label: 'Инциденты'    },
  { key: 'analytics',    icon: '📊', label: 'Аналитика'    },
];

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ManagementPage() {
  const [activeSection, setActiveSection] = useState(null);

  const section = SECTIONS.find((s) => s.key === activeSection);

  function renderSection() {
    if (!activeSection) return null;
    switch (activeSection) {
      case 'staff':         return <StaffSection />;
      case 'squads':        return <SquadsSection />;
      case 'duties':        return <DutiesSection />;
      case 'announcements': return <AnnouncementsSection />;
      case 'incidents':     return <IncidentsSection />;
      case 'analytics':     return <AnalyticsSection />;
      default: return (
        <div className={styles.placeholder}>
          <div className={styles.emptyIcon}>🚧</div>
          <div className={styles.emptyTitle}>В разработке</div>
        </div>
      );
    }
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        {activeSection ? (
          <>
            <button
              className={styles.backBtn}
              onClick={() => setActiveSection(null)}
            >
              ←
            </button>
            <span className={styles.headerTitle}>
              {section?.icon} {section?.label}
            </span>
          </>
        ) : (
          <span className={styles.headerTitle}>Управление</span>
        )}
      </div>

      {/* Content */}
      {activeSection ? (
        renderSection()
      ) : (
        <div className={styles.menuList}>
          {SECTIONS.map((s) => (
            <button
              key={s.key}
              className={styles.menuRow}
              onClick={() => setActiveSection(s.key)}
            >
              <span className={styles.menuIcon}>{s.icon}</span>
              <span className={styles.menuLabel}>{s.label}</span>
              <span className={styles.menuChevron}>›</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
