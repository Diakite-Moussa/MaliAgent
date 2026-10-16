// En production, si le dashboard est hébergé sur un domaine distinct de l'API (ex: Render Static Site),
// l'URL de l'API peut être définie dynamiquement via window.__API_URL__ ou localStorage 'maliagent_api_url',
// ou codée en dur ci-dessous avec l'URL Render de l'API (ex: 'https://maliagent-api.onrender.com').
const getProductionApiUrl = (): string => {
  if (typeof window !== 'undefined') {
    const win = window as any;
    if (win.__API_URL__) return win.__API_URL__;
    const stored = localStorage.getItem('maliagent_api_url');
    if (stored) return stored;
  }
  return '';
};

export const environment = {
  production: true,
  apiUrl: getProductionApiUrl(),
};

