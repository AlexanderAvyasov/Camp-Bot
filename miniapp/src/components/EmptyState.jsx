import React from 'react';
import styles from './EmptyState.module.css';

export default function EmptyState({ icon = '📭', title = 'Ничего нет', subtitle = '' }) {
  return (
    <div className={styles.wrapper}>
      <span className={styles.icon}>{icon}</span>
      <p className={styles.title}>{title}</p>
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
    </div>
  );
}
