import React, { useCallback, useEffect, useRef, useState } from 'react';
import { childrenApi, squadsApi } from '../../api';
import styles from './ChildrenPage.module.css';

const SPECIAL_FILTERS = [
  { id: 'med', label: '⚠️ Мед', param: { has_allergies: true } },
  { id: 'food', label: '🍽 Питание', param: { has_food_type: true } },
];

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

function ChildModal({ child, onClose }) {
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.sheet} onClick={(e) => e.stopPropagation()}>
        <div className={styles.sheetHandle} />
        <div className={styles.sheetHeader}>
          <h2 className={styles.childName}>{child.full_name}</h2>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.modalContent}>
          <div className={styles.infoRow}>
            <span className={styles.infoIcon}>🏕</span>
            <span className={styles.infoLabel}>Отряд:</span>
            <span className={styles.infoValue}>{child.squad_name || '—'}</span>
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoIcon}>🎂</span>
            <span className={styles.infoLabel}>Дата рождения:</span>
            <span className={styles.infoValue}>{formatDate(child.birth_date)}</span>
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoIcon}>🏠</span>
            <span className={styles.infoLabel}>Адрес:</span>
            <span className={styles.infoValue}>{child.address || '—'}</span>
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoIcon}>🎫</span>
            <span className={styles.infoLabel}>№ путёвки:</span>
            <span className={styles.infoValue}>{child.voucher || '—'}</span>
          </div>

          {child.parents && child.parents.length > 0 && (
            <div className={styles.parentsSection}>
              <h3 className={styles.parentsTitle}>👨‍👩‍👦 Родители</h3>
              {child.parents.map((p) => (
                <div key={p.id} className={styles.parentRow}>
                  <div className={styles.parentInfo}>
                    <span className={styles.parentName}>{p.full_name}</span>
                    {p.relation && (
                      <span className={styles.parentRelation}>{p.relation}</span>
                    )}
                  </div>
                  {p.phone && (
                    <a href={`tel:${p.phone}`} className={styles.phoneBtn}>
                      📞 {p.phone}
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ChildrenPage() {
  const [children, setChildren] = useState([]);
  const [total, setTotal] = useState(0);
  const [squads, setSquads] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [squadFilter, setSquadFilter] = useState(null);
  const [specialFilter, setSpecialFilter] = useState(null); // 'med' | 'food' | null
  const [viewMode, setViewMode] = useState('table');
  const [selectedChild, setSelectedChild] = useState(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [importing, setImporting] = useState(false);
  const [importSquad, setImportSquad] = useState('');
  const [importResult, setImportResult] = useState(null);
  const fileRef = useRef();
  const searchTimeout = useRef();
  const PAGE_SIZE = 20;

  useEffect(() => {
    squadsApi.list().then(setSquads).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (searchQuery) params.search = searchQuery;
      if (squadFilter) params.squad_id = squadFilter;
      const sf = SPECIAL_FILTERS.find(f => f.id === specialFilter);
      if (sf) Object.assign(params, sf.param);
      const data = await childrenApi.list(params);
      setChildren(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, squadFilter, specialFilter, page]);

  useEffect(() => {
    load();
  }, [load]);

  function handleSearchInput(e) {
    const val = e.target.value;
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setPage(1);
      setSearchQuery(val);
    }, 400);
  }

  function handleSquadFilter(id) {
    setPage(1);
    setSquadFilter(id);
  }

  async function handleImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const result = await childrenApi.import(file, importSquad || undefined);
      setImportResult(result);
      load();
    } catch (err) {
      setImportResult({ error: err.message });
    } finally {
      setImporting(false);
      fileRef.current.value = '';
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className={styles.page}>
      {/* Sticky search */}
      <div className={styles.searchWrap}>
        <input
          className={styles.search}
          placeholder="🔍 Поиск по имени..."
          onChange={handleSearchInput}
        />
      </div>

      {/* Filter chips */}
      <div className={styles.filters}>
        <button
          className={`${styles.chip} ${squadFilter === null && !specialFilter ? styles.chipActive : ''}`}
          onClick={() => { handleSquadFilter(null); setSpecialFilter(null); }}
        >
          Все
        </button>
        {squads.map((s) => (
          <button
            key={s.id}
            className={`${styles.chip} ${squadFilter === s.id ? styles.chipActive : ''}`}
            onClick={() => { handleSquadFilter(s.id); setSpecialFilter(null); }}
          >
            Отряд {s.name}
          </button>
        ))}
        {SPECIAL_FILTERS.map(f => (
          <button
            key={f.id}
            className={`${styles.chip} ${specialFilter === f.id ? styles.chipActive : ''}`}
            onClick={() => {
              setSquadFilter(null);
              setPage(1);
              setSpecialFilter(prev => prev === f.id ? null : f.id);
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* View toggle + import */}
      <div className={styles.toolbar}>
        <div className={styles.toggleView}>
          <button
            className={`${styles.toggleBtn} ${viewMode === 'table' ? styles.toggleBtnActive : ''}`}
            onClick={() => setViewMode('table')}
          >
            ☰ Таблица
          </button>
          <button
            className={`${styles.toggleBtn} ${viewMode === 'cards' ? styles.toggleBtnActive : ''}`}
            onClick={() => setViewMode('cards')}
          >
            ⊞ Карточки
          </button>
        </div>
        <div className={styles.importGroup}>
          <select
            className={styles.importSelect}
            value={importSquad}
            onChange={(e) => setImportSquad(e.target.value)}
          >
            <option value="">Отряд из файла</option>
            {squads.map((s) => (
              <option key={s.id} value={s.id}>
                Отряд {s.name}
              </option>
            ))}
          </select>
          <button
            className={styles.importBtn}
            onClick={() => fileRef.current.click()}
            disabled={importing}
          >
            {importing ? '⏳...' : '📊 Импорт'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: 'none' }}
            onChange={handleImport}
          />
        </div>
      </div>

      {/* Import result */}
      {importResult && (
        <div className={importResult.error ? styles.importError : styles.importSuccess}>
          {importResult.error
            ? `❌ ${importResult.error}`
            : `✅ Добавлено: ${importResult.added}, обновлено: ${importResult.updated}`}
          {importResult.warnings?.length > 0 && (
            <div className={styles.importWarnings}>
              {importResult.warnings.slice(0, 3).map((w, i) => (
                <div key={i}>⚠️ {w}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className={styles.loaderWrap}>
          <div className={styles.loader} />
          <span>Загрузка…</span>
        </div>
      ) : children.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>👧</div>
          <div className={styles.emptyTitle}>Дети не найдены</div>
          <div className={styles.emptySubtitle}>Попробуйте изменить фильтр или поисковый запрос</div>
        </div>
      ) : viewMode === 'table' ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Имя</th>
                <th>Отряд</th>
                <th>Корпус</th>
                <th>Питание</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {children.map((c) => (
                <tr
                  key={c.id}
                  className={styles.tableRow}
                  onClick={() => setSelectedChild(c)}
                >
                  <td>{c.full_name}</td>
                  <td>{c.squad_name || '—'}</td>
                  <td>{c.dormitory || '—'}</td>
                  <td>{c.food_type || '—'}</td>
                  <td>{c.allergies ? '⚠️' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className={styles.grid}>
          {children.map((c) => (
            <div
              key={c.id}
              className={styles.childCard}
              onClick={() => setSelectedChild(c)}
            >
              <div className={styles.cardAvatar}>
                {c.full_name
                  ? c.full_name.trim().split(' ').slice(0, 2).map(w => w[0]).join('')
                  : '?'}
              </div>
              <div className={styles.cardInfo}>
                <div className={styles.cardName}>{c.full_name}</div>
                <div className={styles.cardSquad}>
                  {c.squad_name ? `Отряд ${c.squad_name}` : '—'}
                </div>
                {c.allergies && <div className={styles.cardSquad}>⚠️ Аллергия</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageBtn}
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ◀
          </button>
          <span className={styles.pageInfo}>
            {page} / {totalPages}
          </span>
          <button
            className={styles.pageBtn}
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            ▶
          </button>
        </div>
      )}

      {/* Child detail modal */}
      {selectedChild && (
        <ChildModal child={selectedChild} onClose={() => setSelectedChild(null)} />
      )}
    </div>
  );
}
