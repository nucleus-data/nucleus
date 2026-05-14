// Docs: https://react.dev/  (react==18.3.1)
// Docs: https://tanstack.com/query/v5  (@tanstack/react-query==5.62.3)
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';
import App from './App';
import { applyTheme, getStoredTheme } from './lib/theme';

// Apply stored theme immediately before first paint to avoid flash.
applyTheme(getStoredTheme());

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30s cache window — asset registry rarely changes in dev
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
