import React, { useCallback, useEffect, useState } from 'react';
import { circlesApi } from '../../api';
import { useAuth } from '../../hooks/useAuth';

// All styles inline — no separate CSS module required
const S = {
  page: { display:'flex', flexDirection:'column', minHeight:'100vh', background:'var(--tg-theme-bg-color,#f4f4f8)', paddingBottom:'calc(var(--tab-height,60px) + 80px)' },
  header: { position:'sticky', top:0, zIndex:10, display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 16px', background:'var(--tg-theme-bg-color,#f4f4f8)', borderBottom:'1px solid rgba(0,0,0,.07)' },
  headerTitle: { fontSize:18, fontWeight:700, color:'var(--tg-theme-text-color,#1c1c1e)' },
  refreshBtn: { background:'rgba(0,0,0,.07)', border:'none', borderRadius:8, width:32, height:32, fontSize:16, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center' },
  loaderWrap: { display:'flex', alignItems:'center', justifyContent:'center', padding:'48px 16px' },
  loader: { width:32, height:32, border:'3px solid rgba(0,0,0,.1)', borderTopColor:'var(--tg-theme-button-color,#3478f6)', borderRadius:'50%', animation:'spin .7s linear infinite' },
  emptyState: { display:'flex', flexDirection:'column', alignItems:'center', padding:'56px 16px', gap:8 },
  emptyIcon: { fontSize:48 },
  emptyTitle: { fontSize:17, fontWeight:600, color:'var(--tg-theme-text-color,#1c1c1e)' },
  emptySubtitle: { fontSize:14, color:'var(--tg-theme-hint-color,#8e8e93)', textAlign:'center' },
  // My circle card
  myCircleCard: { margin:'16px 16px 8px', background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:18, padding:18, boxShadow:'0 2px 12px rgba(0,0,0,.08)' },
  circleName: { fontSize:22, fontWeight:800, color:'var(--tg-theme-text-color,#1c1c1e)', marginBottom:6 },
  circleSchedule: { fontSize:14, color:'var(--tg-theme-hint-color,#8e8e93)', marginBottom:4 },
  circleStats: { display:'flex', gap:16, marginTop:10 },
  statItem: { display:'flex', flexDirection:'column', alignItems:'center', gap:2 },
  statNum: { fontSize:20, fontWeight:800, color:'var(--tg-theme-button-color,#3478f6)' },
  statLabel: { fontSize:11, color:'var(--tg-theme-hint-color,#8e8e93)', textTransform:'uppercase', letterSpacing:'.04em' },
  // Members
  membersSection: { margin:'0 16px 16px' },
  sectionTitle: { fontSize:13, fontWeight:700, textTransform:'uppercase', letterSpacing:'.04em', color:'var(--tg-theme-hint-color,#8e8e93)', marginBottom:8, paddingTop:4 },
  memberRow: { display:'flex', alignItems:'center', gap:10, padding:'10px 0', borderBottom:'1px solid rgba(0,0,0,.06)' },
  memberAvatar: { flexShrink:0, width:36, height:36, borderRadius:'50%', background:'var(--tg-theme-button-color,#3478f6)', color:'var(--tg-theme-button-text-color,#fff)', fontSize:13, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', textTransform:'uppercase' },
  memberInfo: { flex:1, minWidth:0 },
  memberName: { fontSize:14, fontWeight:600, color:'var(--tg-theme-text-color,#1c1c1e)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' },
  memberSquad: { fontSize:12, color:'var(--tg-theme-hint-color,#8e8e93)' },
  attendanceDots: { display:'flex', gap:3, flexShrink:0 },
  dot: { width:8, height:8, borderRadius:'50%' },
  // Circle list (if not in my-circle view)
  circleList: { display:'flex', flexDirection:'column', gap:8, padding:'0 16px' },
  circleCard: { background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:14, padding:'14px', boxShadow:'0 1px 4px rgba(0,0,0,.07)', cursor:'pointer' },
  circleCardName: { fontSize:16, fontWeight:700, color:'var(--tg-theme-text-color,#1c1c1e)', marginBottom:4 },
  circleCardMeta: { fontSize:13, color:'var(--tg-theme-hint-color,#8e8e93)' },
  // FAB
  fab: { position:'fixed', bottom:'calc(var(--tab-height,60px) + 16px)', right:16, width:52, height:52, borderRadius:'50%', background:'var(--tg-theme-button-color,#3478f6)', color:'var(--tg-theme-button-text-color,#fff)', fontSize:26, lineHeight:1, border:'none', boxShadow:'0 4px 16px rgba(0,0,0,.18)', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', zIndex:50 },
  // Bottom sheet / attendance modal
  overlay: { position:'fixed', inset:0, background:'rgba(0,0,0,.45)', zIndex:200, display:'flex', alignItems:'flex-end' },
  sheet: { width:'100%', background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:'20px 20px 0 0', padding:'8px 0 32px', maxHeight:'85vh', overflowY:'auto' },
  sheetHandle: { width:40, height:4, borderRadius:2, background:'rgba(0,0,0,.15)', margin:'0 auto 12px' },
  sheetHeader: { display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 16px 12px', borderBottom:'1px solid rgba(0,0,0,.07)' },
  sheetTitle: { fontSize:17, fontWeight:700, color:'var(--tg-theme-text-color,#1c1c1e)', margin:0 },
  closeBtn: { background:'rgba(0,0,0,.07)', border:'none', borderRadius:'50%', width:28, height:28, display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, cursor:'pointer' },
  sheetBody: { padding:16 },
  sheetMemberRow: { display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 0', borderBottom:'1px solid rgba(0,0,0,.06)' },
  sheetMemberName: { fontSize:15, fontWeight:500, color:'var(--tg-theme-text-color,#1c1c1e)' },
  sheetToggle: { display:'flex', borderRadius:8, overflow:'hidden', border:'1.5px solid rgba(0,0,0,.1)' },
  sheetToggleBtn: { padding:'6px 12px', border:'none', fontSize:13, fontWeight:600, cursor:'pointer', transition:'all .15s' },
  saveBtn: { width:'100%', padding:13, borderRadius:12, border:'none', background:'var(--tg-theme-button-color,#3478f6)', color:'var(--tg-theme-button-text-color,#fff)', fontSize:15, fontWeight:700, cursor:'pointer', marginTop:16 },
};

function getInitials(name) {
  if (!name) return '?';
  const parts = name.trim().split(' ');
  return parts.length >= 2 ? parts[0][0] + parts[1][0] : parts[0].substring(0, 2);
}

function attendancePercent(members) {
  if (!members || members.length === 0) return 0;
  const total = members.reduce((acc, m) => acc + (m.sessions_total || 0), 0);
  const present = members.reduce((acc, m) => acc + (m.sessions_present || 0), 0);
  if (total === 0) return 0;
  return Math.round(present / total * 100);
}

// Attendance dot: true=present, false=absent, null=no class
function AttendanceDot({ value }) {
  let bg = '#d1d5db'; // gray - no class
  if (value === true) bg = '#22c55e';  // green
  if (value === false) bg = '#ef4444'; // red
  return <div style={{ ...S.dot, background: bg }} />;
}

function AttendanceSheet({ circle, members, onClose, onSaved }) {
  const [attendance, setAttendance] = useState(() => {
    const init = {};
    members.forEach(m => { init[m.id] = false; });
    return init;
  });
  const [saving, setSaving] = useState(false);

  function toggle(id, present) {
    setAttendance(prev => ({ ...prev, [id]: present }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const records = members.map(m => ({ child_id: m.id, present: !!attendance[m.id] }));
      await circlesApi.saveAttendance(circle.id, today, records);
      onSaved();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.sheet} onClick={e => e.stopPropagation()}>
        <div style={S.sheetHandle} />
        <div style={S.sheetHeader}>
          <h2 style={S.sheetTitle}>Отметить посещаемость</h2>
          <button style={S.closeBtn} onClick={onClose}>✕</button>
        </div>
        <div style={S.sheetBody}>
          {members.map(m => {
            const present = attendance[m.id];
            return (
              <div key={m.id} style={S.sheetMemberRow}>
                <span style={S.sheetMemberName}>{m.full_name || m.name || `#${m.id}`}</span>
                <div style={S.sheetToggle}>
                  <button
                    style={{
                      ...S.sheetToggleBtn,
                      background: present ? '#22c55e' : 'transparent',
                      color: present ? '#fff' : 'var(--tg-theme-hint-color,#8e8e93)',
                    }}
                    onClick={() => toggle(m.id, true)}
                  >
                    ✅ Был
                  </button>
                  <button
                    style={{
                      ...S.sheetToggleBtn,
                      background: present === false ? '#ef4444' : 'transparent',
                      color: present === false ? '#fff' : 'var(--tg-theme-hint-color,#8e8e93)',
                    }}
                    onClick={() => toggle(m.id, false)}
                  >
                    ❌ Не был
                  </button>
                </div>
              </div>
            );
          })}
          <button style={{ ...S.saveBtn, opacity: saving ? 0.6 : 1 }} onClick={handleSave} disabled={saving}>
            {saving ? 'Сохранение...' : '💾 Сохранить посещаемость'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CirclesPage() {
  const { staff } = useAuth();
  const [circles, setCircles] = useState([]);
  const [activeCircle, setActiveCircle] = useState(null);
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showAttendance, setShowAttendance] = useState(false);

  const loadCircles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await circlesApi.list();
      const list = Array.isArray(data) ? data : data.items || [];
      setCircles(list);
      // Auto-select my circle if leader
      if (staff?.role === 'circle_leader') {
        const mine = list.find(c => c.leader_id === staff.id || c.staff_id === staff.id);
        if (mine) selectCircle(mine, list);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [staff?.id, staff?.role]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadCircles(); }, [loadCircles]);

  async function selectCircle(circle) {
    setActiveCircle(circle);
    setMembersLoading(true);
    try {
      const data = await circlesApi.members(circle.id);
      setMembers(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      setMembers([]);
    } finally {
      setMembersLoading(false);
    }
  }

  function handleAttendanceSaved() {
    setShowAttendance(false);
    if (activeCircle) selectCircle(activeCircle);
  }

  const totalChildren = members.length;
  const pctAttendance = attendancePercent(members);

  if (loading) {
    return (
      <div style={S.page}>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        <div style={S.loaderWrap}><div style={S.loader} /></div>
      </div>
    );
  }

  if (!activeCircle && circles.length === 0) {
    return (
      <div style={S.page}>
        <div style={S.emptyState}>
          <div style={S.emptyIcon}>🧩</div>
          <div style={S.emptyTitle}>Кружки не найдены</div>
          <div style={S.emptySubtitle}>Нет назначенных кружков</div>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>

      <div style={S.header}>
        {activeCircle ? (
          <>
            <button
              style={{ ...S.refreshBtn, marginRight: 8 }}
              onClick={() => setActiveCircle(null)}
            >
              ←
            </button>
            <span style={S.headerTitle}>{activeCircle.name}</span>
          </>
        ) : (
          <span style={S.headerTitle}>🧩 Кружки</span>
        )}
        <button style={S.refreshBtn} onClick={loadCircles} disabled={loading}>↻</button>
      </div>

      {!activeCircle ? (
        /* Circle list */
        <div style={S.circleList}>
          {circles.map(c => (
            <div key={c.id} style={S.circleCard} onClick={() => selectCircle(c)}>
              <div style={S.circleCardName}>{c.name}</div>
              {c.schedule && <div style={S.circleCardMeta}>🕐 {c.schedule}</div>}
              {c.location && <div style={S.circleCardMeta}>📍 {c.location}</div>}
              {c.members_count !== undefined && (
                <div style={S.circleCardMeta}>👥 {c.members_count} детей</div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <>
          {/* My Circle summary card */}
          <div style={S.myCircleCard}>
            <div style={S.circleName}>{activeCircle.name}</div>
            {activeCircle.schedule && (
              <div style={S.circleSchedule}>🕐 {activeCircle.schedule}</div>
            )}
            {activeCircle.location && (
              <div style={S.circleSchedule}>📍 {activeCircle.location}</div>
            )}
            <div style={S.circleStats}>
              <div style={S.statItem}>
                <span style={S.statNum}>{totalChildren}</span>
                <span style={S.statLabel}>детей</span>
              </div>
              <div style={S.statItem}>
                <span style={S.statNum}>{pctAttendance}%</span>
                <span style={S.statLabel}>посещ.</span>
              </div>
            </div>
          </div>

          {/* Members list */}
          {membersLoading ? (
            <div style={S.loaderWrap}><div style={S.loader} /></div>
          ) : (
            <div style={S.membersSection}>
              <div style={S.sectionTitle}>Участники</div>
              {members.length === 0 ? (
                <div style={{ ...S.emptyState, padding: '24px 0' }}>
                  <div style={S.emptyIcon}>👥</div>
                  <div style={S.emptyTitle}>Нет участников</div>
                </div>
              ) : (
                members.map(m => {
                  // Last 7 sessions attendance dots
                  const history = m.attendance_history || [];
                  const dots = Array.from({ length: 7 }, (_, i) => {
                    const entry = history[history.length - 7 + i];
                    if (entry === undefined) return null;
                    return entry;
                  });
                  return (
                    <div key={m.id} style={S.memberRow}>
                      <div style={S.memberAvatar}>
                        {getInitials(m.full_name || m.name)}
                      </div>
                      <div style={S.memberInfo}>
                        <div style={S.memberName}>{m.full_name || m.name || `#${m.id}`}</div>
                        {m.squad_name && (
                          <div style={S.memberSquad}>Отряд {m.squad_name}</div>
                        )}
                      </div>
                      <div style={S.attendanceDots}>
                        {dots.map((val, i) => <AttendanceDot key={i} value={val} />)}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* FAB: mark attendance */}
          <button
            style={S.fab}
            onClick={() => setShowAttendance(true)}
            title="Отметить посещаемость"
          >
            ✅
          </button>
        </>
      )}

      {/* Attendance bottom sheet */}
      {showAttendance && activeCircle && (
        <AttendanceSheet
          circle={activeCircle}
          members={members}
          onClose={() => setShowAttendance(false)}
          onSaved={handleAttendanceSaved}
        />
      )}
    </div>
  );
}
