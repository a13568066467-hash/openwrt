import { useState } from 'react';
import type { CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { userApi, formatTrafficMB, formatSpeed, Plan } from '../api';
import { PageHero, PageLoading, SectionTitle } from '../components/PageShell';
import { PlansTabIcon } from '../components/icons/TabBarIcons';

const PLAN_THEMES = ['#1296db', '#6c5ce7', '#00b894', '#fd9644', '#e17055'];
const INITIAL_VISIBLE = 2;

function PlanCard({
  plan,
  theme,
  featured,
  compact,
  onRecharge,
}: {
  plan: Plan;
  theme: string;
  featured: boolean;
  compact?: boolean;
  onRecharge: () => void;
}) {
  const watermark = formatTrafficMB(plan.traffic_mb);
  const price = (plan.price_cents / 100).toFixed(plan.price_cents % 100 === 0 ? 0 : 2);
  const perGb = plan.traffic_mb >= 1024
    ? `¥${((plan.price_cents / 100) / (plan.traffic_mb / 1024)).toFixed(2)}/GB`
    : `¥${((plan.price_cents / 100) / plan.traffic_mb * 1024).toFixed(2)}/GB`;

  if (compact) {
    return (
      <article
        className="plan-card plan-card--compact"
        style={{ '--plan-accent': theme } as CSSProperties}
      >
        <div className="plan-card__stripe" />
        <div className="plan-card__compact-row">
          <div className="plan-card__compact-info">
            <span className="plan-card__name">{plan.name}</span>
            <span className="plan-card__compact-traffic">{watermark}</span>
          </div>
          <div className="plan-card__compact-right">
            <span className="plan-card__compact-price">¥{price}</span>
            <button type="button" className="plan-card__compact-btn" onClick={onRecharge}>
              充值
            </button>
          </div>
        </div>
      </article>
    );
  }

  return (
    <article
      className={`plan-card${featured ? ' plan-card--featured' : ''}`}
      style={{ '--plan-accent': theme } as CSSProperties}
    >
      <span
        className="plan-card__watermark"
        aria-hidden
        style={{ '--wm-chars': watermark.length } as CSSProperties}
      >
        {watermark}
      </span>
      {featured && <span className="plan-card__badge">热门推荐</span>}
      <div className="plan-card__stripe" />

      <div className="plan-card__head">
        <div>
          <h3 className="plan-card__name">{plan.name}</h3>
          <p className="plan-card__traffic">{watermark}</p>
          <p className="plan-card__unit">流量额度</p>
        </div>
        <div className="plan-card__price">
          <span className="plan-card__currency">¥</span>
          <span className="plan-card__amount">{price}</span>
        </div>
      </div>

      <div className="plan-card__meta">
        <span className="meta-chip meta-chip--up">↑ {formatSpeed(plan.upload_rate_kbps ?? 0)}</span>
        <span className="meta-chip meta-chip--down">↓ {formatSpeed(plan.download_rate_kbps ?? 0)}</span>
      </div>

      <div className="plan-card__footer">
        <span className="plan-card__per">{perGb}</span>
        <button type="button" className="plan-card__action" onClick={onRecharge}>
          去充值
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
            <path fill="currentColor" d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z" />
          </svg>
        </button>
      </div>
    </article>
  );
}

export default function PlansPage() {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: () => userApi.getPlans().then(r => r.data),
  });

  const plans = data ?? [];

  const featuredId = plans.length > 0
    ? plans.reduce((best, p) =>
        p.traffic_mb / p.price_cents > best.traffic_mb / best.price_cents ? p : best,
      ).id
    : null;

  const primaryPlans = plans.slice(0, INITIAL_VISIBLE);
  const extraPlans = plans.slice(INITIAL_VISIBLE);
  const hasMore = extraPlans.length > 0;

  if (isLoading) return <PageLoading />;

  return (
    <div className="page page--plans">
      <PageHero
        variant="plans"
        title="流量套餐"
        subtitle="多种规格任选，灵活满足上网需求"
        icon={<PlansTabIcon size={40} color="#fff" />}
        extra={
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat__value">{plans.length}</span>
              <span className="hero-stat__label">可选方案</span>
            </div>
            <div className="hero-stat__divider" />
            <div className="hero-stat">
              <span className="hero-stat__value">即买即用</span>
              <span className="hero-stat__label">卡密兑换</span>
            </div>
          </div>
        }
      />

      <div className="page-body page-body--with-tab">
        <div className="info-banner info-banner--gradient">
          <span className="info-banner__icon">✦</span>
          购买卡密后，在「充值」页输入即可到账
        </div>

        <SectionTitle
          action={hasMore && !expanded ? (
            <span className="section-title__hint">已展示 {INITIAL_VISIBLE} 个</span>
          ) : undefined}
        >
          全部套餐
        </SectionTitle>

        {plans.length === 0 ? (
          <div className="surface-card">
            <p className="text-muted" style={{ textAlign: 'center', padding: '32px 0' }}>暂无可用套餐</p>
          </div>
        ) : (
          <>
            <div className="plan-list">
              {primaryPlans.map((plan, idx) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  theme={PLAN_THEMES[idx % PLAN_THEMES.length]}
                  featured={plan.id === featuredId}
                  onRecharge={() => navigate('/recharge')}
                />
              ))}
            </div>

            {hasMore && (
              <div className="plan-more">
                <button
                  type="button"
                  className={`plan-more__toggle${expanded ? ' plan-more__toggle--open' : ''}`}
                  onClick={() => setExpanded(v => !v)}
                  aria-expanded={expanded}
                >
                  <span>
                    {expanded ? '收起套餐' : `展开其余 ${extraPlans.length} 个套餐`}
                  </span>
                  <svg className="plan-more__chevron" viewBox="0 0 24 24" width="18" height="18" aria-hidden>
                    <path fill="currentColor" d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
                  </svg>
                </button>

                <div className={`plan-more__panel${expanded ? ' plan-more__panel--open' : ''}`}>
                  <div className="plan-list plan-list--compact">
                    {extraPlans.map((plan, idx) => (
                      <PlanCard
                        key={plan.id}
                        plan={plan}
                        theme={PLAN_THEMES[(idx + INITIAL_VISIBLE) % PLAN_THEMES.length]}
                        featured={false}
                        compact
                        onRecharge={() => navigate('/recharge')}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
