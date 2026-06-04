import React from 'react';
import styles from './Avatar.module.css';

const COLORS = [
  '#2563EB', '#16A34A', '#D97706', '#DC2626',
  '#7C3AED', '#0891B2', '#BE185D', '#059669',
];

function hashColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
  return COLORS[Math.abs(h) % COLORS.length];
}

function initials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return parts[0].substring(0, 2).toUpperCase();
}

export default function Avatar({ name = '', size = 40 }) {
  const label = initials(name);
  const bg = hashColor(name || '?');
  return (
    <div
      className={styles.avatar}
      style={{ width: size, height: size, fontSize: size * 0.38, backgroundColor: bg }}
    >
      {label}
    </div>
  );
}
