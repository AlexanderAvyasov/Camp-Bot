import React, { useCallback, useEffect, useState } from "react";
import { staffApi } from "./api";
import EditModal from "./components/EditModal";
import StaffTable from "./components/StaffTable";
import CalendarPage from "./components/CalendarPage";
import styles from "./App.module.css";

const TABS = [
  { id: "staff", label: "👥 Сотрудники" },
  { id: "calendar", label: "🗓 Календарь" },
];

export default function App() {
  const [tab, setTab] = useState("staff");
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
      <nav className={styles.tabs}>
        {TABS.map(t => (
          <button
            key={t.id}
            className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "staff" && (
        <>
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
        </>
      )}

      {tab === "calendar" && <CalendarPage />}
    </div>
  );
}
