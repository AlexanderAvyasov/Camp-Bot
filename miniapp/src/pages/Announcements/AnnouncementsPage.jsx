import React from 'react';

export default function AnnouncementsPage() {
  return (
    <div style={{ padding: '20px' }}>
      <h1 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '16px' }}>Объявления</h1>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '48px 16px', gap: '8px' }}>
        <div style={{ fontSize: '48px' }}>🚧</div>
        <div style={{ fontSize: '17px', fontWeight: '600', color: 'var(--tg-theme-text-color, #1c1c1e)' }}>В разработке</div>
        <div style={{ fontSize: '14px', color: 'var(--tg-theme-hint-color, #8e8e93)', textAlign: 'center' }}>Раздел будет доступен в следующей версии</div>
      </div>
    </div>
  );
}
