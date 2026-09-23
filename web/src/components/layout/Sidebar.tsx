import { NavLink } from "react-router-dom";
import {
  Award, BookOpen, Briefcase, Compass, FileCheck2, FlaskConical, Gauge,
  GraduationCap, LayoutDashboard, MessagesSquare, PlusCircle, ShieldCheck,
  Sparkles, Trophy, Users,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useAuth } from "@/features/auth/useAuth";

type Item = { to: string; label: string; icon: typeof Gauge; end?: boolean };
type Group = {
  heading: string;
  items: Item[];
  requires?: "review_proposals" | "moderate" | "grant_roles";
};

const GROUPS: Group[] = [
  {
    heading: "",
    items: [{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    heading: "Projects",
    items: [
      { to: "/discover", label: "Discover projects", icon: Compass },
      { to: "/projects/new", label: "Propose a project", icon: PlusCircle },
      { to: "/projects", label: "My projects", icon: Briefcase },
    ],
  },
  {
    heading: "Collaboration",
    items: [
      { to: "/tasks", label: "My tasks", icon: FileCheck2 },
      { to: "/community", label: "Community", icon: MessagesSquare },
      { to: "/mentors", label: "Find a mentor", icon: GraduationCap },
    ],
  },
  {
    heading: "Evidence",
    items: [
      { to: "/contributions", label: "Contributions", icon: Sparkles },
      { to: "/ledger", label: "The ledger", icon: ShieldCheck },
    ],
  },
  {
    heading: "Recognition",
    items: [
      { to: "/portfolio", label: "My portfolio", icon: BookOpen },
      { to: "/achievements", label: "Achievements", icon: Award },
      { to: "/leaderboards", label: "Leaderboards", icon: Trophy },
      { to: "/showcase", label: "Showcase", icon: FlaskConical },
    ],
  },
  {
    heading: "Stewardship",
    requires: "review_proposals",
    items: [{ to: "/review-queue", label: "Review queue", icon: Users }],
  },
  {
    heading: "Administration",
    requires: "grant_roles",
    items: [{ to: "/administration", label: "Members and access", icon: ShieldCheck }],
  },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();

  return (
    <nav className="flex-1 overflow-y-auto px-3 pb-6" aria-label="Main">
      {GROUPS.filter((group) => !group.requires || can(group.requires)).map((group) => (
        <div key={group.heading || "root"} className="mb-5 first:mt-1">
          {group.heading ? (
            <h2 className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-sidebar-fg/55">
              {group.heading}
            </h2>
          ) : null}
          <ul className="space-y-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-sidebar-active text-sidebar-fg-active font-medium"
                        : "text-sidebar-fg hover:bg-white/5 hover:text-sidebar-fg-active",
                    )
                  }
                >
                  <item.icon className="size-4.5 shrink-0" aria-hidden />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
