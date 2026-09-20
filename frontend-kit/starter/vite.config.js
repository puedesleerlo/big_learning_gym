import { defineConfig } from 'vite';
import fs from 'node:fs';
const manifest = JSON.parse(fs.readFileSync(new URL('./experience.json', import.meta.url)));
export default defineConfig({base: `/experience/${manifest.id}/`, resolve: {dedupe: ['react', 'react-dom']}, server: {proxy: {'/api': (process.env.GYM_DEV_ORIGIN || 'http://127.0.0.1:8787'), '/app-config.json': (process.env.GYM_DEV_ORIGIN || 'http://127.0.0.1:8787')}}, build: {target: 'es2022'}});
