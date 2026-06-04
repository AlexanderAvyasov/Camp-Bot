import React, { useCallback, useEffect, useState } from "react";
import { eventsApi } from "../api";
import EventModal from "./EventModal";
import styles from "./CalendarPage.module.css";

const DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const MONTHS = [
  "Январь","Февраль","Март","Апрель","Май","Июнь",
  "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь",
];

function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function daysInMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
}

// Monday-first day-of-week index
function dowMon(date) {
  return (date.getDay() + 6) % 7;
}

export default function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [creating, setCreating] = useState(null); // date string for new event
  const [loading, setLoading] = useState(false);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await eventsApi.list();
      setEvents(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  function eventsForDay(day) {
    return events.filter(ev => {
      const start = new Date(ev.start_time);
      return isSameDay(start, day);
    });
  }

  function buildCalendarDays() {
    const first = startOfMonth(currentMonth);
    const totalDays = daysInMonth(currentMonth);
    const startDow = dowMon(first);
    const days = [];
    for (let i = 0; i < startDow; i++) days.push(null);
    for (let d = 1; d <= totalDays; d++) {
      days.push(new Date(currentMonth.getFullYear(), currentMonth.getMonth(), d));
    }
    return days;
  }

  function prevMonth() {
    setCurrentMonth(m => new Date(m.getFullYear(), m.getMonth() - 1, 1));
  }
  function nextMonth() {
    setCurrentMonth(m => new Date(m.getFullYear(), m.getMonth() + 1, 1));
  }

  const today = new Date();
  const calDays = buildCalendarDays();

  return (
    <div className={styles.calendar}>
      <div className={styles.header}>
        <button onClick={prevMonth}>‹</button>
        <span className={styles.monthTitle}>
          {MONTHS[currentMonth.getMonth()]} {currentMonth.getFullYear()}
        </span>
        <button onClick={nextMonth}>›</button>
        <button className={styles.refreshBtn} onClick={loadEvents} disabled={loading}>↻</button>
      </div>

      <div className={styles.grid}>
        {DAYS.map(d => (
          <div key={d} className={styles.dayName}>{d}</div>
        ))}
        {calDays.map((day, i) => {
          if (!day) return <div key={`empty-${i}`} className={styles.emptyCell} />;
          const dayEvents = eventsForDay(day);
          const isToday = isSameDay(day, today);
          return (
            <div
              key={day.toISOString()}
              className={`${styles.dayCell} ${isToday ? styles.today : ""}`}
              onClick={() => setCreating(day.toISOString().slice(0, 10))}
            >
              <span className={styles.dayNum}>{day.getDate()}</span>
              {dayEvents.slice(0, 3).map(ev => (
                <div
                  key={ev.id}
                  className={styles.eventChip}
                  style={{ background: ev.color || "#888" }}
                  onClick={e => { e.stopPropagation(); setSelectedEvent(ev); }}
                >
                  {ev.start_time.slice(11, 16)} {ev.title}
                </div>
              ))}
              {dayEvents.length > 3 && (
                <div className={styles.moreChip}>+{dayEvents.length - 3}</div>
              )}
            </div>
          );
        })}
      </div>

      {selectedEvent && (
        <EventModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
          onSaved={() => { setSelectedEvent(null); loadEvents(); }}
          onDeleted={() => { setSelectedEvent(null); loadEvents(); }}
        />
      )}

      {creating && !selectedEvent && (
        <EventModal
          defaultDate={creating}
          onClose={() => setCreating(null)}
          onSaved={() => { setCreating(null); loadEvents(); }}
        />
      )}
    </div>
  );
}
