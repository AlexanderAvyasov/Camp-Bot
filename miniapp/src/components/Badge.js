import React from 'react';
import styles from './Badge.module.css';

export default function Badge({ children, variant = 'default' }) {
  const cls = styles[variant] || styles.default;
  return (
    <span className={`${styles.badge} ${cls}`}>{children}</span>
  );
}
