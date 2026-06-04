import React from 'react';
import styles from './Badge.module.css';

/**
 * type: 'default' | 'info' | 'success' | 'warning' | 'danger'
 */
export default function Badge({ type = 'default', text }) {
  return (
    <span className={`${styles.badge} ${styles[type] || styles.default}`}>
      {text}
    </span>
  );
}
