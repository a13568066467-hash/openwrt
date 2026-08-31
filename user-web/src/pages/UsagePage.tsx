import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  userApi,
  formatBytes,
  formatRecordTime,
  formatRecordDate,
  formatTrafficMB,
  RedeemedVoucher,
} from '../api';
import { PageHero, PageLoading, EmptyState, SectionTitle } from '../components/PageShell';
import { UsageTabIcon } from '../components/icons/TabBarIcons';

function groupByDate(records: RedeemedVoucher[]) {
  const groups = new Map<string, RedeemedVoucher[]>();
  for (const r of records) {
    const key = r.redeemed_at ? formatRecordDate(r.redeemed_at) : '未知日期';
    const list = groups.get(key) ?? [];
    list.push(r);
    groups.set(key, list);
  }
  return groups;
}

export default function UsagePage() {
  const navigate = useNavigate();
  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: () => userApi.getProfile().then(r => r.data),
  });
  const { data, isLoading } = useQuery({
    queryKey: ['redeemed-vouchers'],
    queryFn: () => userApi.getRedeemedVouchers().then(r => r.data),
  });

  const records = data ?? [];

  const totalRedeemedMB = useMemo(
    () => records.reduce((sum, r) => sum + r.traffic_mb, 0),
    [records],
  );

  const grouped = useMemo(() => groupByDate(records), [records]);

  if (isLoading) return <PageLoading />;

  const remaining = profile?.quota_remaining_bytes ?? 0;

  return (
    <div className="page page--usage">
      <PageHero
        variant="usage"
        title="兑换明细"
        subtitle="查看已兑换的卡密套餐与流量"
        icon={<UsageTabIcon size={40} color="#fff" />}
        extra={
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat__value">{formatBytes(remaining)}</span>
              <span className="hero-stat__label">剩余流量</span>
            </div>
            <div className="hero-stat__divider" />
            <div className="hero-stat">
              <span className="hero-stat__value">{formatTrafficMB(totalRedeemedMB)}</span>
              <span className="hero-stat__label">累计兑换</span>
            </div>
          </div>
        }
      />

      <div className="page-body">
        <div className="stat-row">
          <div className="stat-card stat-card--glass">
            <span className="stat-card__icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="#1296db" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14H7v-2h5v2zm5-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
            </span>
            <span className="stat-card__value">{records.length}</span>
            <span className="stat-card__label">兑换笔数</span>
          </div>
          <div className="stat-card stat-card--accent">
            <span className="stat-card__icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="#fff" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            </span>
            <span className="stat-card__value">{formatTrafficMB(totalRedeemedMB)}</span>
            <span className="stat-card__label">累计兑换流量</span>
          </div>
        </div>

        {records.length === 0 ? (
          <div className="surface-card surface-card--dashed">
            <EmptyState
              icon={<UsageTabIcon size={64} color="#b8dff5" />}
              title="暂无已兑换卡密"
              description="在充值页输入卡密兑换后，记录将显示在这里"
            />
            <button type="button" className="empty-state__cta" onClick={() => navigate('/recharge')}>
              去充值兑换
            </button>
          </div>
        ) : (
          <div className="timeline">
            <SectionTitle>已兑换的卡密套餐</SectionTitle>
            {[...grouped.entries()].map(([date, items]) => (
              <section key={date} className="timeline__group">
                <div className="timeline__date-row">
                  <span className="timeline__date">{date}</span>
                  <span className="timeline__date-total timeline__date-total--gain">
                    +{formatTrafficMB(items.reduce((s, r) => s + r.traffic_mb, 0))}
                  </span>
                </div>
                <div className="timeline__list">
                  {items.map((r, i) => (
                    <div key={r.id} className="usage-item usage-item--gain">
                      <div className="usage-item__rail">
                        <span className="usage-item__dot usage-item__dot--gain" />
                        {i < items.length - 1 && <span className="usage-item__line" />}
                      </div>
                      <div className="usage-item__icon usage-item__icon--gain">
                        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
                          <path fill="currentColor" d="M20 4H4c-1.11 0-2 .89-2 2v12c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4V6h16v12zM6 10h2v2H6v-2zm0 4h8v2H6v-2zm10 0h2v2h-2v-2zm-4-4h8v2h-8v-2z" />
                        </svg>
                      </div>
                      <div className="usage-item__body">
                        <span className="usage-item__title">{r.batch_name || '卡密套餐'}</span>
                        <span className="usage-item__time">
                          {r.redeemed_at ? formatRecordTime(r.redeemed_at) : '—'}
                        </span>
                      </div>
                      <span className="usage-item__amount usage-item__amount--gain">
                        +{formatTrafficMB(r.traffic_mb)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
