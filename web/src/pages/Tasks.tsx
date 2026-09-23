import { ListTodo } from "lucide-react";
import { format } from "date-fns";
import { useMyTasks, useWorkspaceMutations } from "@/api/queries";
import { Card, EmptyState, LinkButton, Loading, PageHeader, Pill, Select } from "@/components/ui";
import { cn } from "@/lib/cn";

const STATUSES = [
  { value: "todo", label: "To do" },
  { value: "in_progress", label: "In progress" },
  { value: "blocked", label: "Blocked" },
  { value: "in_review", label: "In review" },
  { value: "done", label: "Done" },
];

export function Tasks() {
  const { data, isLoading } = useMyTasks();
  const { updateTask } = useWorkspaceMutations();
  const tasks = data ?? [];

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="My tasks"
        description="Assigned to you across every project you are on."
      />

      {isLoading ? (
        <Loading />
      ) : tasks.length === 0 ? (
        <Card>
          <EmptyState
            icon={<ListTodo className="size-10" aria-hidden />}
            title="Nothing assigned to you"
            description="Tasks appear here once a project lead assigns you something. If you are on a team and idle, say so in the weekly update."
            action={<LinkButton to="/projects">Go to my projects</LinkButton>}
          />
        </Card>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <Card key={task.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium text-strong">{task.title}</h3>
                    {task.priority === 3 ? <Pill tone="red">High</Pill> : null}
                    {task.status === "blocked" ? <Pill tone="ember">Blocked</Pill> : null}
                  </div>
                  {task.description ? (
                    <p className="text-sm text-muted mt-1 line-clamp-2">{task.description}</p>
                  ) : null}
                  {task.status === "blocked" && task.blocked_reason ? (
                    <p className="text-sm text-ember-700 dark:text-ember-300 mt-1.5">
                      Blocked on: {task.blocked_reason}
                    </p>
                  ) : null}
                  {task.due_on ? (
                    <p
                      className={cn(
                        "text-xs mt-1.5",
                        new Date(task.due_on) < new Date() ? "text-red-600" : "text-muted",
                      )}
                    >
                      Due {format(new Date(task.due_on), "d MMM yyyy")}
                    </p>
                  ) : null}
                </div>

                <Select
                  value={task.status ?? "todo"}
                  onChange={(event) =>
                    void updateTask.mutateAsync({ id: task.id, status: event.target.value })
                  }
                  className="w-36 shrink-0"
                  aria-label={`Status of ${task.title}`}
                >
                  {STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </Select>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
