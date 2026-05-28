/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

const isDev = window.location.port === '5173';
const BACKEND_HOST = isDev ? '127.0.0.1:8090' : window.location.host;

export const API_BASE = `${window.location.protocol}//${BACKEND_HOST}`;
export const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${BACKEND_HOST}`;
