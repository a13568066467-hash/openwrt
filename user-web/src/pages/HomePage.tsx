import { Dialog } from 'antd-mobile';
import type { CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { userApi, formatTraffic, formatSpeed } from '../api';
import { PageHero, PageLoading, SectionTitle } from '../components/PageShell';
import {
  HomeTabIcon,
  RechargeTabIcon,
  PlansTabIcon,
  UsageTabIcon,
  DevicesIcon,
} from '../components/icons/TabBarIcons';

function QuotaRing({ percent, label }: { percent: number; label: string }) {
  const size = 140;
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, Math.max(0, percent)) / 100) * circumference;

  return (
    <div className="quota-ring">
      <svg className="quota-ring__svg" width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          className="quota-ring__track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
        />
        <circle
          className="quota-ring__progress"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="quota-ring__center">
        <span className="quota-ring__value">{label}</span>
        <span className="quota-ring__label">剩余流量</span>
      </div>
    </div>
  );
}

const SHORTCUTS = [
  {
    path: '/recharge',
    label: '卡密充值',
    desc: '输入卡密兑换流量',
    Icon: RechargeTabIcon,
    accent: '#0abde3',
  },
  {
    path: '/plans',
    label: '流量套餐',
    desc: '查看可选方案',
    Icon: PlansTabIcon,
    accent: '#6c5ce7',
  },
  {
    path: '/usage',
    label: '消费明细',
    desc: '流量使用记录',
    Icon: UsageTabIcon,
    accent: '#1296db',
  },
  {
    path: '/devices',
    label: '我的设备',
    desc: '管理绑定设备',
    Icon: DevicesIcon,
    accent: '#00b894',
  },
] as const;

export default function HomePage() {
  const navigate = useNavigate();
  const { data: user, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => userApi.getProfile().then(r => r.data),
  });

  if (isLoading) return <PageLoading />;

  const remaining = user?.quota_remaining_bytes ?? 0;
  const remainingMB = remaining / 1024 / 1024;
  const percent = Math.min(100, (remainingMB / 1024) * 100);
  const isActive = user?.status === 'active';

  const handleLogout = () => {
    Dialog.confirm({
      content: '确认退出当前账号？',
      confirmText: '退出',
      cancelText: '取消',
      onConfirm: () => {
        localStorage.removeItem('user_token');
        navigate('/login', { replace: true });
      },
    });
  };

  return (
    <div className="page page--home">
      <PageHero
        variant="home"
        title={`你好，${user?.username ?? '用户'}`}
        subtitle="连接 WiFi，畅享高速上网"
        icon={<HomeTabIcon size={40} color="#fff" />}
        headerAction={
          <button type="button" className="hero-logout-btn" onClick={handleLogout}>
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
              <path
                fill="currentColor"
                d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"
              />
            </svg>
            退出
          </button>
        }
        extra={
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat__value">{formatTraffic(remaining)}</span>
              <span className="hero-stat__label">可用流量</span>
            </div>
            <div className="hero-stat__divider" />
            <div className="hero-stat">
              <span className="hero-stat__value">{isActive ? '正常' : '受限'}</span>
              <span className="hero-stat__label">账户状态</span>
            </div>
          </div>
        }
      />

      <div className="page-body page-body--with-tab">
        <div className="quota-card surface-card">
          <QuotaRing percent={percent} label={formatTraffic(remaining)} />
          <div className="quota-card__speeds">
            <span className="quota-speed quota-speed--up">
              ↑ {formatSpeed(user?.upload_rate_kbps ?? 0)}
            </span>
            <span className="quota-speed quota-speed--down">
              ↓ {formatSpeed(user?.download_rate_kbps ?? 0)}
            </span>
          </div>
        </div>

        <SectionTitle>快捷服务</SectionTitle>
        <div className="shortcut-grid">
          {SHORTCUTS.map(({ path, label, desc, Icon, accent }) => (
            <button
              key={path}
              type="button"
              className="shortcut-card"
              style={{ '--shortcut-accent': accent } as CSSProperties}
              onClick={() => navigate(path)}
            >
              <span className="shortcut-card__icon">
                <Icon size={28} color={accent} />
              </span>
              <span className="shortcut-card__label">{label}</span>
              <span className="shortcut-card__desc">{desc}</span>
              <svg className="shortcut-card__arrow" viewBox="0 0 24 24" width="14" height="14" aria-hidden>
                <path fill="currentColor" d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z" />
              </svg>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
