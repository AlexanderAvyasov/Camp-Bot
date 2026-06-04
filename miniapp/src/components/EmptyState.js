import React from 'react';
import styles from './EmptyState.module.css';

export default function EmptyState({ icon, title, subtitle, action, onAction }) {
  return (
    <div className={styles.wrapper}>
      {icon && <div className={styles.icon}>{icon}</div>}
      {title && <div className={styles.title}>{title}</div>}
      {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
      {action && onAction && (
        <button onClick={onAction} style={{ marginTop: 8, padding: '8px 20px', borderRadius: 'var(--radius-sm)', background: 'var(--color-primary)', color: '#fff', border: 'none', fontWeight: 600, fontSize: 14 }}>
          {action}
        </button>
      )}
    </div>
  );
}
