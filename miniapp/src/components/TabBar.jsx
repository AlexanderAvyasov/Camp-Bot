import React from 'react';
import styles from './TabBar.module.css';

export default function TabBar({ tabs, activeTab, onTabChange }) {
  return (
    <nav className={styles.tabBar}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`${styles.tab} ${activeTab === tab.id ? styles.active : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className={styles.icon}>{tab.icon}</span>
          <span className={styles.label}>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
