import { QueryClient, QueryClientProvider, type Query } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const LIVE_POLL_MS = 4_000

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2_000,
      retry: 2,
      retryDelay: (i) => Math.min(1_000 * 2 ** i, 8_000),
      // Avoid hammering a dead backend every 4s; only poll after a successful fetch.
      refetchInterval: (q: Query) =>
        q.state.status === 'success' ? LIVE_POLL_MS : false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
