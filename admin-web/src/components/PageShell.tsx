import type { ReactNode } from 'react';

interface PageShellProps {
  title: string;
  extra?: ReactNode;
  children: ReactNode;
}

export default function PageShell({ title, extra, children }: PageShellProps) {
  return (
    <div className="page-shell">
      <div className="page-shell__header">
        <h2 className="page-shell__title">{title}</h2>
        {extra}
      </div>
      <div className="glass-panel">{children}</div>
    </div>
  );
}
