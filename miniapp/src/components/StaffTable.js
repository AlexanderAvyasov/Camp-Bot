import React from "react";
import { ROLE_LABELS } from "../constants";
import styles from "./StaffTable.module.css";

export default function StaffTable({ staff, onEdit }) {
  if (!staff.length) return <p style={{ padding: "16px" }}>Нет данных.</p>;

  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>ФИО</th>
            <th>Роль</th>
            <th>Отряд</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {staff.map((s) => (
            <tr key={s.id} className={!s.is_active ? styles.inactive : ""}>
              <td>{s.full_name}</td>
              <td>{ROLE_LABELS[s.role] ?? s.role}</td>
              <td>{s.squad?.name ?? "—"}</td>
              <td>{s.is_active ? "✅" : "❌"}</td>
              <td>
                <button className={styles.editBtn} onClick={() => onEdit(s)}>
                  Изменить
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
