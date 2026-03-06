import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NavBar } from './components/NavBar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { CallbackPage } from './pages/CallbackPage';
import { DealDetailPage } from './pages/DealDetailPage';
import { FeedPage } from './pages/FeedPage';
import { LoginPage } from './pages/LoginPage';
import { PreferencesPage } from './pages/PreferencesPage';
import { SearchPage } from './pages/SearchPage';
import { TopDealsPage } from './pages/TopDealsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-header-icon">
          <img src="/dealfinder_icon.png" alt="Deal Finder" />
        </div>
        <NavBar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<FeedPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/top" element={<TopDealsPage />} />
            <Route path="/deals/:id" element={<DealDetailPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<CallbackPage />} />
            <Route
              path="/preferences"
              element={
                <ProtectedRoute>
                  <PreferencesPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
