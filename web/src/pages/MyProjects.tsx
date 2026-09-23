import { Briefcase } from "lucide-react";
import { useMyProjects } from "@/api/queries";
import { Card, EmptyState, LinkButton, Loading, PageHeader } from "@/components/ui";
import { ProjectCard } from "@/features/projects/bits";

export function MyProjects() {
  const { data, isLoading } = useMyProjects();
  const projects = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="My projects"
        description="Everything you lead or are a member of, including finished work."
        action={<LinkButton to="/projects/new">Propose a project</LinkButton>}
      />
      {isLoading ? (
        <Loading />
      ) : projects.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Briefcase className="size-10" aria-hidden />}
            title="You are not on a team yet"
            description="Joining is usually the better way in than starting. Find a role that fits what you already know, or one open to beginners."
            action={<LinkButton to="/discover">Find a project</LinkButton>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}
