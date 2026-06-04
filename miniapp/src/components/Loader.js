import React from 'react';
import styles from './Loader.module.css';

export default function Loader({ center = false }) {
  return (
    <div className={center ? styles.wrapper : undefined} style={center ? {} : { display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
      <div className={styles.spinner} />
    </div>
  );
}
