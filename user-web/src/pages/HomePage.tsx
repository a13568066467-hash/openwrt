import { useQuery } from '@tanstack/react-query';
import { Card, Grid, SpinLoading } from 'antd-mobile';
import { useNavigate } from 'react-router-dom';
import { userApi, formatBytes } from '../api';

function QuotaRing({ percent, label }: { percent: number; label: string }) {
  const size = 160;
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 0' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="#eee" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="#1677ff" strokeWidth={stroke}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <div style={{ marginTop: -100, textAlign: 'center' }}>
        <div style={{ fontSize: 32, fontWeight: 700, color: '#1677ff' }}>{label}</div>
        <div style={{ fontSize: 14, color: '#999', marginTop: 4 }}>剩余流量</div>
      </div>
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const { data: user, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => userApi.getProfile().then(r => r.data),
  });

  if (isLoading) return <div style={{ textAlign: 'center', padding: 80 }}><SpinLoading /></div>;

  const totalMB = 1024;
  const remainingMB = (user?.quota_remaining_bytes || 0) / 1024 / 1024;
  const percent = Math.min(100, (remainingMB / totalMB) * 100);

  return (
    <div style={{ padding: 16 }}>
      <Card title={`你好，${user?.username}`}>
        <QuotaRing percent={percent} label={formatBytes(user?.quota_remaining_bytes || 0)} />
      </Card>

      <Grid columns={2} gap={12} style={{ marginTop: 16 }}>
        <Grid.Item>
          <Card onClick={() => navigate('/recharge')} style={{ textAlign: 'center', cursor: 'pointer' }}>
            <div style={{ fontSize: 32 }}>💳</div>
            <div>卡密充值</div>
          </Card>
        </Grid.Item>
        <Grid.Item>
          <Card onClick={() => navigate('/plans')} style={{ textAlign: 'center', cursor: 'pointer' }}>
            <div style={{ fontSize: 32 }}>📦</div>
            <div>流量套餐</div>
          </Card>
        </Grid.Item>
        <Grid.Item>
          <Card onClick={() => navigate('/usage')} style={{ textAlign: 'center', cursor: 'pointer' }}>
            <div style={{ fontSize: 32 }}>📊</div>
            <div>消费明细</div>
          </Card>
        </Grid.Item>
        <Grid.Item>
          <Card onClick={() => navigate('/devices')} style={{ textAlign: 'center', cursor: 'pointer' }}>
            <div style={{ fontSize: 32 }}>📱</div>
            <div>我的设备</div>
          </Card>
        </Grid.Item>
      </Grid>
    </div>
  );
}
