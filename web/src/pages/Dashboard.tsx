import { Link } from "react-router-dom";
import {
  ArrowRight, Award, Briefcase, CheckCheck, Compass, FileCheck2, PlusCircle,
  Search, Sparkles, TrendingUp, UserPlus, Users,
} from "lucide-react";
import {
  useAttestationQueue, useContributions, useMyProjects, useMyTasks, useReviewQueue,
  useStanding, useSuggestedRoles,
} from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import {
  Card, CardHeader, EmptyState, LinkButton, Loading, Pill, StatTile,
} from "@/components/ui";
import { Progress, ProgressRing } from "@/components/ui/Progress";
import { ProjectArt } from "@/features/projects/ProjectArt";
import { projectProgress } from "@/features/projects/bits";
import type { ProjectSummary } from "@/api/types";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const ACTIVE = ["recruiting", "building", "in_review", "documenting"];

export function Dashboard() {
  const { member, can } = useAuth();
  const projects = useMyProjects();
  const standing = useStanding();
  const attestations = useAttestationQueue();
  const tasks = useMyTasks();
  const suggestions = useSuggestedRoles();
  const reviews = useReviewQueue(can("review_proposals"));
  const contributions = useContributions({ page_size: 100 });

  const activeProjects = (projects.data?.results ?? []).filter((project) =>
    ACTIVE.includes(project.status ?? ""),
  );
  const pendingAttestations = attestations.data?.count ?? 0;
  const openTasks = tasks.data?.length ?? 0;

  // "This month" is counted client-side from what we already have, rather than
  // asking the server for a second aggregate the dashboard would then wait on.
  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const thisMonth = (contributions.data?.results ?? []).filter(
    (item) => item.created_at && new Date(item.created_at) >= monthStart,
  );
  const confirmedThisMonth = thisMonth.filter((item) => item.status === "confirmed");

  const next = standing.data?.next_level as
    | { name?: string; points_needed?: number }
    | null
    | undefined;
  const points = standing.data?.total_points ?? 0;
  const target = points + (next?.points_needed ?? 0);

  return (
    <div className="space-y-6">
      {/* Greeting band, with the platform's line on the right as in the mockup. */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-strong tracking-tight">
            {greeting()}, {member?.display_name?.split(" ")[0]}{" "}
            <span aria-hidden>👋</span>
          </h1>
          <p className="text-sm text-muted mt-1">Build. Collaborate. Demonstrate.</p>
        </div>
        <div className="hidden lg:block text-right">
          <p className="text-sm text-muted italic">
            "The future is built by those who do."
          </p>
          <p className="text-xs text-ember-600 font-semibold mt-0.5">— FORGE</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Active projects"
          value={activeProjects.length}
          icon={<Briefcase className="size-5" aria-hidden />}
        />
        <StatTile
          label="Contribution points"
          value={points}
          icon={<TrendingUp className="size-5" aria-hidden />}
          tone="green"
        />
        <StatTile
          label="Open tasks"
          value={openTasks}
          icon={<FileCheck2 className="size-5" aria-hidden />}
          tone="purple"
        />
        <Card className="p-4 flex items-center gap-3.5">
          <span className="grid place-items-center size-11 rounded-xl bg-ember-500 text-navy-950 shrink-0">
            <Award className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-lg font-bold text-strong leading-tight truncate">
              {standing.data?.level?.name ?? "Apprentice"}
            </div>
            <div className="text-xs text-muted">Current level</div>
            <Link
              to="/achievements"
              className="text-xs text-brand-600 font-medium hover:underline mt-1 inline-block"
            >
              View progress →
            </Link>
          </div>
        </Card>
      </div>

      {/*
        Action banners, ordered by whose time is being wasted. Confirmations
        first: a lead who is behind on them is a team whose portfolios are all
        empty, and nobody else can unblock it.
      */}
      {pendingAttestations > 0 ? (
        <Banner
          tone="ember"
          icon={<CheckCheck className="size-5" aria-hidden />}
          title={`${pendingAttestations} contribution${pendingAttestations === 1 ? "" : "s"} waiting on you`}
          body="Nothing enters anyone's portfolio until you and the mentor have both confirmed it."
          action={
            <LinkButton to="/contributions?tab=confirm" variant="ember" size="sm">
              Review them
            </LinkButton>
          }
        />
      ) : null}

      {member?.must_change_password ? (
        <Banner
          tone="brand"
          icon={<Sparkles className="size-5" aria-hidden />}
          title="Choose your own password"
          body="You are still signed in with the one we emailed you. Replace it and that one stops working."
          action={
            <LinkButton to="/settings" size="sm">
              Change it
            </LinkButton>
          }
        />
      ) : null}

      {can("review_proposals") && (reviews.data?.count ?? 0) > 0 ? (
        <Banner
          tone="brand"
          icon={<UserPlus className="size-5" aria-hidden />}
          title={`${reviews.data?.count} proposal${reviews.data?.count === 1 ? "" : "s"} awaiting review`}
          body="Students cannot recruit a team until someone has looked."
          action={
            <LinkButton to="/review-queue" size="sm">
              Open the queue
            </LinkButton>
          }
        />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-strong">Your active projects</h2>
            <Link
              to="/projects"
              className="text-sm text-brand-600 font-medium hover:underline flex items-center gap-1"
            >
              View all <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </div>

          {projects.isLoading ? (
            <Loading />
          ) : activeProjects.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Compass className="size-10" aria-hidden />}
                title="Nothing on the go yet"
                description="Join a team that needs what you can do, or propose something of your own. Most people start by joining."
                action={
                  <div className="flex flex-wrap gap-3 justify-center">
                    <LinkButton to="/discover">Find a project</LinkButton>
                    <LinkButton to="/projects/new" variant="secondary">
                      Propose one
                    </LinkButton>
                  </div>
                }
              />
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {activeProjects.slice(0, 6).map((project) => (
                <ActiveProjectCard key={project.id} project={project} />
              ))}
            </div>
          )}

          <Card className="overflow-hidden">
            <div className="relative bg-navy-900 p-6 sm:p-8">
              <div
                aria-hidden
                className="absolute -top-16 -right-10 size-56 rounded-full bg-brand-600/25 blur-3xl"
              />
              <div
                aria-hidden
                className="absolute -bottom-20 -left-10 size-56 rounded-full bg-ember-500/15 blur-3xl"
              />
              <div className="relative flex flex-wrap items-end justify-between gap-6">
                <div className="max-w-md">
                  <h3 className="text-xl font-bold text-white">From ideas to impact.</h3>
                  <p className="text-sm text-navy-200 mt-1.5">
                    Real projects. Real skills. A record you keep after you graduate.
                  </p>
                  <LinkButton to="/showcase" variant="ember" size="sm" className="mt-4">
                    Explore opportunities
                  </LinkButton>
                </div>
                <p className="text-ember-400 font-semibold text-sm italic hidden sm:block">
                  Students building a better Kenya
                </p>
              </div>
            </div>
          </Card>
        </section>

        <aside className="space-y-5">
          <Card>
            <CardHeader title="Your contribution this month" />
            <div className="p-5 pt-3 flex items-center gap-5">
              <ProgressRing
                value={points}
                max={target || 1}
                label={String(points)}
                sublabel="points"
              />
              <ul className="text-sm space-y-1.5 min-w-0">
                <Fact value={activeProjects.length} label="active projects" />
                <Fact value={thisMonth.length} label="contributions logged" />
                <Fact value={confirmedThisMonth.length} label="confirmed" />
                <Fact
                  value={standing.data?.people_mentored ?? 0}
                  label="mentorship entries"
                />
              </ul>
            </div>
            {next?.name ? (
              <div className="px-5 pb-5">
                <Progress
                  value={target ? (points / target) * 100 : 0}
                  tone="ember"
                  label={`Progress to ${next.name}`}
                />
                <p className="text-xs text-muted mt-2">
                  <span className="font-medium text-strong">
                    {next.points_needed ?? 0} points
                  </span>{" "}
                  to {next.name}. Every contribution counts.
                </p>
              </div>
            ) : null}
          </Card>

          <Card>
            <CardHeader title="Quick actions" />
            <div className="p-3 pt-1 space-y-0.5">
              <QuickAction to="/projects/new" icon={<PlusCircle className="size-4" aria-hidden />}>
                Propose a project
              </QuickAction>
              <QuickAction to="/discover" icon={<Search className="size-4" aria-hidden />}>
                Find a team to join
              </QuickAction>
              <QuickAction to="/contributions" icon={<Sparkles className="size-4" aria-hidden />}>
                Log a contribution
              </QuickAction>
              <QuickAction to="/mentors" icon={<Users className="size-4" aria-hidden />}>
                Find a mentor
              </QuickAction>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Roles that fit you"
              subtitle="Matched on your declared skills"
            />
            <div className="p-5 pt-3 space-y-2.5">
              {suggestions.isLoading ? (
                <Loading label="Matching" />
              ) : (suggestions.data ?? []).length === 0 ? (
                <p className="text-sm text-muted">
                  Nothing open that matches yet.{" "}
                  <Link to="/settings" className="text-brand-600 hover:underline">
                    Add your skills
                  </Link>{" "}
                  and we will keep looking.
                </p>
              ) : (
                (suggestions.data ?? []).slice(0, 4).map((role) => (
                  <Link
                    key={role.id}
                    to={`/projects/${role.project?.slug}`}
                    className="block rounded-lg border border-line p-3 hover:border-brand-300 hover:bg-sunken transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-strong leading-snug">
                        {role.title}
                      </p>
                      {role.open_to_beginners ? (
                        <Pill tone="green" className="shrink-0">
                          Beginner
                        </Pill>
                      ) : null}
                    </div>
                    <p className="text-xs text-muted mt-1 line-clamp-1">
                      {role.project?.title}
                    </p>
                  </Link>
                ))
              )}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function Fact({ value, label }: { value: number; label: string }) {
  return (
    <li className="flex items-baseline gap-1.5">
      <span className="font-semibold text-strong tabular-nums">{value}</span>
      <span className="text-muted truncate">{label}</span>
    </li>
  );
}

function QuickAction({
  to,
  icon,
  children,
}: {
  to: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-body hover:bg-sunken transition-colors"
    >
      <span className="text-brand-600">{icon}</span>
      {children}
    </Link>
  );
}

function Banner({
  tone,
  icon,
  title,
  body,
  action,
}: {
  tone: "ember" | "brand";
  icon: React.ReactNode;
  title: string;
  body: string;
  action: React.ReactNode;
}) {
  const styles =
    tone === "ember"
      ? "border-ember-300 bg-ember-50/60 dark:bg-ember-700/10"
      : "border-brand-300 bg-brand-50/60 dark:bg-brand-900/20";
  const badge = tone === "ember" ? "bg-ember-500 text-navy-950" : "bg-brand-600 text-white";

  return (
    <Card className={`p-4 sm:p-5 ${styles}`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <span className={`grid place-items-center size-10 rounded-xl shrink-0 ${badge}`}>
            {icon}
          </span>
          <div>
            <p className="font-semibold text-strong">{title}</p>
            <p className="text-sm text-body mt-0.5">{body}</p>
          </div>
        </div>
        {action}
      </div>
    </Card>
  );
}

/** A denser card than the discover grid uses: this one is about continuing. */
function ActiveProjectCard({ project }: { project: ProjectSummary }) {
  const progress = projectProgress(project.stage ?? 1);
  const area = project.discipline_areas?.[0];

  return (
    <Card className="overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      <ProjectArt
        slug={project.slug ?? ""}
        title={project.title ?? ""}
        areaSlug={area?.slug}
        className="h-24 shrink-0"
        compact
      />
      <div className="p-4 flex flex-col flex-1">
        <div className="flex flex-wrap gap-1.5 mb-2">
          {project.discipline_areas?.slice(0, 2).map((item) => (
            <Pill key={item.id} tone="brand">
              {item.name}
            </Pill>
          ))}
        </div>
        <h3 className="font-semibold text-strong text-sm leading-snug line-clamp-2">
          {project.title}
        </h3>
        <p className="text-xs text-muted mt-1 line-clamp-2 flex-1">{project.summary}</p>

        <div className="mt-3">
          <Progress value={progress} showValue label={`${project.title} progress`} />
        </div>

        <div className="flex items-center justify-between mt-3">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Users className="size-3.5" aria-hidden />
            {project.team_size ?? 0}
          </span>
          <Link
            to={`/projects/${project.slug}`}
            className="text-xs font-semibold text-brand-600 hover:underline"
          >
            Continue →
          </Link>
        </div>
      </div>
    </Card>
  );
}
