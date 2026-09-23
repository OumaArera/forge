import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Bell, LogOut, Menu, Moon, Search, Sun, UserRound, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { useAuth } from "@/features/auth/useAuth";
import { useUnreadCount } from "@/api/queries";
import { Avatar, Pill } from "@/components/ui";
import { SidebarNav } from "./Sidebar";

function Logo({ className }: { className?: string }) {
  return (
    <Link to="/dashboard" className={cn("flex items-center gap-2.5", className)}>
      <img src="/forge-logo.png" srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x" alt="" className="size-8 shrink-0" />
      <span className="text-lg font-bold tracking-tight text-white">FORGE</span>
    </Link>
  );
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">(() => {
    try {
      return (localStorage.getItem("forge.theme") as "light" | "dark") ?? "system";
    } catch {
      return "system";
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      if (theme === "system") localStorage.removeItem("forge.theme");
      else localStorage.setItem("forge.theme", theme);
    } catch {
      /* a remembered theme is a convenience, not a requirement */
    }
  }, [theme]);

  const isDark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  return { isDark, toggle: () => setTheme(isDark ? "light" : "dark") };
}

export function AppShell() {
  const { member, signOut } = useAuth();
  const { data: unread } = useUnreadCount();
  const { isDark, toggle } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMenuOpen(false);
    setAccountOpen(false);
  }, [location.pathname]);

  const unreadTotal = unread?.total ?? 0;

  return (
    <div className="min-h-dvh bg-page">
      {/* Skip link: the sidebar is long and keyboard users should not have to
          tab through it on every page. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-3 focus:left-3 focus:rounded-lg focus:bg-brand-600 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      {/* Sidebar — permanent from lg, a drawer below it. */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 bg-sidebar flex flex-col transition-transform lg:translate-x-0",
          menuOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between h-16 px-5 shrink-0">
          <Logo />
          <button
            onClick={() => setMenuOpen(false)}
            className="lg:hidden text-sidebar-fg p-1.5 -mr-1.5 rounded-lg hover:bg-white/5"
            aria-label="Close menu"
          >
            <X className="size-5" />
          </button>
        </div>
        <SidebarNav onNavigate={() => setMenuOpen(false)} />
      </aside>

      {menuOpen ? (
        <div
          className="fixed inset-0 z-30 bg-navy-950/60 lg:hidden"
          onClick={() => setMenuOpen(false)}
          aria-hidden
        />
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 h-16 bg-card/85 backdrop-blur border-b border-line">
          <div className="h-full px-4 sm:px-6 flex items-center gap-3">
            <button
              onClick={() => setMenuOpen(true)}
              className="lg:hidden p-2 -ml-2 rounded-lg text-body hover:bg-sunken"
              aria-label="Open menu"
            >
              <Menu className="size-5" />
            </button>

            <Link
              to="/discover"
              className="flex-1 max-w-md hidden sm:flex items-center gap-2 h-9 px-3 rounded-lg border border-line bg-sunken text-muted text-sm hover:border-brand-300 transition-colors"
            >
              <Search className="size-4 shrink-0" aria-hidden />
              <span>Search projects, people, skills…</span>
            </Link>

            <div className="flex-1 sm:hidden" />

            <button
              onClick={toggle}
              className="p-2 rounded-lg text-body hover:bg-sunken"
              aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
            >
              {isDark ? <Sun className="size-5" /> : <Moon className="size-5" />}
            </button>

            <Link
              to="/notifications"
              className="relative p-2 rounded-lg text-body hover:bg-sunken"
              aria-label={
                unreadTotal ? `Notifications, ${unreadTotal} unread` : "Notifications"
              }
            >
              <Bell className="size-5" />
              {unreadTotal > 0 ? (
                <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-red-500 text-[10px] font-bold text-white grid place-items-center tabular-nums">
                  {unreadTotal > 99 ? "99+" : unreadTotal}
                </span>
              ) : null}
            </Link>

            <div className="relative">
              <button
                onClick={() => setAccountOpen((open) => !open)}
                className="flex items-center gap-2.5 pl-1 pr-2 py-1 rounded-lg hover:bg-sunken"
                aria-expanded={accountOpen}
                aria-haspopup="menu"
              >
                <Avatar name={member?.display_name ?? "?"} src={member?.avatar} size={32} />
                <span className="hidden md:block text-left leading-tight">
                  <span className="block text-sm font-medium text-strong">
                    {member?.display_name}
                  </span>
                  <span className="block text-xs text-muted capitalize">{member?.kind}</span>
                </span>
              </button>

              {accountOpen ? (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-60 rounded-xl border border-line bg-card shadow-lg p-1.5"
                >
                  <div className="px-3 py-2.5 border-b border-line mb-1.5">
                    <p className="text-sm font-medium text-strong truncate">
                      {member?.full_name}
                    </p>
                    <p className="text-xs text-muted truncate">{member?.email}</p>
                    {member?.roles?.length ? (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {member.roles.slice(0, 3).map((role) => (
                          <Pill key={role} tone="brand" className="text-[10px]">
                            {role.replace(/_/g, " ")}
                          </Pill>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <Link
                    to="/settings"
                    role="menuitem"
                    className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-body hover:bg-sunken"
                  >
                    <UserRound className="size-4" aria-hidden />
                    Profile and settings
                  </Link>
                  <button
                    onClick={signOut}
                    role="menuitem"
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40"
                  >
                    <LogOut className="size-4" aria-hidden />
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main id="main" className="px-4 sm:px-6 py-6 max-w-[1400px] mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
