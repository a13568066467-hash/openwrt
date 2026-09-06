import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import RechargePage from './pages/RechargePage';
import PlansPage from './pages/PlansPage';
import UsagePage from './pages/UsagePage';
import DevicesPage from './pages/DevicesPage';
import TabBar from './components/TabBar';

function consumePortalToken() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (!token) return;
  localStorage.setItem('user_token', token);
  params.delete('token');
  const qs = params.toString();
  const next = window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash;
  window.history.replaceState({}, '', next);
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  return localStorage.getItem('user_token') ? <>{children}</> : <Navigate to="/login" />;
}

export default function App() {
  consumePortalToken();
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={
          <PrivateRoute>
            <div className="app-container">
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/recharge" element={<RechargePage />} />
                <Route path="/plans" element={<PlansPage />} />
                <Route path="/usage" element={<UsagePage />} />
                <Route path="/devices" element={<DevicesPage />} />
              </Routes>
              <TabBar />
            </div>
          </PrivateRoute>
        } />
      </Routes>
    </BrowserRouter>
  );
}
