import { SpinLoading } from 'antd-mobile';
import { ReactNode } from 'react';

export type PageVariant = 'home' | 'recharge' | 'plans' | 'usage';

interface PageHeroProps {
  title: string;
  subtitle: string;
  icon: ReactNode;
  variant?: PageVariant;
  extra?: ReactNode;
  headerAction?: ReactNode;
}

export function PageHero({ title, subtitle, icon, variant = 'plans', extra, headerAction }: PageHeroProps) {
  return (
    <header className={`page-hero page-hero--${variant}`}>
      <div className="page-hero__decor" aria-hidden>
        <span className="page-hero__orb page-hero__orb--1" />
        <span className="page-hero__orb page-hero__orb--2" />
        <span className="page-hero__orb page-hero__orb--3" />
      </div>
      {headerAction && <div className="page-hero__action">{headerAction}</div>}
      <div className="page-hero__content">
        <div className="page-hero__icon">{icon}</div>
        <h1 className="page-hero__title">{title}</h1>
        <p className="page-hero__subtitle">{subtitle}</p>
        {extra}
      </div>
    </header>
  );
}

export function PageLoading() {
  return (
    <div className="page-loading">
      <SpinLoading color="primary" />
    </div>
  );
}

export function EmptyState({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">{icon}</div>
      <p className="empty-state__title">{title}</p>
      <p className="empty-state__desc">{description}</p>
    </div>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="section-title">
      <span className="section-title__text">{children}</span>
      {action}
    </div>
  );
}

export function StepGuide({ steps }: { steps: { num: string; title: string; desc: string }[] }) {
  return (
    <div className="step-guide">
      {steps.map((s, i) => (
        <div key={s.num} className="step-guide__item">
          <div className="step-guide__num">{s.num}</div>
          {i < steps.length - 1 && <div className="step-guide__line" />}
          <div className="step-guide__body">
            <span className="step-guide__title">{s.title}</span>
            <span className="step-guide__desc">{s.desc}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
