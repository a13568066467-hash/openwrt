import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import './index.css';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            colorPrimary: '#3b82f6',
            colorBgContainer: 'rgba(255, 255, 255, 0.7)',
            colorBorder: 'rgba(255, 255, 255, 0.8)',
            borderRadius: 10,
            fontFamily: "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          },
          components: {
            Button: {
              primaryShadow: '0 2px 8px rgba(59, 130, 246, 0.25)',
            },
            Table: {
              headerBg: 'rgba(255, 255, 255, 0.35)',
              rowHoverBg: 'rgba(255, 255, 255, 0.45)',
              borderColor: 'rgba(255, 255, 255, 0.55)',
              colorBgContainer: 'transparent',
            },
            Modal: {
              contentBg: 'rgba(255, 255, 255, 0.92)',
            },
          },
        }}
      >
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
