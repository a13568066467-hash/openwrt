import { useLocation, useNavigate } from 'react-router-dom';
import { TabBar as AntTabBar } from 'antd-mobile';
import { AppOutline, UnorderedListOutline, PayCircleOutline, SetOutline } from 'antd-mobile-icons';

export default function TabBar() {
  const location = useLocation();
  const navigate = useNavigate();

  const tabs = [
    { key: '/', title: '首页', icon: <AppOutline /> },
    { key: '/recharge', title: '充值', icon: <PayCircleOutline /> },
    { key: '/plans', title: '套餐', icon: <UnorderedListOutline /> },
    { key: '/usage', title: '明细', icon: <SetOutline /> },
  ];

  if (location.pathname === '/login') return null;

  return (
    <AntTabBar activeKey={location.pathname} onChange={navigate} style={{ position: 'fixed', bottom: 0, width: '100%', maxWidth: 430 }}>
      {tabs.map(t => (
        <AntTabBar.Item key={t.key} icon={t.icon} title={t.title} />
      ))}
    </AntTabBar>
  );
}
