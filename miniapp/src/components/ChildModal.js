import React from "react";
import styles from "./ChildModal.module.css";

export default function ChildModal({ child, onClose }) {
  const bd = child.birth_date || "—";
  const squad = child.squad_name || "—";

  function sendToBot() {
    if (window.Telegram?.WebApp?.sendData) {
      window.Telegram.WebApp.sendData(
        JSON.stringify({ action: "child_card", child_id: child.id })
      );
    }
  }

  const hasTg = !!window.Telegram?.WebApp?.sendData;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.name}>{child.full_name}</h2>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.body}>
          <div className={styles.section}>
            <Row label="Дата рождения" value={bd} />
            <Row label="Отряд" value={squad} />
            <Row label="№ путёвки" value={child.voucher} />
            <Row label="Адрес" value={child.address} />
          </div>

          {child.parents?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>👨‍👩‍👦 Родители</h3>
              {child.parents.map(p => (
                <div key={p.id} className={styles.parent}>
                  <span className={styles.parentName}>{p.full_name}</span>
                  {p.relation && <span className={styles.parentRel}> ({p.relation})</span>}
                  {p.phone && (
                    <a href={`tel:${p.phone}`} className={styles.phone}>{p.phone}</a>
                  )}
                </div>
              ))}
            </div>
          )}

          {hasTg && (
            <button className={styles.sendBtn} onClick={sendToBot}>
              📨 Отправить карточку в бот
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}:</span>
      <span className={styles.value}>{value || "—"}</span>
    </div>
  );
}
