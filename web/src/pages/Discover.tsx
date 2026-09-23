import { useState } from "react";
import { Compass, Search, Sparkles } from "lucide-react";
import { useProjects, useReference } from "@/api/queries";
import { Card, EmptyState, Input, LinkButton, Loading, Select } from "@/components/ui";
import { ProjectCard } from "@/features/projects/bits";
import { PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";

export function Discover() {
  const { data: reference } = useReference();
  const [search, setSearch] = useState("");
  const [discipline, setDiscipline] = useState("");
  const [status, setStatus] = useState("");
  const [beginner, setBeginner] = useState(false);
  const [cross, setCross] = useState(false);

  const { data, isLoading } = useProjects({
    search: search || undefined,
    discipline: discipline || undefined,
    status: status || undefined,
    beginner_friendly: beginner || undefined,
    cross_disciplinary: cross || undefined,
    recruiting: !status || undefined,
  });

  const projects = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Discover projects"
        description="Work being built across every school. Join one, or propose your own."
        action={<LinkButton to="/projects/new">Propose a project</LinkButton>}
      />

      <Card className="p-4 mb-6">
        <div className="flex flex-col lg:flex-row gap-3">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted pointer-events-none"
              aria-hidden
            />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search projects, problems, skills…"
              className="pl-9"
              aria-label="Search projects"
            />
          </div>
          <div className="flex gap-3">
            <Select
              value={discipline}
              onChange={(event) => setDiscipline(event.target.value)}
              aria-label="Filter by discipline"
              className="sm:w-52"
            >
              <option value="">All disciplines</option>
              {reference?.discipline_areas.map((area) => (
                <option key={area.id} value={area.slug}>
                  {area.name}
                </option>
              ))}
            </Select>
            <Select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              aria-label="Filter by stage"
              className="sm:w-44"
            >
              <option value="">Recruiting now</option>
              <option value="building">In build</option>
              <option value="in_review">In review</option>
              <option value="documenting">Documenting</option>
              <option value="completed">Completed</option>
            </Select>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-line">
          <FilterChip
            active={beginner}
            onClick={() => setBeginner((value) => !value)}
            icon={<Sparkles className="size-3.5" aria-hidden />}
          >
            Open to beginners
          </FilterChip>
          <FilterChip active={cross} onClick={() => setCross((value) => !value)}>
            Cross-school teams
          </FilterChip>
        </div>
      </Card>

      {isLoading ? (
        <Loading />
      ) : projects.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Compass className="size-10" aria-hidden />}
            title="Nothing matches that yet"
            description="Try widening the filters. Or propose the project you were hoping to find — someone else is probably looking for it too."
            action={<LinkButton to="/projects/new">Propose a project</LinkButton>}
          />
        </Card>
      ) : (
        <>
          <p className="text-sm text-muted mb-4">
            {data?.count} project{data?.count === 1 ? "" : "s"}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200"
          : "border-line text-muted hover:border-brand-300 hover:text-body",
      )}
    >
      {icon}
      {children}
    </button>
  );
}
