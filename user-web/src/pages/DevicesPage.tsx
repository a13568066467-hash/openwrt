import { useQuery } from '@tanstack/react-query';
import { userApi } from '../api';
import { PageHero, PageLoading, EmptyState, SectionTitle } from '../components/PageShell';
import { DevicesIcon } from '../components/icons/TabBarIcons';

function formatWhen(iso: string | undefined) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('zh-CN', { hour12: false });
}

function deviceTitle(name: string | undefined, _mac: string) {
  const n = (name || '').trim();
  if (n && n !== '*') return n;
  return '未命名设备';
}

export default function DevicesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: () => userApi.getDevices().then(r => r.data),
  });

  if (isLoading) return <PageLoading />;

  const devices = data ?? [];

  return (
    <div className="page page--devices">
      <PageHero
        variant="plans"
        title="我的设备"
        subtitle="同一账户可绑定多台设备，同时仅允许 1 台在线"
        icon={<DevicesIcon size={40} color="#fff" />}
        extra={
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat__value">{devices.length}</span>
              <span className="hero-stat__label">已绑定</span>
            </div>
          </div>
        }
      />

      <div className="page-body">
        <SectionTitle>已绑定设备</SectionTitle>
        {devices.length === 0 ? (
          <EmptyState
            icon={<DevicesIcon size={36} color="#8c9aab" />}
            title="暂无绑定设备"
            description="连接 WiFi 并完成认证后，本机会自动绑定"
          />
        ) : (
          <div className="device-list">
            {devices.map(d => (
              <div key={d.id} className="device-card">
                <div className="device-card__icon" aria-hidden>
                  <DevicesIcon size={22} color="#1296db" />
                </div>
                <div className="device-card__body">
                  <div className="device-card__name">{deviceTitle(d.name, d.mac)}</div>
                  <div className="device-card__mac">{d.mac}</div>
                  <div className="device-card__meta">
                    <span>首次 {formatWhen(d.first_seen)}</span>
                    <span>最近 {formatWhen(d.last_seen)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
