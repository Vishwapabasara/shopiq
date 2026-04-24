const API_URL = import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app';

// Session is managed via the HTTP-only cookie set by the backend during OAuth.
// Shop is only read from URL params (present during the OAuth redirect moment).
const getShop = (): string | null =>
  new URLSearchParams(window.location.search).get('shop');

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
      if (response.status === 401) window.location.href = '/login';
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
      if (response.status === 401) window.location.href = '/login';
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
    window.location.href = '/login';
  }
};
