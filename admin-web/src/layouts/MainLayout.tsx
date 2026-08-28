import { Layout, Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  CloudServerOutlined, UserOutlined, GiftOutlined,
  KeyOutlined, BarChartOutlined, AuditOutlined, LogoutOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

const items = [
  { key: '/routers', icon: <CloudServerOutlined />, label: '设备管理' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
  { key: '/plans', icon: <GiftOutlined />, label: '套餐管理' },
  { key: '/vouchers', icon: <KeyOutlined />, label: '卡密管理' },
  { key: '/usage', icon: <BarChartOutlined />, label: '用量报表' },
  { key: '/audit', icon: <AuditOutlined />, label: '审计日志' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={220}>
        <div style={{ color: '#fff', padding: '16px 24px', fontSize: 18, fontWeight: 600 }}>
          NDS 管理
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
          <LogoutOutlined
            style={{ cursor: 'pointer', fontSize: 16 }}
            onClick={() => { localStorage.removeItem('admin_token'); navigate('/login'); }}
          />
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
