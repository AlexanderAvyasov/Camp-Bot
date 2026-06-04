import React, { useCallback, useEffect, useState } from "react";
import { staffApi } from "./api";
import EditModal from "./components/EditModal";
import StaffTable from "./components/StaffTable";
import styles from "./App.module.css";

export default function App() {
  const [staff, setStaff] = useState([]);
  const [squads, setSquads] = useState([]);
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadStaff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await staffApi.list();
      setStaff(data);
      // Deduplicate squads from staff data
      const squadMap = new Map();
      data.forEach((s) => {
        if (s.squad) squadMap.set(s.squad.id, s.squad);
      });
      setSquads([...squadMap.values()]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStaff(); }, [loadStaff]);

  function handleSaved(updated) {
    setStaff((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setEditing(null);
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Сотрудники лагеря</h1>
        <button className={styles.refreshBtn} onClick={loadStaff} disabled={loading}>
          {loading ? "…" : "↻"}
        </button>
      </header>

      {error && <p className={styles.error}>Ошибка: {error}</p>}

      {loading ? (
        <p className={styles.loading}>Загрузка…</p>
      ) : (
        <StaffTable staff={staff} onEdit={setEditing} />
      )}

      {editing && (
        <EditModal
          staff={editing}
          squads={squads}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
