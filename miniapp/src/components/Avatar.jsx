import React from 'react';
import styles from './Avatar.module.css';

const COLORS = ['#2563EB','#7C3AED','#16A34A','#D97706','#DC2626','#0891B2'];

function getColor(name = '') {
  const idx = name.charCodeAt(0) % COLORS.length;
  return COLORS[idx];
}

function getInitials(name = '') {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

export default function Avatar({ name = '', size = 36 }) {
  return (
    <div
      className={styles.avatar}
      style={{ width: size, height: size, fontSize: size * 0.36, background: getColor(name) }}
    >
      {getInitials(name)}
    </div>
  );
}
