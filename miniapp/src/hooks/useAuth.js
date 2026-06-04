import { useState, useEffect } from 'react';
import { staffApi } from '../api';

export function useAuth() {
  const [staff, setStaff] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (!tgUser) {
      setLoading(false);
      return;
    }
    staffApi.list()
      .then(data => {
        const me = (data.items || data).find(s => s.telegram_id === tgUser.id);
        setStaff(me || null);
      })
      .catch(err => setError(err))
      .finally(() => setLoading(false));
  }, []);

  return { staff, loading, error };
}
