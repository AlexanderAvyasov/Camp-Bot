import React, { useCallback, useEffect, useState } from 'react';
import { dutiesApi } from '../../api';
import { useAuth } from '../../hooks/useAuth';
import { DUTY_TYPE_LABELS, DUTY_STATUS_COLORS } from '../../constants';

// Inline style map (no separate CSS module needed)
const S = {
  page: { display:'flex', flexDirection:'column', minHeight:'100vh', background:'var(--tg-theme-bg-color,#f4f4f8)', paddingBottom:'calc(var(--tab-height,60px) + 16px)' },
  header: { position:'sticky', top:0, zIndex:10, display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 16px', background:'var(--tg-theme-bg-color,#f4f4f8)', borderBottom:'1px solid rgba(0,0,0,.07)' },
  headerTitle: { fontSize:18, fontWeight:700, color:'var(--tg-theme-text-color,#1c1c1e)' },
  refreshBtn: { background:'rgba(0,0,0,.07)', border:'none', borderRadius:8, width:32, height:32, fontSize:16, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center' },
  loaderWrap: { display:'flex', alignItems:'center', justifyContent:'center', padding:'48px 16px' },
  loader: { width:32, height:32, border:'3px solid rgba(0,0,0,.1)', borderTopColor:'var(--tg-theme-button-color,#3478f6)', borderRadius:'50%' },
  todayCard: { margin:16, background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:18, padding:18, boxShadow:'0 2px 12px rgba(0,0,0,.08)' },
  todayHeader: { display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 },
  todayLabel: { fontSize:12, fontWeight:700, textTransform:'uppercase', letterSpacing:'.04em', color:'var(--tg-theme-hint-color,#8e8e93)' },
  dutyType: { fontSize:24, fontWeight:800, color:'var(--tg-theme-text-color,#1c1c1e)', marginBottom:4 },
  dutyTime: { fontSize:14, color:'var(--tg-theme-hint-color,#8e8e93)', marginBottom:14 },
  todayActions: { display:'flex', flexDirection:'column', gap:10 },
  actionRow: { display:'flex', gap:8, flexWrap:'wrap' },
  btnPrimary: { flex:1, minWidth:100, padding:'11px 16px', borderRadius:12, border:'none', background:'var(--tg-theme-button-color,#3478f6)', color:'var(--tg-theme-button-text-color,#fff)', fontSize:14, fontWeight:600, cursor:'pointer' },
  btnSecondary: { flex:1, minWidth:90, padding:'11px 12px', borderRadius:12, border:'1.5px solid rgba(0,0,0,.12)', background:'transparent', color:'var(--tg-theme-text-color,#1c1c1e)', fontSize:14, fontWeight:600, cursor:'pointer' },
  btnDanger: { flex:1, minWidth:90, padding:'11px 12px', borderRadius:12, border:'none', background:'#ef4444', color:'#fff', fontSize:14, fontWeight:600, cursor:'pointer' },
  completedBadge: { fontSize:15, fontWeight:700, color:'#16a34a', textAlign:'center', padding:'10px 0' },
  checkpoints: { marginTop:16, borderTop:'1px solid rgba(0,0,0,.07)', paddingTop:12 },
  checkpointsTitle: { fontSize:12, fontWeight:700, textTransform:'uppercase', letterSpacing:'.04em', color:'var(--tg-theme-hint-color,#8e8e93)', marginBottom:8 },
  checkpointItem: { display:'flex', gap:10, padding:'6px 0', borderBottom:'1px solid rgba(0,0,0,.05)' },
  checkpointTime: { fontSize:13, fontWeight:600, color:'var(--tg-theme-button-color,#3478f6)', flexShrink:0, width:44 },
  checkpointNote: { fontSize:13, color:'var(--tg-theme-text-color,#1c1c1e)' },
  noDutyCard: { margin:16, background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:18, padding:'32px 18px', boxShadow:'0 2px 12px rgba(0,0,0,.08)', display:'flex', flexDirection:'column', alignItems:'center', gap:8 },
  noDutyIcon: { fontSize:36 },
  noDutyText: { fontSize:16, fontWeight:600, color:'var(--tg-theme-text-color,#1c1c1e)' },
  section: { margin:'0 16px 16px' },
  sectionTitle: { fontSize:13, fontWeight:700, textTransform:'uppercase', letterSpacing:'.04em', color:'var(--tg-theme-hint-color,#8e8e93)', marginBottom:8, paddingTop:4 },
  dutyRow: { display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 14px', background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:12, marginBottom:8, gap:8 },
  dutyRowLeft: { flex:1, minWidth:0 },
  dutyRowType: { fontSize:14, fontWeight:600, color:'var(--tg-theme-text-color,#1c1c1e)' },
  dutyRowDate: { fontSize:12, color:'var(--tg-theme-hint-color,#8e8e93)', marginTop:2 },
  statusBadge: { fontSize:12, fontWeight:600 },
  emptyState: { display:'flex', flexDirection:'column', alignItems:'center', padding:'56px 16px', gap:8 },
  emptyIcon: { fontSize:48 },
  emptyTitle: { fontSize:17, fontWeight:600, color:'var(--tg-theme-text-color,#1c1c1e)' },
  emptySubtitle: { fontSize:14, color:'var(--tg-theme-hint-color,#8e8e93)', textAlign:'center' },
  overlay: { position:'fixed', inset:0, background:'rgba(0,0,0,.5)', zIndex:200, display:'flex', alignItems:'center', justifyContent:'center', padding:16 },
  alertModal: { width:'100%', maxWidth:320, background:'var(--tg-theme-secondary-bg-color,#fff)', borderRadius:20, padding:'24px 20px', textAlign:'center' },
  alertIcon: { fontSize:44, marginBottom:10 },
  alertTitle: { fontSize:18, fontWeight:800, color:'var(--tg-theme-text-color,#1c1c1e)', margin:'0 0 8px' },
  alertBody: { fontSize:14, color:'var(--tg-theme-hint-color,#8e8e93)', lineHeight:1.5, margin:'0 0 20px' },
  alertActions: { display:'flex', gap:10 },
  btnCancel: { flex:1, padding:12, borderRadius:12, border:'1.5px solid rgba(0,0,0,.12)', background:'transparent', fontSize:15, fontWeight:600, cursor:'pointer', color:'var(--tg-theme-text-color,#1c1c1e)' },
};

const STATUS_LABELS = {
  scheduled: 'запланировано',
  active: 'активно',
  completed: 'выполнено',
};

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'long', weekday: 'short',
  });
}

function formatTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

function AlertModal({ onConfirm, onClose }) {
  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.alertModal} onClick={e => e.stopPropagation()}>
        <div style={S.alertIcon}>🚨</div>
        <h2 style={S.alertTitle}>Объявить тревогу?</h2>
        <p style={S.alertBody}>
          Это действие немедленно уведомит старшего вожатого и администрацию.
        </p>
        <div style={S.alertActions}>
          <button style={S.btnCancel} onClick={onClose}>Отмена</button>
          <button style={S.btnDanger} onClick={onConfirm}>Объявить</button>
        </div>
      </div>
    </div>
  );
}

