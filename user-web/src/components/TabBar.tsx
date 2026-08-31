import { useLocation, useNavigate } from 'react-router-dom';
import { TabBar as AntTabBar } from 'antd-mobile';
import { tabBarIcons } from './icons/TabBarIcons';

export default function TabBar() {
  const location = useLocation();
  const navigate = useNavigate();

  const tabs = [
    { key: '/', title: '首页', icon: tabBarIcons.home },
    { key: '/recharge', title: '充值', icon: tabBarIcons.recharge },
    { key: '/plans', title: '套餐', icon: tabBarIcons.plans },
    { key: '/usage', title: '明细', icon: tabBarIcons.usage },
  ];

  if (location.pathname === '/login') return null;

  return (
    <div className="app-tab-bar-wrap">
      <AntTabBar activeKey={location.pathname} onChange={navigate} className="app-tab-bar">
        {tabs.map(t => (
          <AntTabBar.Item key={t.key} icon={t.icon} title={t.title} />
        ))}
      </AntTabBar>
    </div>
  );
}
