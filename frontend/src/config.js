const isDev = window.location.port === '5173';
const BACKEND_HOST = isDev ? '127.0.0.1:8090' : window.location.host;

export const API_BASE = `${window.location.protocol}//${BACKEND_HOST}`;
export const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${BACKEND_HOST}`;
