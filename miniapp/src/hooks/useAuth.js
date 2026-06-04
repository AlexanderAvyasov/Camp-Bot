import { useState, useEffect } from 'react';
import { staffApi } from '../api';

export function useAuth() {
  const [staff, setStaff] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const initData = window.Telegram?.WebApp?.initData;
    if (!initData) {
      setLoading(false);
      return;
    }
    staffApi.me()
      .then(data => setStaff(data || null))
      .catch(err => setError(err))
      .finally(() => setLoading(false));
  }, []);

  return { staff, loading, error };
}
