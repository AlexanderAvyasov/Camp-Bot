import React, { useCallback, useEffect, useState } from 'react';
import { eventsApi } from '../../api';
import { EVENT_TYPE_COLORS } from '../../constants';
import EventModal from '../../components/EventModal';
import styles from './CalendarPage.module.css';

const DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];
const HOURS = Array.from({ length: 15 }, (_, i) => i + 8); // 08–22
const HOUR_HEIGHT = 56; // px per hour

function isSameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function startOfWeek(date) {
  const d = new Date(date);
  const dow = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dow);
  d.setHours(0, 0, 0, 0);
  return d;
}

function daysInMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
}

function dowMon(date) {
  return (date.getDay() + 6) % 7;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

function eventColor(ev) {
  return ev.color || EVENT_TYPE_COLORS[ev.type] || '#888';
}

function toDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function eventTopPx(ev) {
  const d = new Date(ev.start_time);
  return ((d.getHours() - 8) * 60 + d.getMinutes()) / 60 * HOUR_HEIGHT;
}

function eventHeightPx(ev) {
  if (!ev.end_time) return HOUR_HEIGHT;
  const s = new Date(ev.start_time);
  const e = new Date(ev.end_time);
  return Math.max(24, (e - s) / 3600000 * HOUR_HEIGHT);
}

export default function CalendarPage() {
  const [view, setView] = useState('month');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [creatingDate, setCreatingDate] = useState(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await eventsApi.list();
      setEvents(Array.isArray(data) ? data : (data.items || []));
    } catch (e) {
      console.error(e);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  useEffect(() => {
    if (view !== 'month' && !selectedDay) setSelectedDay(new Date());
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  function eventsForDay(day) {
    return events.filter(ev => isSameDay(new Date(ev.start_time), day));
  }

  function buildMonthDays() {
    const first = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const total = daysInMonth(currentDate);
    const startDow = dowMon(first);
    const days = [];
    for (let i = 0; i < startDow; i++) days.push(null);
    for (let d = 1; d <= total; d++) {
      days.push(new Date(currentDate.getFullYear(), currentDate.getMonth(), d));
    }
    return days;
  }

  function buildWeekDays() {
    const mon = startOfWeek(currentDate);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(mon);
      d.setDate(mon.getDate() + i);
      return d;
    });
  }

  function prevPeriod() {
    if (view === 'month') {
      setCurrentDate(d => new Date(d.getFullYear(), d.getMonth() - 1, 1));
      setSelectedDay(null);
    } else if (view === 'week') {
      setCurrentDate(d => { const n = new Date(d); n.setDate(n.getDate() - 7); return n; });
      setSelectedDay(null);
    } else {
      setSelectedDay(prev => {
        const n = new Date(prev || currentDate);
        n.setDate(n.getDate() - 1);
        setCurrentDate(new Date(n));
        return n;
      });
    }
  }

  function nextPeriod() {
    if (view === 'month') {
      setCurrentDate(d => new Date(d.getFullYear(), d.getMonth() + 1, 1));
      setSelectedDay(null);
    } else if (view === 'week') {
      setCurrentDate(d => { const n = new Date(d); n.setDate(n.getDate() + 7); return n; });
      setSelectedDay(null);
    } else {
      setSelectedDay(prev => {
        const n = new Date(prev || currentDate);
        n.setDate(n.getDate() + 1);
        setCurrentDate(new Date(n));
        return n;
      });
    }
  }

  function navTitle() {
    if (view === 'month') {
      return `${MONTHS[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
    }
    if (view === 'week') {
      const wd = buildWeekDays();
      const s = wd[0].toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
      const e = wd[6].toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
      return `${s} – ${e}`;
    }
    const d = selectedDay || currentDate;
    return d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'long' });
  }

  const today = new Date();
  const monthDays = buildMonthDays();
  const weekDays = buildWeekDays();
  const dayForPanel = view === 'day' ? (selectedDay || currentDate) : selectedDay;
  const dayEvents = dayForPanel ? eventsForDay(dayForPanel) : [];

  return (
    <div className={styles.page}>
      {/* View switcher */}
      <div className={styles.viewSwitch}>
        {['month', 'week', 'day'].map(v => (
          <button
            key={v}
            className={`${styles.switchBtn} ${view === v ? styles.switchActive : ''}`}
            onClick={() => {
              if (v !== 'month' && !selectedDay) setSelectedDay(new Date());
              setView(v);
            }}
          >
            {v === 'month' ? 'Месяц' : v === 'week' ? 'Неделя' : 'День'}
          </button>
        ))}
      </div>

      {/* Navigation */}
      <div className={styles.navHeader}>
        <button className={styles.navBtn} onClick={prevPeriod}>‹</button>
        <span className={styles.navTitle}>{navTitle()}</span>
        <button className={styles.navBtn} onClick={nextPeriod}>›</button>
        <button className={styles.refreshBtn} onClick={loadEvents} disabled={loading}>↻</button>
      </div>

      {loading ? (
        <div className={styles.loaderWrap}><div className={styles.loader} /></div>
      ) : (
        <>
          {/* ── MONTH VIEW ── */}
          {view === 'month' && (
            <div className={styles.monthGrid}>
              {DAYS.map(d => (
                <div key={d} className={styles.dayName}>{d}</div>
              ))}
              {monthDays.map((day, i) => {
                if (!day) return <div key={`e-${i}`} className={styles.emptyCell} />;
                const dayEvs = eventsForDay(day);
                const isToday = isSameDay(day, today);
                const isSelected = selectedDay && isSameDay(day, selectedDay);
                return (
                  <div
                    key={day.toISOString()}
                    className={[
                      styles.dayCell,
                      isToday ? styles.todayCell : '',
                      isSelected ? styles.selectedCell : '',
                    ].join(' ')}
                    onClick={() => setSelectedDay(isSelected ? null : day)}
                  >
                    <span className={styles.dayNum}>{day.getDate()}</span>
                    {dayEvs.slice(0, 2).map(ev => (
                      <div
                        key={ev.id}
                        className={styles.eventChip}
                        style={{ background: eventColor(ev) }}
                        onClick={e => { e.stopPropagation(); setSelectedEvent(ev); }}
                      >
                        {formatTime(ev.start_time)} {ev.title}
                      </div>
                    ))}
                    {dayEvs.length > 2 && (
                      <div className={styles.moreChip}>+{dayEvs.length - 2}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── WEEK VIEW ── */}
          {view === 'week' && (
            <>
              <div className={styles.weekRow}>
                {weekDays.map(day => {
                  const hasEvs = eventsForDay(day).length > 0;
                  const isToday = isSameDay(day, today);
                  const isSelected = selectedDay && isSameDay(day, selectedDay);
                  return (
                    <button
                      key={day.toISOString()}
                      className={[
                        styles.weekDay,
                        isToday ? styles.todayWeekDay : '',
                        isSelected ? styles.selectedWeekDay : '',
                      ].join(' ')}
                      onClick={() => setSelectedDay(day)}
                    >
                      <span className={styles.weekDayName}>{DAYS[dowMon(day)]}</span>
                      <span className={styles.weekDayNum}>{day.getDate()}</span>
                      {hasEvs && <span className={styles.weekDot} />}
                    </button>
                  );
                })}
              </div>
              <div className={styles.timeGrid}>
                <div className={styles.timeAxis}>
                  {HOURS.map(h => (
                    <div key={h} className={styles.timeLabel} style={{ height: HOUR_HEIGHT }}>
                      {String(h).padStart(2, '0')}:00
                    </div>
                  ))}
                </div>
                <div className={styles.weekColumns}>
                  {weekDays.map(day => (
                    <div key={day.toISOString()} className={styles.weekColumn}>
                      {HOURS.map(h => (
                        <div key={h} className={styles.hourCell} style={{ height: HOUR_HEIGHT }} />
                      ))}
                      {eventsForDay(day).map(ev => (
                        <div
                          key={ev.id}
                          className={styles.timeEventBlock}
                          style={{
                            top: eventTopPx(ev),
                            height: eventHeightPx(ev),
                            background: eventColor(ev),
                          }}
                          onClick={() => setSelectedEvent(ev)}
                        >
                          <span className={styles.timeEventTitle}>{ev.title}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* ── DAY VIEW ── */}
          {view === 'day' && (
            <div className={styles.timeGrid}>
              <div className={styles.timeAxis}>
                {HOURS.map(h => (
                  <div key={h} className={styles.timeLabel} style={{ height: HOUR_HEIGHT }}>
                    {String(h).padStart(2, '0')}:00
                  </div>
                ))}
              </div>
              <div className={styles.dayColumn}>
                {HOURS.map(h => (
                  <div key={h} className={styles.hourCell} style={{ height: HOUR_HEIGHT }} />
                ))}
                {dayEvents.map(ev => (
                  <div
                    key={ev.id}
                    className={styles.dayEventBlock}
                    style={{
                      top: eventTopPx(ev),
                      height: eventHeightPx(ev),
                      background: eventColor(ev),
                    }}
                    onClick={() => setSelectedEvent(ev)}
                  >
                    <span className={styles.dayEventTime}>{formatTime(ev.start_time)}</span>
                    <span className={styles.dayEventTitle}>{ev.title}</span>
                    {ev.location && (
                      <span className={styles.dayEventLoc}>📍 {ev.location}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Month day events panel ── */}
          {view === 'month' && selectedDay && (
            <div className={styles.dayPanel}>
              <h3 className={styles.dayPanelTitle}>
                {selectedDay.toLocaleDateString('ru-RU', {
                  weekday: 'long', day: 'numeric', month: 'long',
                })}
              </h3>
              {dayEvents.length === 0 ? (
                <div className={styles.emptyState}>
                  <div className={styles.emptyStateIcon}>📅</div>
                  <div className={styles.emptyStateTitle}>Событий нет</div>
                </div>
              ) : (
                <div className={styles.eventList}>
                  {dayEvents.map(ev => (
                    <div
                      key={ev.id}
                      className={styles.eventCard}
                      onClick={() => setSelectedEvent(ev)}
                    >
                      <div className={styles.eventCardHeader}>
                        <span
                          className={styles.eventColorDot}
                          style={{ background: eventColor(ev) }}
                        />
                        <span className={styles.eventCardTime}>
                          {formatTime(ev.start_time)}
                          {ev.end_time && ` – ${formatTime(ev.end_time)}`}
                        </span>
                      </div>
                      <p className={styles.eventCardTitle}>{ev.title}</p>
                      {ev.location && (
                        <p className={styles.eventCardLoc}>📍 {ev.location}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* FAB */}
      <button
        className={styles.fab}
        onClick={() => setCreatingDate(toDateStr(selectedDay || currentDate))}
        title="Добавить мероприятие"
      >
        ＋
      </button>

      {/* Modals */}
      {selectedEvent && (
        <EventModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
          onSaved={() => { setSelectedEvent(null); loadEvents(); }}
          onDeleted={() => { setSelectedEvent(null); loadEvents(); }}
        />
      )}
      {creatingDate && !selectedEvent && (
        <EventModal
          defaultDate={creatingDate}
          onClose={() => setCreatingDate(null)}
          onSaved={() => { setCreatingDate(null); loadEvents(); }}
        />
      )}
    </div>
  );
}
