import { Link } from "react-router-dom";
import { Check, GitBranch, Users } from "lucide-react";
import { Card, Pill } from "@/components/ui";
import { Progress } from "@/components/ui/Progress";
import { ProjectArt } from "./ProjectArt";
import { cn } from "@/lib/cn";
import { PROJECT_STAGES, type ProjectSummary } from "@/api/types";

const STATUS_TONE: Record<string, "neutral" | "brand" | "ember" | "green" | "red" | "purple"> = {
  draft: "neutral",
  submitted: "ember",
  under_review: "ember",
  returned: "ember",
  declined: "red",
  recruiting: "brand",
  building: "purple",
  in_review: "purple",
  documenting: "purple",
  completed: "green",
  archived: "neutral",
  abandoned: "red",
};

export function StatusPill({ status, label }: { status?: string; label?: string }) {
  return (
    <Pill tone={STATUS_TONE[status ?? ""] ?? "neutral"}>{label ?? status ?? "—"}</Pill>
  );
}

/**
 * The seven-stage tracker.
 *
 * Shown on every project because the lifecycle is the thing that distinguishes
 * FORGE from a discussion forum, and a team that cannot see which stage it is
 * in cannot tell what it should be doing next.
 */
/**
 * The seven-stage tracker.
 *
 * Numbered circles with ticks for what is done, as in the mockup. Shown on
 * every project because the lifecycle is what distinguishes FORGE from a
 * discussion forum, and a team that cannot see which stage it is in cannot
 * tell what it should be doing next.
 *
 * `compact` renders the bar form used inside cards, where there is no room
 * for labels.
 */
export function StageTracker({ stage, compact }: { stage: number; compact?: boolean }) {
  if (compact) {
    return (
      <ol className="flex items-start gap-1">
        {PROJECT_STAGES.map((item) => {
          const done = item.number < stage;
          const current = item.number === stage;
          return (
            <li key={item.number} className="flex-1 min-w-0">
              <div
                className={cn(
                  "h-1.5 rounded-full",
                  done && "bg-emerald-500",
                  current && "bg-brand-600",
                  !done && !current && "bg-sunken",
                )}
              />
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <ol className="flex items-start">
      {PROJECT_STAGES.map((item, index) => {
        const done = item.number < stage;
        const current = item.number === stage;
        const last = index === PROJECT_STAGES.length - 1;

        return (
          <li key={item.number} className="flex-1 flex flex-col items-center min-w-0 relative">
            {/* The connector sits behind the circle and stops at the next one. */}
            {!last ? (
              <span
                aria-hidden
                className={cn(
                  "absolute top-4 left-1/2 w-full h-0.5",
                  done ? "bg-emerald-500" : "bg-sunken",
                )}
              />
            ) : null}

            <span
              className={cn(
                "relative z-10 grid place-items-center size-8 rounded-full text-xs font-bold border-2 transition-colors",
                done && "bg-emerald-500 border-emerald-500 text-white",
                current && "bg-brand-600 border-brand-600 text-white ring-4 ring-brand-600/15",
                !done && !current && "bg-card border-line text-muted",
              )}
            >
              {done ? <Check className="size-4" aria-hidden /> : item.number}
            </span>

            <span
              className={cn(
                "mt-2 text-[11px] font-medium text-center leading-tight px-0.5 truncate max-w-full",
                current ? "text-brand-600" : done ? "text-emerald-600" : "text-muted",
              )}
            >
              {item.label}
            </span>
            <span
              className={cn(
                "text-[10px] text-center",
                current ? "text-brand-600" : "text-muted",
              )}
            >
              {done ? "Complete" : current ? "In progress" : "Pending"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Rough completion of a project, as a percentage.
 *
 * Derived from the lifecycle stage rather than from tasks ticked off, because
 * a task list is optional on FORGE and a project that keeps its board
 * elsewhere would otherwise sit at zero forever. Stage 7 of 7 is the only
 * thing that reads 100%.
 */
export function projectProgress(stage: number): number {
  return Math.round((Math.max(stage, 1) / 7) * 100);
}

export function ProjectCard({
  project,
  showProgress = true,
}: {
  project: ProjectSummary;
  showProgress?: boolean;
}) {
  const openRoles = project.open_roles ?? 0;
  const area = project.discipline_areas?.[0];
  const progress = projectProgress(project.stage ?? 1);

  return (
    <Card className="flex flex-col overflow-hidden hover:border-brand-300 hover:shadow-md transition-all group">
      <Link to={`/projects/${project.slug}`} className="flex flex-col flex-1">
        <ProjectArt
          slug={project.slug ?? ""}
          title={project.title ?? ""}
          areaSlug={area?.slug}
          className="h-28 shrink-0"
          compact
        />

        <div className="p-4 flex-1 flex flex-col">
          <div className="flex flex-wrap items-center gap-1.5 mb-2">
            {project.discipline_areas?.slice(0, 2).map((item) => (
              <Pill key={item.id} tone="brand">
                {item.name}
              </Pill>
            ))}
            {project.is_cross_disciplinary ? (
              <Pill tone="purple" icon={<GitBranch className="size-3" aria-hidden />}>
                Cross-school
              </Pill>
            ) : null}
          </div>

          <h3 className="font-semibold text-strong leading-snug line-clamp-2 group-hover:text-brand-600 transition-colors">
            {project.title}
          </h3>
          <p className="text-sm text-muted mt-1.5 line-clamp-2 flex-1">{project.summary}</p>

          {showProgress ? (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-muted">
                  Stage {project.stage} of 7 · {project.status_display}
                </span>
              </div>
              <Progress
                value={progress}
                showValue
                tone={project.status === "completed" ? "green" : "brand"}
                label={`${project.title} progress`}
              />
            </div>
          ) : null}

          <div className="flex items-center justify-between mt-4 pt-3.5 border-t border-line">
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <Users className="size-3.5" aria-hidden />
              {project.team_size ?? 0} {project.team_size === 1 ? "member" : "members"}
            </span>
            {openRoles > 0 ? (
              <Pill tone="green">
                {openRoles} open {openRoles === 1 ? "role" : "roles"}
              </Pill>
            ) : (
              <StatusPill status={project.status} label={project.status_display} />
            )}
          </div>
        </div>
      </Link>
    </Card>
  );
}
