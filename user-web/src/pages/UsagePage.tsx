import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { userApi, formatBytes, formatRecordTime, formatRecordDate, UsageRecord } from '../api';
import { PageHero, PageLoading, EmptyState, SectionTitle } from '../components/PageShell';
import { UsageTabIcon } from '../components/icons/TabBarIcons';

function groupByDate(records: UsageRecord[]) {
  const groups = new Map<string, UsageRecord[]>();
  for (const r of records) {
    const key = formatRecordDate(r.recorded_at);
    const list = groups.get(key) ?? [];
    list.push(r);
    groups.set(key, list);
  }
  return groups;
}

function UsageBar({ records }: { records: UsageRecord[] }) {
  const last7 = useMemo(() => {
    const buckets = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (6 - i));
      d.setHours(0, 0, 0, 0);
      return { date: d, bytes: 0 };
    });
    for (const r of records) {
      const d = new Date(r.recorded_at);
      d.setHours(0, 0, 0, 0);
      const bucket = buckets.find(b => b.date.getTime() === d.getTime());
      if (bucket) bucket.bytes += Math.abs(r.delta_bytes);
    }
    const max = Math.max(...buckets.map(b => b.bytes), 1);
    return buckets.map(b => ({
      label: b.date.toLocaleDateString('zh-CN', { weekday: 'short' }).replace('星期', '周'),
      pct: (b.bytes / max) * 100,
      bytes: b.bytes,
    }));
  }, [records]);

  if (records.length === 0) return null;

  return (
    <div className="usage-chart">
      <SectionTitle>近 7 日消耗</SectionTitle>
      <div className="usage-chart__bars">
        {last7.map(b => (
          <div key={b.label} className="usage-chart__col">
            <div className="usage-chart__track">
              <div
                className="usage-chart__fill"
                style={{ height: `${Math.max(b.pct, b.bytes > 0 ? 8 : 0)}%` }}
                title={formatBytes(b.bytes)}
              />
            </div>
            <span className="usage-chart__label">{b.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function UsagePage() {
  const navigate = useNavigate();
  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: () => userApi.getProfile().then(r => r.data),
  });
  const { data, isLoading } = useQuery({
    queryKey: ['usage'],
    queryFn: () => userApi.getUsage().then(r => r.data),
  });

  const records = data ?? [];

  const totalConsumed = useMemo(
    () => records.reduce((sum, r) => sum + Math.abs(r.delta_bytes), 0),
    [records],
  );

  const todayConsumed = useMemo(() => {
    const today = new Date().toDateString();
    return records
      .filter(r => new Date(r.recorded_at).toDateString() === today)
      .reduce((sum, r) => sum + Math.abs(r.delta_bytes), 0);
  }, [records]);

  const grouped = useMemo(() => groupByDate(records), [records]);

  if (isLoading) return <PageLoading />;

  const remaining = profile?.quota_remaining_bytes ?? 0;

  return (
    <div className="page page--usage">
      <PageHero
        variant="usage"
        title="消费明细"
        subtitle="掌握每一笔流量去向"
        icon={<UsageTabIcon size={40} color="#fff" />}
        extra={
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat__value">{formatBytes(remaining)}</span>
              <span className="hero-stat__label">剩余流量</span>
            </div>
            <div className="hero-stat__divider" />
            <div className="hero-stat">
              <span className="hero-stat__value">{formatBytes(todayConsumed)}</span>
              <span className="hero-stat__label">今日消耗</span>
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
            <span className="stat-card__label">消费笔数</span>
          </div>
          <div className="stat-card stat-card--accent">
            <span className="stat-card__icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="#fff" d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>
            </span>
            <span className="stat-card__value">{formatBytes(totalConsumed)}</span>
            <span className="stat-card__label">累计消耗</span>
          </div>
        </div>

        <UsageBar records={records} />

        {records.length === 0 ? (
          <div className="surface-card surface-card--dashed">
            <EmptyState
              icon={<UsageTabIcon size={64} color="#b8dff5" />}
              title="暂无消费记录"
              description="连接 WiFi 上网后，流量消耗将自动记录在这里"
            />
            <button type="button" className="empty-state__cta" onClick={() => navigate('/recharge')}>
              去充值流量
            </button>
          </div>
        ) : (
          <div className="timeline">
            <SectionTitle>消费记录</SectionTitle>
            {[...grouped.entries()].map(([date, items]) => (
              <section key={date} className="timeline__group">
                <div className="timeline__date-row">
                  <span className="timeline__date">{date}</span>
                  <span className="timeline__date-total">
                    -{formatBytes(items.reduce((s, r) => s + Math.abs(r.delta_bytes), 0))}
                  </span>
                </div>
                <div className="timeline__list">
                  {items.map((r, i) => (
                    <div key={r.id} className="usage-item">
                      <div className="usage-item__rail">
                        <span className="usage-item__dot" />
                        {i < items.length - 1 && <span className="usage-item__line" />}
                      </div>
                      <div className="usage-item__icon">
                        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
                          <path fill="currentColor" d="M13 2.05v2.02c3.95.49 7 3.85 7 7.93 0 3.21-1.92 6-4.72 7.28L13 17v5h5v-5.07c3.5-.98 6-4.12 6-7.93 0-4.42-3.58-8-8-8zM4 12c0-4.08 3.05-7.44 7-7.93V2.05C5.58 2.56 2 6.14 2 11c0 3.79 2.4 7.03 5.78 8.28L7 22h5v-5.07C9.5 15.95 7 12.71 7 9H4z" />
                        </svg>
                      </div>
                      <div className="usage-item__body">
                        <span className="usage-item__title">流量消耗</span>
                        <span className="usage-item__time">{formatRecordTime(r.recorded_at)}</span>
                      </div>
                      <span className="usage-item__amount">-{formatBytes(Math.abs(r.delta_bytes))}</span>
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
