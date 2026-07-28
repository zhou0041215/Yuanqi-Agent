/// <reference types="vite/client" />

interface Window {
  __YUANQI_AUTH__?: { accessToken: string };
  __YUANQI_CONFIG__?: { agentApiBaseUrl?: string };
}
