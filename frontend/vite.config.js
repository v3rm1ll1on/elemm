/*
 * Copyright (C) 2026 Marc Stöcker
 * Website: https://elemm.dev
 *
 * This program is licensed under the Business Source License 1.1 (BSL 1.1).
 * See the LICENSE file in the root directory for details.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
