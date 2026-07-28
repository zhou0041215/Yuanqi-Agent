import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2022',
    sourcemap: true,
    chunkSizeWarningLimit: 800,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'react-runtime',
              test: /node_modules\/(?:react|react-dom|scheduler)\//,
              priority: 40,
            },
            {
              name: 'echarts-runtime',
              test: /node_modules\/(?:echarts|zrender)\//,
              priority: 30,
            },
            {
              name: 'knowledge-graph-runtime',
              test: /node_modules\/(?:3d-force-graph|force-graph|three|three-spritetext|d3-force-3d)\//,
              priority: 35,
            },
            {
              name: 'ant-design',
              test: /node_modules\/(?:@ant-design|antd|@rc-component|rc-[^/]+)\//,
              priority: 20,
            },
            {
              name: 'markdown-runtime',
              test: /node_modules\/(?:marked|dompurify|html-react-parser|@ant-design\/x-markdown)\//,
              priority: 15,
            },
          ],
        },
      },
    },
  },
});
