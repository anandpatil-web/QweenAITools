import type { ReactNode } from "react";

export type ToolId = "upscaler" | "skinfix";

const TOOLS: { id: ToolId; name: string }[] = [
  { id: "upscaler", name: "Image Upscaler" },
  { id: "skinfix", name: "Skin Fix" },
];

interface Props {
  children: ReactNode;
  activeTool: ToolId;
  onSelectTool: (id: ToolId) => void;
}

export function AppShell({ children, activeTool, onSelectTool }: Props) {
  return (
    <div className="qw-app">
      <header className="qw-topbar">
        <div className="qw-topbar__inner">
          <div className="qw-brand">
            <span className="qw-brand__mark">QWEEN</span>
            <span className="qw-brand__sub">AI Tools</span>
          </div>
          <nav className="qw-topnav">
            {TOOLS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`qw-topnav__link${t.id === activeTool ? " is-active" : ""}`}
                onClick={() => onSelectTool(t.id)}
              >
                {t.name}
              </button>
            ))}
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
