import { useState } from "react";
import { GraduationCap } from "lucide-react";
import { toForgeError } from "@/api/client";
import { api } from "@/api/client";
import { useAvailableMentors, useMentorshipRequests, useMyProjects } from "@/api/queries";
import {
  Avatar, Button, Card, CardHeader, EmptyState, Field, FormError, Loading,
  PageHeader, Pill, Select, Textarea,
} from "@/components/ui";

/**
 * Mentors with actual capacity.
 *
 * The list is filtered by capacity rather than advertising everyone: a
 * directory that lists mentors who are already full produces a queue of
 * unanswered requests, and an unanswered request is how a student concludes
 * the platform is dead.
 */
export function Mentors() {
  const { data: mentors, isLoading } = useAvailableMentors();
  const requests = useMentorshipRequests();
  const [asking, setAsking] = useState<string | null>(null);

  return (
    <div>
      <PageHeader
        title="Find a mentor"
        description="Volunteer academic staff and alumni. Only those with room to take somebody on are shown."
      />

      {(requests.data?.results ?? []).length > 0 ? (
        <Card className="mb-6">
          <CardHeader title="Your requests" />
          <ul className="p-5 pt-3 divide-y divide-line">
            {(requests.data?.results ?? []).map((request) => (
              <li key={request.id} className="py-3 first:pt-0 last:pb-0 flex items-center gap-3">
                <Avatar name={request.mentor?.display_name ?? "?"} size={32} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-strong">
                    {request.mentor?.display_name}
                  </p>
                  {request.project_title ? (
                    <p className="text-xs text-muted">{request.project_title}</p>
                  ) : null}
                </div>
                <Pill
                  tone={
                    request.status === "accepted"
                      ? "green"
                      : request.status === "declined"
                        ? "red"
                        : "ember"
                  }
                >
                  {request.status}
                </Pill>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {isLoading ? (
        <Loading />
      ) : (mentors ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={<GraduationCap className="size-10" aria-hidden />}
            title="No mentors have room right now"
            description="Mentors set their own capacity, honestly and low. Check back — or ask your question in the community, where somebody will usually answer."
          />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(mentors ?? []).map((mentor) => (
            <Card key={mentor.id} className="p-5">
              <div className="flex items-start gap-3.5">
                <Avatar
                  name={mentor.user?.display_name ?? "?"}
                  src={mentor.user?.avatar}
                  size={48}
                />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-strong">{mentor.user?.display_name}</h3>
                  <p className="text-sm text-muted">{mentor.headline}</p>
                  {mentor.organisation ? (
                    <p className="text-xs text-muted mt-0.5">{mentor.organisation}</p>
                  ) : null}

                  <p className="text-sm text-body mt-3 line-clamp-3">{mentor.about}</p>

                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {mentor.expertise?.slice(0, 5).map((skill) => (
                      <Pill key={skill.id}>{skill.name}</Pill>
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 mt-4">
                    <Pill tone="green">
                      {mentor.current_load}/{mentor.capacity} projects
                    </Pill>
                    {mentor.hours_per_month ? (
                      <span className="text-xs text-muted">
                        about {mentor.hours_per_month}h a month
                      </span>
                    ) : null}
                    {mentor.is_alumnus ? <Pill tone="purple">Alumnus</Pill> : null}
                  </div>

                  <Button
                    size="sm"
                    variant="secondary"
                    className="mt-4"
                    onClick={() =>
                      setAsking(asking === mentor.user?.id ? null : (mentor.user?.id ?? null))
                    }
                  >
                    Ask for help
                  </Button>

                  {asking === mentor.user?.id ? (
                    <RequestForm
                      mentorId={mentor.user!.id}
                      onDone={() => {
                        setAsking(null);
                        void requests.refetch();
                      }}
                    />
                  ) : null}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function RequestForm({ mentorId, onDone }: { mentorId: string; onDone: () => void }) {
  const projects = useMyProjects();
  const [message, setMessage] = useState("");
  const [project, setProject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="mt-4 pt-4 border-t border-line space-y-3">
      <FormError message={error} />
      <Field label="Which project?">
        <Select value={project} onChange={(event) => setProject(event.target.value)}>
          <option value="">Not about a specific project</option>
          {(projects.data?.results ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </Select>
      </Field>
      <Field
        label="What would you like help with?"
        required
        hint="A specific ask gets a reply. 'Be my mentor' usually does not."
      >
        <Textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={3}
          maxLength={1500}
        />
      </Field>
      <div className="flex gap-2">
        <Button
          size="sm"
          loading={busy}
          disabled={!message.trim()}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await api.post("/mentorship/requests/", {
                mentor_id: mentorId,
                project: project || undefined,
                message,
              });
              onDone();
            } catch (caught) {
              setError(toForgeError(caught).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Send request
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
