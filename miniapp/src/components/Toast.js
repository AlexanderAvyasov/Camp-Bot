import React, { createContext, useContext, useState, useCallback } from 'react';
import styles from './Toast.module.css';

export const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    const delay = type === 'error' ? 3000 : 2000;
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, delay);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className={styles.container}>
        {toasts.map(t => (
          <div key={t.id} className={`${styles.toast} ${styles[t.type] || styles.info}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
