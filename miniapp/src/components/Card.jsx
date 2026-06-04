import React from 'react';
import styles from './Card.module.css';

export default function Card({ children, onClick, className = '', style }) {
  return (
    <div
      className={`${styles.card} ${onClick ? styles.clickable : ''} ${className}`}
      onClick={onClick}
      style={style}
    >
      {children}
    </div>
  );
}
