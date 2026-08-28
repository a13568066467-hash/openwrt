import { Card, List, Tag, SpinLoading } from 'antd-mobile';
import { useQuery } from '@tanstack/react-query';
import { userApi } from '../api';

export default function PlansPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: () => userApi.getPlans().then(r => r.data),
  });

  if (isLoading) return <div style={{ textAlign: 'center', padding: 80 }}><SpinLoading /></div>;

  return (
    <div style={{ padding: 16 }}>
      <Card title="流量套餐">
        <p style={{ color: '#999', fontSize: 14, marginBottom: 12 }}>
          购买卡密后可在充值页兑换对应流量
        </p>
        <List>
          {data?.map(plan => (
            <List.Item
              key={plan.id}
              description={`${plan.traffic_mb} MB`}
              extra={<Tag color="primary">¥{(plan.price_cents / 100).toFixed(2)}</Tag>}
            >
              {plan.name}
            </List.Item>
          ))}
        </List>
      </Card>
    </div>
  );
}
