import React, { useCallback, useEffect, useRef, useState } from "react";
import { childrenApi, squadsApi } from "../api";
import ChildModal from "./ChildModal";
import styles from "./ChildrenPage.module.css";

export default function ChildrenPage() {
  const [children, setChildren] = useState([]);
  const [total, setTotal] = useState(0);
  const [squads, setSquads] = useState([]);
  const [squadFilter, setSquadFilter] = useState("");
  const [importSquad, setImportSquad] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef();
  const PAGE_SIZE = 20;

  useEffect(() => {
    squadsApi.list().then(setSquads).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await childrenApi.list({
        search: search || undefined,
        squad_id: squadFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setChildren(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [search, squadFilter, page]);

  useEffect(() => { load(); }, [load]);

  const searchTimeout = useRef();
  function handleSearch(e) {
    const val = e.target.value;
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setPage(1);
      setSearch(val);
    }, 400);
  }

  function handleSquadFilter(e) {
    setPage(1);
    setSquadFilter(e.target.value);
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
      fileRef.current.value = "";
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <input
          className={styles.search}
          placeholder="🔍 Поиск по имени..."
          onChange={handleSearch}
        />
        <select className={styles.squadSelect} value={squadFilter} onChange={handleSquadFilter}>
          <option value="">Все отряды</option>
          {squads.map(s => (
            <option key={s.id} value={s.id}>Отряд {s.name}</option>
          ))}
        </select>
      </div>

      <div className={styles.importBar}>
        <select
          className={styles.squadSelect}
          value={importSquad}
          onChange={e => setImportSquad(e.target.value)}
        >
          <option value="">Отряд из файла</option>
          {squads.map(s => (
            <option key={s.id} value={s.id}>Отряд {s.name}</option>
          ))}
        </select>
        <button
          className={styles.importBtn}
          onClick={() => fileRef.current.click()}
          disabled={importing}
        >
          {importing ? "⏳..." : "📊 Импорт Excel"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: "none" }}
          onChange={handleImport}
        />
      </div>

      {importResult && (
        <div className={importResult.error ? styles.importError : styles.importSuccess}>
          {importResult.error
            ? `❌ ${importResult.error}`
            : `✅ Добавлено: ${importResult.added}, обновлено: ${importResult.updated}`}
          {importResult.warnings?.length > 0 && (
            <div className={styles.importWarnings}>
              {importResult.warnings.slice(0, 3).map((w, i) => <div key={i}>⚠️ {w}</div>)}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <p className={styles.loading}>Загрузка…</p>
      ) : children.length === 0 ? (
        <p className={styles.empty}>Ничего не найдено.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Имя</th>
              <th>Отряд</th>
              <th>№ пут.</th>
              <th>Адрес</th>
            </tr>
          </thead>
          <tbody>
            {children.map(c => (
              <tr key={c.id} className={styles.row} onClick={() => setSelected(c)}>
                <td>{c.full_name}</td>
                <td>{c.squad_name || "—"}</td>
                <td>{c.voucher || "—"}</td>
                <td>{c.address || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>◀️</button>
          <span>{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>▶️</button>
        </div>
      )}

      {selected && (
        <ChildModal
          child={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
