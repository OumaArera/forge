import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock, ExternalLink,
  FileCheck2, GitBranch, Globe, Plus, Users,
} from "lucide-react";
import { format } from "date-fns";
import { toForgeError } from "@/api/client";
import { useProject, useProjectHistory, useProjectMutations } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import {
  Avatar, Button, Card, CardHeader, ErrorState, Field, FormError, Loading, Pill,
  Textarea,
} from "@/components/ui";
import { Progress } from "@/components/ui/Progress";
import { ProjectArt } from "@/features/projects/ProjectArt";
import { StageTracker, StatusPill, projectProgress } from "@/features/projects/bits";
import { ReviewPanel } from "@/features/projects/ReviewPanel";
import { cn } from "@/lib/cn";

const TABS = ["Overview", "Team", "Activity"] as const;

export function ProjectDetail() {
  const { slug = "" } = useParams();
  const { member, can } = useAuth();
  const { data: project, isLoading, isError, refetch } = useProject(slug);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");

  if (isLoading) return <Loading label="Loading project" />;
  if (isError || !project)
    return (
      <ErrorState
        message="That project could not be loaded. It may be a draft that is not yours to see."
        onRetry={() => void refetch()}
      />
    );

  const isLead = project.my_role === "lead";
  const isMentor = project.my_role === "mentor";
  const isTeam = Boolean(project.my_role);
  const openRoles = (project.roles ?? []).filter((role) => role.has_vacancy);

  return (
    <div className="space-y-6">
      <nav className="text-sm text-muted mb-1" aria-label="Breadcrumb">
        <Link to="/discover" className="hover:text-brand-600">
          Projects
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-body">{project.title}</span>
      </nav>

      <div className="grid gap-5 lg:grid-cols-[260px_1fr] items-start">
        <ProjectArt
          slug={project.slug ?? ""}
          title={project.title ?? ""}
          areaSlug={project.discipline_areas?.[0]?.slug}
          className="h-40 lg:h-44 rounded-[--radius-card]"
        />

        <div className="min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 mb-2">
                {project.discipline_areas?.map((area) => (
                  <Pill key={area.id} tone="brand">
                    {area.name}
                  </Pill>
                ))}
                {project.is_cross_disciplinary ? (
                  <Pill tone="purple" icon={<GitBranch className="size-3" aria-hidden />}>
                    {project.school_spread} schools
                  </Pill>
                ) : null}
                <StatusPill status={project.status} label={project.status_display} />
              </div>
              <h1 className="text-2xl font-bold text-strong tracking-tight">
                {project.title}
              </h1>
              <p className="text-body mt-2 max-w-3xl">{project.summary}</p>
            </div>

            {isLead ? (
              <Link
                to={`/projects/${slug}/edit`}
                className="inline-flex items-center h-9 px-4 rounded-lg border border-line bg-card text-sm font-medium text-strong hover:bg-sunken shrink-0"
              >
                Edit project
              </Link>
            ) : null}
          </div>

          <div className="mt-4">
            <Progress
              value={projectProgress(project.stage ?? 1)}
              showValue
              tone={project.status === "completed" ? "green" : "brand"}
              label="Project progress"
            />
          </div>

          {/* The facts a visitor scans for before reading anything else. */}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-4 text-sm text-muted">
            <span className="flex items-center gap-1.5">
              <Users className="size-4" aria-hidden />
              {(project.memberships ?? []).length} members
            </span>
            <span className="flex items-center gap-1.5">
              <FileCheck2 className="size-4" aria-hidden />
              {openRoles.length} open roles
            </span>
            {project.effort_hours_per_week ? (
              <span className="flex items-center gap-1.5">
                <Clock className="size-4" aria-hidden />
                ~{project.effort_hours_per_week}h a week
              </span>
            ) : null}
            <span className="flex items-center gap-1.5">
              <Globe className="size-4" aria-hidden />
              {project.visibility === "public" ? "Public project" : "University only"}
            </span>
          </div>
        </div>
      </div>

      {project.is_stale && isTeam ? (
        <Card className="p-4 border-ember-300 bg-ember-50/60 dark:bg-ember-700/10 flex items-start gap-3">
          <AlertTriangle className="size-5 text-ember-600 shrink-0 mt-0.5" aria-hidden />
          <div>
            <p className="font-medium text-strong text-sm">This project has gone quiet</p>
            <p className="text-sm text-body mt-0.5">
              Post a progress update, hand it over, or close it. Any of the three is
              better than silence — after 60 days it is archived automatically.
            </p>
          </div>
        </Card>
      ) : null}

      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-strong">Project lifecycle</h2>
          <span className="text-xs text-muted">
            Stage {project.stage} of 7 — {project.status_display}
          </span>
        </div>
        <StageTracker stage={project.stage ?? 1} />
      </Card>

      {isLead || isMentor ? <LifecycleActions project={project} slug={slug} /> : null}

      {(project.status === "submitted" || project.status === "under_review") &&
      can("review_proposals") &&
      project.lead?.id !== member?.id ? (
        <ReviewPanel slug={slug} />
      ) : null}

      <div className="border-b border-line">
        <div className="flex gap-1 -mb-px" role="tablist">
          {TABS.map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={tab === name}
              onClick={() => setTab(name)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
                tab === name
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-muted hover:text-body",
              )}
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      {tab === "Overview" ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader title="The problem" />
              <p className="p-5 pt-3 text-body whitespace-pre-line leading-relaxed">
                {project.problem_statement}
              </p>
            </Card>
            <Card>
              <CardHeader
                title="Objectives"
                subtitle="What delivery will be reviewed against"
              />
              <p className="p-5 pt-3 text-body whitespace-pre-line leading-relaxed">
                {project.objectives}
              </p>
            </Card>

            {openRoles.length > 0 ? (
              <Card>
                <CardHeader
                  title="Open roles"
                  subtitle={`${openRoles.length} position${openRoles.length === 1 ? "" : "s"} to fill`}
                />
                <div className="p-5 pt-3 space-y-3">
                  {openRoles.map((role) => (
                    <RoleRow
                      key={role.id}
                      role={role}
                      canApply={!isTeam && project.status === "recruiting"}
                    />
                  ))}
                </div>
              </Card>
            ) : null}
          </div>

          <aside className="space-y-4">
            <Card className="p-5 space-y-4">
              <Detail label="Project lead">
                <Link
                  to={`/p/${project.lead?.public_slug}`}
                  className="flex items-center gap-2.5 hover:text-brand-600"
                >
                  <Avatar
                    name={project.lead?.display_name ?? "?"}
                    src={project.lead?.avatar}
                    size={32}
                  />
                  <span className="text-sm font-medium text-strong">
                    {project.lead?.display_name}
                  </span>
                </Link>
              </Detail>

              <Detail label="Mentor">
                {project.mentor ? (
                  <Link
                    to={`/p/${project.mentor.public_slug}`}
                    className="flex items-center gap-2.5 hover:text-brand-600"
                  >
                    <Avatar
                      name={project.mentor.display_name ?? "?"}
                      src={project.mentor.avatar}
                      size={32}
                    />
                    <span className="text-sm font-medium text-strong">
                      {project.mentor.display_name}
                    </span>
                  </Link>
                ) : (
                  <span className="text-sm text-muted">Not yet assigned</span>
                )}
              </Detail>

              {project.effort_hours_per_week ? (
                <Detail label="Expected commitment">
                  <span className="text-sm text-body">
                    about {project.effort_hours_per_week} hours a week
                  </span>
                </Detail>
              ) : null}

              {project.target_completion_on ? (
                <Detail label="Target completion">
                  <span className="text-sm text-body flex items-center gap-1.5">
                    <CalendarDays className="size-4 text-muted" aria-hidden />
                    {format(new Date(project.target_completion_on), "d MMMM yyyy")}
                  </span>
                </Detail>
              ) : null}

              {project.is_open_source ? (
                <Detail label="Open source">
                  <div className="flex items-center gap-2">
                    <Pill tone="green">{project.licence}</Pill>
                    {project.repository_url ? (
                      <a
                        href={project.repository_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-sm text-brand-600 hover:underline inline-flex items-center gap-1"
                      >
                        <ExternalLink className="size-3.5" aria-hidden /> Repository
                      </a>
                    ) : null}
                  </div>
                </Detail>
              ) : null}
            </Card>

            {isTeam ? (
              <Card>
                <CardHeader title="Team workspace" />
                <div className="p-5 pt-3 space-y-2">
                  <QuickLink to={`/projects/${slug}/workspace`}>
                    Tasks and milestones
                  </QuickLink>
                  <QuickLink to={`/contributions?project=${project.id}`}>
                    Log a contribution
                  </QuickLink>
                  <QuickLink to={`/projects/${slug}/updates`}>
                    Weekly progress updates
                  </QuickLink>
                </div>
              </Card>
            ) : null}
          </aside>
        </div>
      ) : null}

      {tab === "Team" ? <TeamTab project={project} /> : null}
      {tab === "Activity" ? <ActivityTab slug={slug} /> : null}
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-muted mb-1.5">
        {label}
      </div>
      {children}
    </div>
  );
}

function QuickLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-body hover:bg-sunken"
    >
      {children}
      <ArrowRight className="size-3.5 text-muted" aria-hidden />
    </Link>
  );
}

function RoleRow({
  role,
  canApply,
}: {
  role: NonNullable<import("@/api/types").Project["roles"]>[number];
  canApply: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [statement, setStatement] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);
  const { apply } = useProjectMutations();

  async function submit() {
    setError(null);
    try {
      await apply.mutateAsync({ roleId: role.id, statement });
      setApplied(true);
      setOpen(false);
    } catch (caught) {
      setError(toForgeError(caught).message);
    }
  }

  return (
    <div className="rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-medium text-strong">{role.title}</h3>
            {role.open_to_beginners ? <Pill tone="green">Open to beginners</Pill> : null}
          </div>
          <p className="text-sm text-muted mt-1">{role.description}</p>
          {role.required_skills?.length ? (
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {role.required_skills.map((skill) => (
                <Pill key={skill.id}>{skill.name}</Pill>
              ))}
            </div>
          ) : null}
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-muted mb-2">
            {role.filled_slots}/{role.slots} filled
          </p>
          {applied ? (
            <Pill tone="green" icon={<CheckCircle2 className="size-3" aria-hidden />}>
              Applied
            </Pill>
          ) : canApply ? (
            <Button size="sm" variant="secondary" onClick={() => setOpen((v) => !v)}>
              Apply
            </Button>
          ) : null}
        </div>
      </div>

      {open ? (
        <div className="mt-4 pt-4 border-t border-line space-y-3">
          <FormError message={error} />
          <Field
            label="Why this role?"
            hint="What you would bring, and what you want out of it. Two paragraphs is plenty."
          >
            <Textarea
              value={statement}
              onChange={(event) => setStatement(event.target.value)}
              rows={4}
              maxLength={1500}
              autoFocus
            />
          </Field>
          <div className="flex gap-2">
            <Button size="sm" onClick={submit} loading={apply.isPending}>
              Send application
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TeamTab({ project }: { project: import("@/api/types").Project }) {
  const members = project.memberships ?? [];
  return (
    <Card>
      <CardHeader
        title={`Team (${members.length})`}
        subtitle={
          project.is_cross_disciplinary
            ? `Drawn from ${project.school_spread} schools`
            : undefined
        }
      />
      <ul className="p-5 pt-3 divide-y divide-line">
        {members.map((membership) => (
          <li key={membership.id} className="flex items-center gap-3.5 py-3 first:pt-0">
            <Avatar
              name={membership.user?.display_name ?? "?"}
              src={membership.user?.avatar}
              size={40}
            />
            <div className="flex-1 min-w-0">
              <Link
                to={`/p/${membership.user?.public_slug}`}
                className="font-medium text-strong hover:text-brand-600"
              >
                {membership.user?.display_name}
              </Link>
              <p className="text-sm text-muted truncate">
                {membership.role_title ?? "Team member"}
                {membership.user?.school ? ` · ${membership.user.school}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {membership.is_lead ? <Pill tone="ember">Lead</Pill> : null}
              {membership.understudy_to ? (
                <Pill tone="purple">
                  Understudy to {membership.understudy_to.display_name}
                </Pill>
              ) : null}
              <span className="text-xs text-muted hidden sm:block">
                {membership.days_served}d
              </span>
            </div>
          </li>
        ))}
        {members.length === 0 ? (
          <li className="py-6 text-center text-sm text-muted">
            <Users className="size-8 mx-auto mb-2 opacity-40" aria-hidden />
            No members yet.
          </li>
        ) : null}
      </ul>
    </Card>
  );
}

function ActivityTab({ slug }: { slug: string }) {
  const { data, isLoading } = useProjectHistory(slug);
  if (isLoading) return <Loading />;

  return (
    <Card>
      <CardHeader title="Stage history" subtitle="Every change, with who made it and why" />
      <ol className="p-5 pt-3 space-y-4">
        {(data ?? []).map((entry) => (
          <li key={entry.id} className="flex gap-3.5">
            <div className="flex flex-col items-center shrink-0">
              <span className="size-2.5 rounded-full bg-brand-500 mt-1.5" aria-hidden />
              <span className="flex-1 w-px bg-line my-1" aria-hidden />
            </div>
            <div className="pb-1 min-w-0">
              <p className="text-sm text-strong">
                <span className="font-medium">
                  {entry.actor?.display_name ?? "The platform"}
                </span>{" "}
                moved this to{" "}
                <span className="font-medium">{entry.to_status?.replace(/_/g, " ")}</span>
              </p>
              {entry.note ? <p className="text-sm text-muted mt-0.5">{entry.note}</p> : null}
              <p className="text-xs text-muted mt-1">
                {entry.created_at
                  ? format(new Date(entry.created_at), "d MMM yyyy 'at' HH:mm")
                  : ""}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/** The stage buttons a lead or mentor can actually press right now. */
function LifecycleActions({
  project,
  slug,
}: {
  project: import("@/api/types").Project;
  slug: string;
}) {
  const { submit, transition, addRole } = useProjectMutations(slug);
  const [error, setError] = useState<string | null>(null);

  const permitted = project.permitted_transitions ?? [];
  const isDraftLike = project.status === "draft" || project.status === "returned";

  const NEXT_LABEL: Record<string, string> = {
    building: "Team is complete — start building",
    in_review: "Submit for review and testing",
    documenting: "Move to documentation",
    completed: "Mark as complete",
    archived: "Archive this project",
    abandoned: "Close as abandoned",
    recruiting: "Reopen recruitment",
  };

  const forward = permitted.filter((status) => status in NEXT_LABEL);

  async function act(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(toForgeError(caught).message);
    }
  }

  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold text-strong mb-3">What happens next</h2>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2 mt-3">
        {isDraftLike ? (
          <>
            <Button
              loading={submit.isPending}
              onClick={() => void act(() => submit.mutateAsync())}
            >
              Submit for review
            </Button>
            {(project.roles ?? []).length === 0 ? (
              <Button
                variant="secondary"
                icon={<Plus className="size-4" aria-hidden />}
                onClick={() =>
                  void act(() =>
                    addRole.mutateAsync({
                      title: "Contributor",
                      description: "Describe what this role does.",
                      slots: 1,
                    }),
                  )
                }
              >
                Add a role first
              </Button>
            ) : null}
          </>
        ) : null}

        {forward.map((status) => (
          <Button
            key={status}
            variant={status === "abandoned" || status === "archived" ? "secondary" : "primary"}
            loading={transition.isPending}
            onClick={() => void act(() => transition.mutateAsync({ to_status: status }))}
          >
            {NEXT_LABEL[status]}
          </Button>
        ))}

        {project.status === "completed" ? (
          <Link
            to={`/showcase/new?project=${project.id}`}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-ember-500 text-navy-950 text-sm font-semibold hover:bg-ember-400"
          >
            Publish to the showcase
            <ExternalLink className="size-4" aria-hidden />
          </Link>
        ) : null}
      </div>
      {isDraftLike && (project.roles ?? []).length === 0 ? (
        <p className="text-sm text-muted mt-3">
          A proposal with no roles has nothing for anyone to join, so it cannot be
          submitted yet.
        </p>
      ) : null}
    </Card>
  );
}
