import { Link } from "react-router-dom";
import { Inbox } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useReviewQueue } from "@/api/queries";
import { Avatar, Card, EmptyState, Loading, PageHeader, Pill } from "@/components/ui";

/**
 * The reviewer's queue, oldest first.
 *
 * Ordering matters here: the oldest proposal is the one keeping a student
 * waiting longest, and a student waiting without an answer concludes the
 * platform is dead.
 */
export function ReviewQueue() {
  const { data, isLoading } = useReviewQueue();
  const projects = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Review queue"
        description="Proposals waiting on a mentor or community lead. Until one is reviewed, nobody can join it."
      />
      {isLoading ? (
        <Loading />
      ) : projects.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Inbox className="size-10" aria-hidden />}
            title="The queue is empty"
            description="Nothing is waiting. That is the state to keep it in."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {projects.map((project) => (
            <Card key={project.id} className="p-5 hover:border-brand-300 transition-colors">
              <Link to={`/projects/${project.slug}`} className="block">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5 mb-2">
                      {project.discipline_areas?.map((area) => (
                        <Pill key={area.id} tone="brand">
                          {area.name}
                        </Pill>
                      ))}
                    </div>
                    <h3 className="font-semibold text-strong">{project.title}</h3>
                    <p className="text-sm text-muted mt-1 line-clamp-2">{project.summary}</p>
                    <div className="flex items-center gap-2 mt-3">
                      <Avatar
                        name={project.lead?.display_name ?? "?"}
                        src={project.lead?.avatar}
                        size={24}
                      />
                      <span className="text-xs text-muted">
                        {project.lead?.display_name}
                        {project.created_at
                          ? ` · submitted ${formatDistanceToNow(new Date(project.created_at), { addSuffix: true })}`
                          : ""}
                      </span>
                    </div>
                  </div>
                  <Pill tone="ember">{project.status_display}</Pill>
                </div>
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
