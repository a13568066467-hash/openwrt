import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import MainLayout from './layouts/MainLayout';
import RoutersPage from './pages/RoutersPage';
import UsersPage from './pages/UsersPage';
import PlansPage from './pages/PlansPage';
import VouchersPage from './pages/VouchersPage';
import UsagePage from './pages/UsagePage';
import AuditPage from './pages/AuditPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('admin_token');
  return token ? <>{children}</> : <Navigate to="/login" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><MainLayout /></PrivateRoute>}>
          <Route index element={<Navigate to="/routers" />} />
          <Route path="routers" element={<RoutersPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="plans" element={<PlansPage />} />
          <Route path="vouchers" element={<VouchersPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
