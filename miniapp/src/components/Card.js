import React from 'react';
import styles from './Card.module.css';

export default function Card({ children, onClick, className }) {
  const cls = [styles.card, onClick ? styles.clickable : '', className || ''].filter(Boolean).join(' ');
  return (
    <div className={cls} onClick={onClick}>
      {children}
    </div>
  );
}