export default function DutiesPage() {
  const { staff } = useAuth();
  const [duties, setDuties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null); // duty id being updated
  const [showAlert, setShowAlert] = useState(false);
  const [activeDutyId, setActiveDutyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = staff?.id ? { staff_id: staff.id } : {};
      const data = await dutiesApi.list(params);
      setDuties(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [staff?.id]);

  useEffect(() => { load(); }, [load]);

  // Find today's duty (active or scheduled for today)
  const today = new Date();
  const todayDuty = duties.find(d => {
    const date = new Date(d.date || d.start_time);
    return (
      date.getFullYear() === today.getFullYear() &&
      date.getMonth() === today.getMonth() &&
      date.getDate() === today.getDate()
    );
  });

  const upcomingDuties = duties
    .filter(d => {
      if (d === todayDuty) return false;
      const date = new Date(d.date || d.start_time);
      return date >= today;
    })
    .sort((a, b) => new Date(a.date || a.start_time) - new Date(b.date || b.start_time))
    .slice(0, 10);

  async function updateStatus(id, status) {
    setUpdating(id);
    try {
      await dutiesApi.updateStatus(id, status);
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setUpdating(null);
    }
  }

  async function handleAlert() {
    setShowAlert(false);
    if (activeDutyId) {
      await updateStatus(activeDutyId, 'alert');
    }
  }

  function statusColor(status) {
    return DUTY_STATUS_COLORS[status] || '#64748B';
  }

  function renderTodayActions(duty) {
    const busy = updating === duty.id;
    if (duty.status === 'scheduled') {
      return (
        <button
          style={{ ...S.btnPrimary, opacity: busy ? 0.6 : 1 }}
          onClick={() => updateStatus(duty.id, 'active')}
          disabled={busy}
        >
          {busy ? '...' : '✅ Заступить'}
        </button>
      );
    }
    if (duty.status === 'active') {
      return (
        <div style={S.actionRow}>
          <button
            style={{ ...S.btnSecondary, opacity: busy ? 0.6 : 1 }}
            onClick={() => updateStatus(duty.id, 'checkpoint')}
            disabled={busy}
          >
            📍 Отметка
          </button>
          <button
            style={{ ...S.btnPrimary, opacity: busy ? 0.6 : 1 }}
            onClick={() => updateStatus(duty.id, 'completed')}
            disabled={busy}
          >
            ✅ Сдать
          </button>
          <button
            style={{ ...S.btnDanger, opacity: busy ? 0.6 : 1 }}
            onClick={() => { setActiveDutyId(duty.id); setShowAlert(true); }}
            disabled={busy}
          >
            🚨 Тревога
          </button>
        </div>
      );
    }
    if (duty.status === 'completed') {
      return (
        <div style={S.completedBadge}>✅ Дежурство сдано</div>
      );
    }
    return null;
  }

  return (
    <div style={S.page}>
      <div style={S.header}>
        <span style={S.headerTitle}>🔄 Дежурства</span>
        <button style={S.refreshBtn} onClick={load} disabled={loading}>↻</button>
      </div>

      {loading ? (
        <div style={S.loaderWrap}>
          <div style={{ ...S.loader, animation: 'spin 0.7s linear infinite' }} />
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      ) : (
        <>
          {/* My Duty Today */}
          {todayDuty ? (
            <div style={S.todayCard}>
              <div style={S.todayHeader}>
                <span style={S.todayLabel}>Сегодня</span>
                <span style={{ ...S.statusBadge, color: statusColor(todayDuty.status) }}>
                  {STATUS_LABELS[todayDuty.status] || todayDuty.status}
                </span>
              </div>
              <div style={S.dutyType}>
                {DUTY_TYPE_LABELS[todayDuty.duty_type || todayDuty.type] || todayDuty.duty_type || todayDuty.type}
              </div>
              {(todayDuty.start_time || todayDuty.date) && (
                <div style={S.dutyTime}>
                  {formatTime(todayDuty.start_time || todayDuty.date)}
                  {todayDuty.end_time && ` – ${formatTime(todayDuty.end_time)}`}
                </div>
              )}
              <div style={S.todayActions}>
                {renderTodayActions(todayDuty)}
              </div>

              {/* Checkpoint history */}
              {todayDuty.checkpoints?.length > 0 && (
                <div style={S.checkpoints}>
                  <div style={S.checkpointsTitle}>История отметок</div>
                  {todayDuty.checkpoints.map((cp, i) => (
                    <div key={i} style={{ ...S.checkpointItem, borderBottom: i < todayDuty.checkpoints.length - 1 ? '1px solid rgba(0,0,0,.05)' : 'none' }}>
                      <span style={S.checkpointTime}>{formatTime(cp.time)}</span>
                      <span style={S.checkpointNote}>{cp.note || '📍 Отметка'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div style={S.noDutyCard}>
              <div style={S.noDutyIcon}>✅</div>
              <div style={S.noDutyText}>Сегодня дежурств нет</div>
            </div>
          )}

          {/* Upcoming duties */}
          {upcomingDuties.length > 0 && (
            <div style={S.section}>
              <div style={S.sectionTitle}>Предстоящие дежурства</div>
              {upcomingDuties.map(d => (
                <div key={d.id} style={S.dutyRow}>
                  <div style={S.dutyRowLeft}>
                    <div style={S.dutyRowType}>
                      {DUTY_TYPE_LABELS[d.duty_type || d.type] || d.duty_type || d.type}
                    </div>
                    <div style={S.dutyRowDate}>
                      {formatDate(d.date || d.start_time)}
                    </div>
                  </div>
                  <span style={{ ...S.statusBadge, color: statusColor(d.status) }}>
                    {STATUS_LABELS[d.status] || d.status}
                  </span>
                </div>
              ))}
            </div>
          )}

          {duties.length === 0 && (
            <div style={S.emptyState}>
              <div style={S.emptyIcon}>🔄</div>
              <div style={S.emptyTitle}>Дежурства не назначены</div>
              <div style={S.emptySubtitle}>Обратитесь к администратору</div>
            </div>
          )}
        </>
      )}

      {showAlert && (
        <AlertModal
          onConfirm={handleAlert}
          onClose={() => setShowAlert(false)}
        />
      )}
    </div>
  );
}
