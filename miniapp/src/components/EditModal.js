import React, { useState } from "react";
import { staffApi } from "../api";
import { ROLE_LABELS, ROLES } from "../constants";
import styles from "./EditModal.module.css";

export default function EditModal({ staff, squads, onClose, onSaved }) {
  const [role, setRole] = useState(staff.role);
  const [squadId, setSquadId] = useState(staff.squad_id ?? "");
  const [isActive, setIsActive] = useState(staff.is_active);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSave() {
    setLoading(true);
    setError(null);
    try {
      const updated = await staffApi.update(staff.id, {
        role,
        squad_id: squadId === "" ? null : Number(squadId),
        is_active: isActive,
      });
      onSaved(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.title}>{staff.full_name}</h2>

        <label className={styles.label}>
          Роль
          <select className={styles.select} value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
        </label>

        <label className={styles.label}>
          Отряд
          <select
            className={styles.select}
            value={squadId}
            onChange={(e) => setSquadId(e.target.value)}
          >
            <option value="">— Не назначен —</option>
            {squads.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
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

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.actions}>
          <button className={styles.btnCancel} onClick={onClose} disabled={loading}>
            Отмена
          </button>
          <button className={styles.btnSave} onClick={handleSave} disabled={loading}>
            {loading ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}
