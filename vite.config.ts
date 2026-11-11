import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],build:{rollupOptions:{output:{manualChunks(id){if(id.includes('maplibre-gl'))return 'maplibre';if(id.includes('@deck.gl')||id.includes('@luma.gl'))return 'deck';if(id.includes('recharts'))return 'charts';}}}}});
