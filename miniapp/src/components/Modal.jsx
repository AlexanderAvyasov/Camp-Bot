import React, { useEffect, useRef } from 'react';
import styles from './Modal.module.css';

export default function Modal({ isOpen, onClose, title, children, fullHeight = false }) {
  const sheetRef = useRef(null);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;
    if (isOpen) {
      tg.BackButton.show();
      tg.BackButton.onClick(onClose);
    } else {
      tg.BackButton.hide();
    }
    return () => { tg.BackButton.hide(); tg.BackButton.offClick(onClose); };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        ref={sheetRef}
        className={`${styles.sheet} ${fullHeight ? styles.fullHeight : ''}`}
        onClick={e => e.stopPropagation()}
      >
        <div className={styles.handle} />
        {title && <h2 className={styles.title}>{title}</h2>}
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
