import React, { useCallback, useEffect, useRef, useState } from 'react';
import { childrenApi, squadsApi } from '../../api';
import ChildModal from '../../components/ChildModal';
import styles from './ChildrenPage.module.css';

const PAGE_SIZE = 20;

function initials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] || '') + (parts[1]?.[0] || '');
}

export default function ChildrenPage({ staff }) {
  const [children, setChildren] = useState([]);
  const [total, setTotal] = useState(0);
  const [squads, setSquads] = useState([]);
  const [search, setSearch] = useState('');
  const [squadFilter, setSquadFilter] = useState('');
  const [medFilter, setMedFilter] = useState(false);
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState('table');
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef();
  const [importSquad, setImportSquad] = useState('');
  const searchRef = useRef();

  const isAdmin = staff?.role === 'admin' || staff?.role === 'senior_counselor';

  useEffect(() => { squadsApi.list().then(setSquads).catch(() => {}); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (search) params.search = search;
      if (squadFilter) params.squad_id = squadFilter;
      if (medFilter) params.has_allergies = true;
      const data = await childrenApi.list(params);
      setChildren(data.items || data || []);
      setTotal(data.total || (data.items ? data.total : (data || []).length) || 0);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [search, squadFilter, medFilter, page]);

  useEffect(() => { load(); }, [load]);

  const searchTimer = useRef();
  function handleSearch(e) {
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setPage(1); setSearch(e.target.value); }, 400);
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
      setImportResult({ error: 'Ошибка импорта' });
    } finally {
      setImporting(false);
      fileRef.current.value = '';
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const filterChips = [
    { id: '', label: 'Все' },
    ...squads.map(s => ({ id: String(s.id), label: `Отряд ${s.name}` })),
    { id: '__med', label: '⚠️ Мед.' },
  ];

  function handleChip(id) {
    setPage(1);
    if (id === '__med') { setMedFilter(m => !m); setSquadFilter(''); }
    else { setSquadFilter(id); setMedFilter(false); }
  }

  const activeChip = medFilter ? '__med' : squadFilter;

  return (
    <div className={styles.page}>
      <div className={styles.searchWrap}>
        <input ref={searchRef} className={styles.search} placeholder="🔍 Поиск по имени…" onChange={handleSearch} />
      </div>

      <div className={styles.filters}>
        {filterChips.map(c => (
          <button key={c.id} className={`${styles.chip} ${activeChip === c.id ? styles.chipActive : ''}`}
            onClick={() => handleChip(c.id)}>{c.label}</button>
        ))}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.toggleView}>
          <button className={`${styles.toggleBtn} ${viewMode === 'table' ? styles.toggleBtnActive : ''}`} onClick={() => setViewMode('table')}>📋</button>
          <button className={`${styles.toggleBtn} ${viewMode === 'cards' ? styles.toggleBtnActive : ''}`} onClick={() => setViewMode('cards')}>🃏</button>
        </div>
        {isAdmin && (
          <div className={styles.importGroup}>
            <select className={styles.importSelect} value={importSquad} onChange={e => setImportSquad(e.target.value)}>
              <option value="">Отряд из файла</option>
              {squads.map(s => <option key={s.id} value={s.id}>Отряд {s.name}</option>)}
            </select>
            <button className={styles.importBtn} disabled={importing} onClick={() => fileRef.current.click()}>
              {importing ? '⏳…' : '📊 Excel'}
            </button>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ display: 'none' }} onChange={handleImport} />
          </div>
        )}
      </div>

      {importResult && (
        <div className={importResult.error ? styles.importError : styles.importSuccess}>
          {importResult.error ? `❌ ${importResult.error}` : `✅ Добавлено: ${importResult.added ?? 0}, обновлено: ${importResult.updated ?? 0}`}
          {importResult.warnings?.slice(0, 3).map((w, i) => <div key={i} className={styles.importWarnings}>⚠️ {w}</div>)}
        </div>
      )}

      {loading ? (
        <div className={styles.loaderWrap}><div className={styles.loader} /></div>
      ) : children.length === 0 ? (
        <div className={styles.emptyState}>
          <span className={styles.emptyIcon}>👦</span>
          <span className={styles.emptyTitle}>Ничего не найдено</span>
          <span className={styles.emptySubtitle}>Попробуйте изменить фильтры</span>
        </div>
      ) : viewMode === 'table' ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Имя</th><th>Отряд</th><th>Корпус</th><th>Питание</th><th></th>
              </tr>
            </thead>
            <tbody>
              {children.map(c => (
                <tr key={c.id} className={styles.tableRow} onClick={() => setSelected(c)}>
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
          {children.map(c => (
            <div key={c.id} className={styles.childCard} onClick={() => setSelected(c)}>
              <div className={styles.cardAvatar}>{initials(c.full_name).toUpperCase()}</div>
              <div className={styles.cardInfo}>
                <div className={styles.cardName}>{c.full_name.split(' ').slice(0, 2).join(' ')}</div>
                <div className={styles.cardSquad}>{c.squad_name ? `Отряд ${c.squad_name}` : '—'}{c.allergies ? ' ⚠️' : ''}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button className={styles.pageBtn} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>◀</button>
          <span className={styles.pageInfo}>{page} / {totalPages}</span>
          <button className={styles.pageBtn} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>▶</button>
        </div>
      )}

      {selected && <ChildModal child={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
