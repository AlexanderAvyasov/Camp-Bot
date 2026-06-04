import React, { useCallback, useEffect, useState } from 'react';
import { eventsApi } from '../../api';
import EventModal from '../../components/EventModal';
import styles from './CalendarPage.module.css';

const DAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const EVENT_COLORS = { sport: '#4CAF50', creative: '#FF9800', camp_wide: '#2196F3', squad: '#9C27B0' };
const HOUR_HEIGHT = 48;
const DAY_START = 8;
const DAY_END = 22;

function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
function dowMon(d) { return (d.getDay() + 6) % 7; }
function fmtTime(iso) { return iso ? iso.slice(11, 16) : ''; }
function fmtDate(d) { return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }); }

function getWeekDays(base) {
  const mon = new Date(base);
  mon.setDate(base.getDate() - dowMon(base));
  return Array.from({ length: 7 }, (_, i) => { const d = new Date(mon); d.setDate(mon.getDate() + i); return d; });
}

export default function CalendarPage({ staff }) {
  const [view, setView] = useState('month');
  const [current, setCurrent] = useState(new Date());
  const [selected, setSelected] = useState(new Date());
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [openEvent, setOpenEvent] = useState(null);
  const [creating, setCreating] = useState(null);

  const isAdmin = staff?.role === 'admin' || staff?.role === 'senior_counselor';

  const load = useCallback(async () => {
    setLoading(true);
    try { setEvents((await eventsApi.list()) || []); } catch (e) { console.error(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  function eventsForDay(day) {
    return events.filter(e => isSameDay(new Date(e.start_time), day)).sort((a, b) => a.start_time.localeCompare(b.start_time));
  }

  function renderMonth() {
    const first = new Date(current.getFullYear(), current.getMonth(), 1);
    const total = new Date(current.getFullYear(), current.getMonth() + 1, 0).getDate();
    const startDow = dowMon(first);
    const cells = [];
    for (let i = 0; i < startDow; i++) cells.push(null);
    for (let d = 1; d <= total; d++) cells.push(new Date(current.getFullYear(), current.getMonth(), d));
    const today = new Date();
    return (
      <div className={styles.monthGrid}>
        {DAYS_SHORT.map(d => <div key={d} className={styles.dayName}>{d}</div>)}
        {cells.map((day, i) => {
          if (!day) return <div key={`e${i}`} className={styles.emptyCell} />;
          const evs = eventsForDay(day);
          const isToday = isSameDay(day, today);
          const isSel = isSameDay(day, selected);
          return (
            <div key={day.toISOString()} className={`${styles.dayCell} ${isToday ? styles.todayCell : ''} ${isSel ? styles.selectedCell : ''}`}
              onClick={() => { setSelected(day); if (view !== 'month') return; }}>
              <span className={styles.dayNum}>{day.getDate()}</span>
              {evs.slice(0, 2).map(ev => (
                <div key={ev.id} className={styles.eventChip} style={{ background: EVENT_COLORS[ev.type] || '#888' }}
                  onClick={e => { e.stopPropagation(); setOpenEvent(ev); }}>
                  {fmtTime(ev.start_time)} {ev.title}
                </div>
              ))}
              {evs.length > 2 && <div className={styles.moreChip}>+{evs.length - 2}</div>}
            </div>
          );
        })}
      </div>
    );
  }

  function renderWeekStrip() {
    const days = getWeekDays(current);
    const today = new Date();
    return (
      <div className={styles.weekRow}>
        {days.map(day => {
          const evs = eventsForDay(day);
          const isToday = isSameDay(day, today);
          const isSel = isSameDay(day, selected);
          return (
            <button key={day.toISOString()} onClick={() => setSelected(day)}
              className={`${styles.weekDay} ${isToday ? styles.todayWeekDay : ''} ${isSel ? styles.selectedWeekDay : ''}`}>
              <span className={styles.weekDayName}>{DAYS_SHORT[dowMon(day)]}</span>
              <span className={styles.weekDayNum}>{day.getDate()}</span>
              {evs.length > 0 && <span className={styles.weekDot} />}
            </button>
          );
        })}
      </div>
    );
  }

  function renderDayPanel(day) {
    const evs = eventsForDay(day);
    return (
      <div className={styles.dayPanel}>
        <div className={styles.dayPanelTitle}>{fmtDate(day)}</div>
        {evs.length === 0
          ? <div className={styles.emptyState}><span className={styles.emptyStateIcon}>📅</span><span className={styles.emptyStateTitle}>Нет мероприятий</span></div>
          : <div className={styles.eventList}>{evs.map(ev => (
            <div key={ev.id} className={styles.eventCard} onClick={() => setOpenEvent(ev)}>
              <div className={styles.eventCardHeader}>
                <span className={styles.eventColorDot} style={{ background: EVENT_COLORS[ev.type] || '#888' }} />
                <span className={styles.eventCardTime}>{fmtTime(ev.start_time)} – {fmtTime(ev.end_time)}</span>
              </div>
              <div className={styles.eventCardTitle}>{ev.title}</div>
              {ev.location && <div className={styles.eventCardLoc}>📍 {ev.location}</div>}
            </div>
          ))}</div>}
        {isAdmin && (
          <button className={styles.fab} onClick={() => setCreating(day.toISOString().slice(0, 10))}>＋</button>
        )}
      </div>
    );
  }

  function renderTimeGrid(days) {
    const hours = Array.from({ length: DAY_END - DAY_START }, (_, i) => DAY_START + i);
    const totalHeight = hours.length * HOUR_HEIGHT;
    function evStyle(ev) {
      const start = new Date(ev.start_time);
      const end = new Date(ev.end_time);
      const startH = start.getHours() + start.getMinutes() / 60 - DAY_START;
      const endH = end.getHours() + end.getMinutes() / 60 - DAY_START;
      const top = Math.max(0, startH * HOUR_HEIGHT);
      const height = Math.max(18, (endH - startH) * HOUR_HEIGHT);
      return { top, height };
    }
    return (
      <div className={styles.timeGrid}>
        <div className={styles.timeAxis}>
          {hours.map(h => <div key={h} className={styles.timeLabel} style={{ height: HOUR_HEIGHT }}>{h}:00</div>)}
        </div>
        {days.length > 1
          ? <div className={styles.weekColumns}>
            {days.map(day => (
              <div key={day.toISOString()} className={styles.weekColumn} style={{ minHeight: totalHeight }}>
                {Array.from({ length: hours.length }, (_, i) => (
                  <div key={i} className={styles.hourCell} style={{ height: HOUR_HEIGHT }} />
                ))}
                {eventsForDay(day).map(ev => {
                  const { top, height } = evStyle(ev);
                  return (
                    <div key={ev.id} className={styles.timeEventBlock}
                      style={{ top, height, background: EVENT_COLORS[ev.type] || '#888' }}
                      onClick={() => setOpenEvent(ev)}>
                      <span className={styles.timeEventTitle}>{ev.title}</span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          : <div className={styles.dayColumn} style={{ minHeight: totalHeight }}>
            {Array.from({ length: hours.length }, (_, i) => <div key={i} className={styles.hourCell} style={{ height: HOUR_HEIGHT }} />)}
            {eventsForDay(days[0]).map(ev => {
              const { top, height } = evStyle(ev);
              return (
                <div key={ev.id} className={styles.dayEventBlock}
                  style={{ top, height, background: EVENT_COLORS[ev.type] || '#888' }}
                  onClick={() => setOpenEvent(ev)}>
                  <span className={styles.dayEventTime}>{fmtTime(ev.start_time)}</span>
                  <span className={styles.dayEventTitle}>{ev.title}</span>
                  {ev.location && <span className={styles.dayEventLoc}>📍 {ev.location}</span>}
                </div>
              );
            })}
          </div>}
      </div>
    );
  }

  const navTitle = view === 'month'
    ? `${MONTHS[current.getMonth()]} ${current.getFullYear()}`
    : view === 'week'
      ? `Неделя ${current.getDate()} ${MONTHS[current.getMonth()]}`
      : fmtDate(selected);

  function prev() {
    if (view === 'month') setCurrent(m => new Date(m.getFullYear(), m.getMonth() - 1, 1));
    else if (view === 'week') { const d = new Date(current); d.setDate(d.getDate() - 7); setCurrent(d); }
    else { const d = new Date(selected); d.setDate(d.getDate() - 1); setSelected(d); setCurrent(d); }
  }
  function next() {
    if (view === 'month') setCurrent(m => new Date(m.getFullYear(), m.getMonth() + 1, 1));
    else if (view === 'week') { const d = new Date(current); d.setDate(d.getDate() + 7); setCurrent(d); }
    else { const d = new Date(selected); d.setDate(d.getDate() + 1); setSelected(d); setCurrent(d); }
  }

  return (
    <div className={styles.page}>
      <div className={styles.viewSwitch}>
        {['month', 'week', 'day'].map(v => (
          <button key={v} className={`${styles.switchBtn} ${view === v ? styles.switchActive : ''}`} onClick={() => setView(v)}>
            {v === 'month' ? 'Месяц' : v === 'week' ? 'Неделя' : 'День'}
          </button>
        ))}
      </div>
      <div className={styles.navHeader}>
        <button className={styles.navBtn} onClick={prev}>‹</button>
        <span className={styles.navTitle}>{navTitle}</span>
        <button className={styles.navBtn} onClick={next}>›</button>
        <button className={styles.refreshBtn} onClick={load} disabled={loading}>↻</button>
      </div>

      {loading && <div className={styles.loaderWrap}><div className={styles.loader} /></div>}

      {!loading && view === 'month' && (
        <>
          {renderMonth()}
          {renderDayPanel(selected)}
        </>
      )}
      {!loading && view === 'week' && (
        <>
          {renderWeekStrip()}
          {renderTimeGrid(getWeekDays(current))}
        </>
      )}
      {!loading && view === 'day' && renderTimeGrid([selected])}

      {openEvent && (
        <EventModal event={openEvent} onClose={() => setOpenEvent(null)}
          onSaved={() => { setOpenEvent(null); load(); }} onDeleted={() => { setOpenEvent(null); load(); }} />
      )}
      {creating && (
        <EventModal defaultDate={creating} onClose={() => setCreating(null)}
          onSaved={() => { setCreating(null); load(); }} />
      )}
    </div>
  );
}
