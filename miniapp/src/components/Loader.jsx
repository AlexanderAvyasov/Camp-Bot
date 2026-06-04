import React from 'react';
import styles from './Loader.module.css';

export default function Loader({ text = 'Загрузка...' }) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.spinner} />
      {text && <p className={styles.text}>{text}</p>}
    </div>
  );
}
