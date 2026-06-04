import React, { useState } from "react";
import { eventsApi } from "../api";
import styles from "./EventModal.module.css";

const EVENT_TYPES = [
  { value: "sport", label: "🏃 Спорт", color: "#4CAF50" },
  { value: "creative", label: "🎨 Творчество", color: "#FF9800" },
  { value: "camp_wide", label: "🏕 Общелагерное", color: "#2196F3" },
  { value: "squad", label: "👥 Отрядное", color: "#9C27B0" },
];

function fmt(dt) {
  if (!dt) return "";
  return new Date(dt).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function toInputDt(isoOrNull) {
  if (!isoOrNull) return "";
  return isoOrNull.slice(0, 16);
}

export default function EventModal({ event, defaultDate, onClose, onSaved, onDeleted }) {
  const isNew = !event;
  const defaultStart = defaultDate ? `${defaultDate}T09:00` : "";

  const [form, setForm] = useState({
    title: event?.title || "",
    type: event?.type || "camp_wide",
    location: event?.location || "",
    start_time: isNew ? defaultStart : toInputDt(event?.start_time),
    end_time: isNew ? (defaultDate ? `${defaultDate}T10:00` : "") : toInputDt(event?.end_time),
    responsible_id: event?.responsible_id || "",
    member_ids: [],
  });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [warnings, setWarnings] = useState([]);
  const [error, setError] = useState(null);

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSave() {
    if (!form.title || !form.start_time || !form.end_time) {
      setError("Заполните название, начало и конец.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        responsible_id: form.responsible_id ? Number(form.responsible_id) : null,
        member_ids: form.member_ids,
      };
      if (isNew) {
        const result = await eventsApi.create(payload);
        if (result.warnings?.length) {
          setWarnings(result.warnings);
        }
        onSaved(result.event);
      } else {
        const updated = await eventsApi.update(event.id, payload);
        onSaved(updated);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Удалить мероприятие?")) return;
    setDeleting(true);
    try {
      await eventsApi.delete(event.id);
      onDeleted();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  }

  const typeInfo = EVENT_TYPES.find(t => t.value === (isNew ? form.type : event?.type));

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.colorBar} style={{ background: typeInfo?.color }} />

        <div className={styles.body}>
          <div className={styles.titleRow}>
            <h2 className={styles.title}>{isNew ? "Новое мероприятие" : event.title}</h2>
            <button className={styles.closeBtn} onClick={onClose}>✕</button>
          </div>

          {!isNew && (
            <div className={styles.viewSection}>
              <p><b>Тип:</b> {typeInfo?.label}</p>
              <p><b>Место:</b> {event.location || "—"}</p>
              <p><b>Начало:</b> {fmt(event.start_time)}</p>
              <p><b>Конец:</b> {fmt(event.end_time)}</p>
              <p><b>Участников:</b> {event.members?.length ?? 0}</p>
            </div>
          )}

          <div className={styles.formSection}>
            <label>Название
              <input name="title" value={form.title} onChange={handleChange} className={styles.input} />
            </label>
            <label>Тип
              <select name="type" value={form.type} onChange={handleChange} className={styles.input}>
                {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label>Место
              <input name="location" value={form.location} onChange={handleChange} className={styles.input} />
            </label>
            <div className={styles.row}>
              <label>Начало
                <input type="datetime-local" name="start_time" value={form.start_time} onChange={handleChange} className={styles.input} />
              </label>
              <label>Конец
                <input type="datetime-local" name="end_time" value={form.end_time} onChange={handleChange} className={styles.input} />
              </label>
            </div>
            <label>ID ответственного
              <input name="responsible_id" value={form.responsible_id} onChange={handleChange} className={styles.input} placeholder="необязательно" />
            </label>
          </div>

          {warnings.length > 0 && (
            <div className={styles.warnings}>
              {warnings.map((w, i) => (
                <p key={i}>⚠️ Конфликт {w.type === "location" ? "места" : "ответственного"}: {w.events.join(", ")}</p>
              ))}
            </div>
          )}
          {error && <p className={styles.error}>{error}</p>}

          <div className={styles.actions}>
            <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
              {saving ? "…" : isNew ? "Создать" : "Сохранить"}
            </button>
            {!isNew && (
              <button className={styles.deleteBtn} onClick={handleDelete} disabled={deleting}>
                {deleting ? "…" : "Удалить"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
