import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="qw-app">
      <header className="qw-topbar">
        <div className="qw-topbar__inner">
          <div className="qw-brand">
            <span className="qw-brand__mark">QWEEN</span>
            <span className="qw-brand__sub">AI Tools</span>
          </div>
          <nav className="qw-topnav">
            <span className="is-active">Image Upscaler</span>
          </nav>
        </div>
      </header>
      <main className="qw-main">{children}</main>
      <footer className="qw-footer">
        QWEEN AI Tools · Internal · Crafted for the creative team
      </footer>
    </div>
  );
}
