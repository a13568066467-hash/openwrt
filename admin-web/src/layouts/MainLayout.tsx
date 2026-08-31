import { Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { menuIcons, LogoutIcon } from '../components/MenuIcons';
import { useBranding } from '../hooks/useBranding';

const items = [
  { key: '/routers', icon: menuIcons.routers, label: '设备管理' },
  { key: '/users', icon: menuIcons.users, label: '用户管理' },
  { key: '/plans', icon: menuIcons.plans, label: '套餐管理' },
  { key: '/vouchers', icon: menuIcons.vouchers, label: '卡密管理' },
  { key: '/usage', icon: menuIcons.usage, label: '用量报表' },
  { key: '/audit', icon: menuIcons.audit, label: '审计日志' },
  { key: '/branding', icon: menuIcons.branding, label: 'Logo 设置' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: branding } = useBranding();

  return (
    <div className="app-bg">
      <aside className="floating-sider">
        <div className="floating-sider__brand">
          {branding?.admin_logo ? (
            <img src={branding.admin_logo} alt="" className="floating-sider__brand-logo" />
          ) : null}
          <span>{branding?.site_title || 'NDS 管理'}</span>
        </div>
        <Menu
          className="floating-sider__menu"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </aside>

      <div className="app-main">
        <header className="app-header">
          <div
            className="app-header__logout"
            onClick={() => { localStorage.removeItem('admin_token'); navigate('/login'); }}
          >
            <LogoutIcon />
            <span>退出登录</span>
          </div>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
