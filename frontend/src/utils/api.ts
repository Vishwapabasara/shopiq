const API_URL = import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app';

const getSession = (): string | null => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('session') || localStorage.getItem('shopiq_session');
};

export const saveSession = (sessionId: string, shop: string) => {
  localStorage.setItem('shopiq_session', sessionId);
  localStorage.setItem('shopiq_shop', shop);
  console.log('✅ Session saved to localStorage:', sessionId);
};

export const clearSession = () => {
  localStorage.removeItem('shopiq_session');
  localStorage.removeItem('shopiq_shop');
  console.log('🗑️ Session cleared from localStorage');
};

export const getShop = (): string | null => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('shop') || localStorage.getItem('shopiq_shop');
};

export const apiClient = {
  get: async (endpoint: string) => {
    const shop = getShop();
    const url = new URL(`${API_URL}${endpoint}`);
    if (shop) url.searchParams.set('shop', shop);

    const response = await fetch(url.toString(), {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      if (response.status === 401) {
        clearSession();
        window.location.href = '/login';
      }
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },

  post: async (endpoint: string, data?: any) => {
    const shop = getShop();
    const url = new URL(`${API_URL}${endpoint}`);
    if (shop) url.searchParams.set('shop', shop);

    const response = await fetch(url.toString(), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });

    if (!response.ok) {
      if (response.status === 401) {
        clearSession();
        window.location.href = '/login';
      }
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },
};

export const logout = async () => {
  try {
    await apiClient.post('/auth/logout');
  } catch (error) {
    console.error('Logout error:', error);
  } finally {
    clearSession();
    window.location.href = '/login';
  }
};
