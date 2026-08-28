import { List, SpinLoading } from 'antd-mobile';
import { useQuery } from '@tanstack/react-query';
import { userApi } from '../api';

export default function DevicesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: () => userApi.getDevices().then(r => r.data),
  });

  if (isLoading) return <div style={{ textAlign: 'center', padding: 80 }}><SpinLoading /></div>;

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ marginBottom: 12 }}>已绑定设备</h3>
      <p style={{ color: '#999', fontSize: 13, marginBottom: 12 }}>
        同一账户可绑定多个设备，但同时仅允许 1 台在线
      </p>
      <List>
        {data?.map(d => (
          <List.Item key={d.id} description={`首次: ${d.first_seen}`} extra={d.mac}>
            {d.mac}
          </List.Item>
        ))}
        {(!data || data.length === 0) && (
          <List.Item>暂无绑定设备，连接 WiFi 并登录后自动绑定</List.Item>
        )}
      </List>
    </div>
  );
}
