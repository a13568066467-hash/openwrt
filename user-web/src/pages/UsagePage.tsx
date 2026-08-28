import { List, SpinLoading } from 'antd-mobile';
import { useQuery } from '@tanstack/react-query';
import { userApi, formatBytes } from '../api';

export default function UsagePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['usage'],
    queryFn: () => userApi.getUsage().then(r => r.data),
  });

  if (isLoading) return <div style={{ textAlign: 'center', padding: 80 }}><SpinLoading /></div>;

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ marginBottom: 12 }}>消费明细</h3>
      <List>
        {data?.map(r => (
          <List.Item
            key={r.id}
            description={r.recorded_at}
            extra={<span style={{ color: '#ff4d4f' }}>-{formatBytes(r.delta_bytes)}</span>}
          >
            流量消耗
          </List.Item>
        ))}
        {(!data || data.length === 0) && (
          <List.Item>暂无消费记录</List.Item>
        )}
      </List>
    </div>
  );
}
