import React from 'react';
import styles from './Modal.module.css';

export default function Modal({ title, onClose, children, fullHeight = false }) {
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={`${styles.sheet}${fullHeight ? ' ' + styles.fullHeight : ''}`}
        onClick={e => e.stopPropagation()}
      >
        <div className={styles.handle} />
        {title && <div className={styles.title}>{title}</div>}
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
