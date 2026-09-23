import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, MessageSquare, Plus } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toForgeError } from "@/api/client";
import { useCommunityMutations, useSpaces, useThreads } from "@/api/queries";
import {
  Avatar, Button, Card, CardHeader, EmptyState, Field, FormError, Input, Loading,
  PageHeader, Pill, Select, Textarea,
} from "@/components/ui";
import { cn } from "@/lib/cn";

const KINDS = [
  { value: "discussion", label: "Discussion" },
  { value: "question", label: "Question" },
  { value: "study_group", label: "Study group" },
  { value: "show_and_tell", label: "Show and tell" },
  { value: "event", label: "Event" },
];

export function Community() {
  const [params, setParams] = useSearchParams();
  const space = params.get("space") ?? "";
  const kind = params.get("kind") ?? "";
  const { data: spaces } = useSpaces();
  const { data, isLoading } = useThreads({
    space: space || undefined,
    kind: kind || undefined,
  });
  const [composing, setComposing] = useState(false);

  const threads = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Community"
        description="Questions, study groups and discussion by discipline. Unlike a chat group, this has memory."
        action={
          <Button
            icon={<Plus className="size-4" aria-hidden />}
            onClick={() => setComposing((value) => !value)}
          >
            Start a discussion
          </Button>
        }
      />

      {composing ? <ThreadForm onDone={() => setComposing(false)} /> : null}

      <div className="grid gap-6 lg:grid-cols-4 mt-6">
        <aside className="lg:col-span-1">
          <Card className="p-3">
            <h2 className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
              Spaces
            </h2>
            <ul className="space-y-0.5 mt-1">
              <li>
                <button
                  onClick={() => setParams(kind ? { kind } : {})}
                  className={cn(
                    "w-full text-left rounded-lg px-3 py-2 text-sm transition-colors",
                    !space ? "bg-brand-50 text-brand-700 font-medium dark:bg-brand-900/40 dark:text-brand-200" : "text-body hover:bg-sunken",
                  )}
                >
                  All spaces
                </button>
              </li>
              {(spaces?.results ?? []).map((item) => (
                <li key={item.id}>
                  <button
                    onClick={() =>
                      setParams(kind ? { space: item.id, kind } : { space: item.id })
                    }
                    className={cn(
                      "w-full text-left rounded-lg px-3 py-2 text-sm transition-colors flex items-center justify-between gap-2",
                      space === item.id
                        ? "bg-brand-50 text-brand-700 font-medium dark:bg-brand-900/40 dark:text-brand-200"
                        : "text-body hover:bg-sunken",
                    )}
                  >
                    <span className="truncate">{item.name}</span>
                    <span className="text-xs text-muted tabular-nums">
                      {item.thread_count}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </aside>

        <div className="lg:col-span-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            {["", ...KINDS.map((item) => item.value)].map((value) => (
              <button
                key={value || "all"}
                onClick={() => {
                  const next: Record<string, string> = {};
                  if (space) next.space = space;
                  if (value) next.kind = value;
                  setParams(next);
                }}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  kind === value
                    ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200"
                    : "border-line text-muted hover:border-brand-300",
                )}
              >
                {value ? KINDS.find((item) => item.value === value)?.label : "Everything"}
              </button>
            ))}
          </div>

          {isLoading ? (
            <Loading />
          ) : threads.length === 0 ? (
            <Card>
              <EmptyState
                icon={<MessageSquare className="size-10" aria-hidden />}
                title="Nothing here yet"
                description="Ask the question. Somebody else on your cohort has it too, and a question with a marked answer is one the next student does not have to ask."
                action={<Button onClick={() => setComposing(true)}>Start a discussion</Button>}
              />
            </Card>
          ) : (
            threads.map((thread) => (
              <Card key={thread.id} className="p-4 hover:border-brand-300 transition-colors">
                <Link to={`/community/${thread.id}`} className="flex gap-3.5">
                  <Avatar
                    name={thread.author?.display_name ?? "?"}
                    src={thread.author?.avatar}
                    size={36}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-strong truncate">{thread.title}</h3>
                      {thread.kind === "question" ? (
                        thread.is_resolved ? (
                          <Pill tone="green" icon={<CheckCircle2 className="size-3" aria-hidden />}>
                            Answered
                          </Pill>
                        ) : (
                          <Pill tone="ember">Question</Pill>
                        )
                      ) : (
                        <Pill>{thread.kind?.replace(/_/g, " ")}</Pill>
                      )}
                    </div>
                    <p className="text-xs text-muted mt-1">
                      {thread.author?.display_name} in {thread.space_name}
                      {thread.last_activity_at
                        ? ` · ${formatDistanceToNow(new Date(thread.last_activity_at), { addSuffix: true })}`
                        : ""}
                    </p>
                  </div>
                  <span className="flex items-center gap-1.5 text-sm text-muted shrink-0">
                    <MessageSquare className="size-4" aria-hidden />
                    {thread.reply_count ?? 0}
                  </span>
                </Link>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ThreadForm({ onDone }: { onDone: () => void }) {
  const { data: spaces } = useSpaces();
  const { createThread } = useCommunityMutations();
  const [form, setForm] = useState({ space: "", kind: "discussion", title: "", body: "" });
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <Card className="mt-4">
      <CardHeader title="Start a discussion" />
      <div className="p-5 pt-3 space-y-4">
        <FormError message={error} />
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Space" required>
            <Select value={form.space} onChange={set("space")} required>
              <option value="">Choose a space…</option>
              {(spaces?.results ?? []).map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Kind" required>
            <Select value={form.kind} onChange={set("kind")}>
              {KINDS.map((kind) => (
                <option key={kind.value} value={kind.value}>
                  {kind.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Title" required>
          <Input value={form.title} onChange={set("title")} maxLength={180} />
        </Field>
        <Field label="Body" required hint="Markdown is fine. HTML is not accepted.">
          <Textarea value={form.body} onChange={set("body")} rows={5} maxLength={8000} />
        </Field>
        <div className="flex gap-2">
          <Button
            loading={createThread.isPending}
            onClick={async () => {
              setError(null);
              try {
                await createThread.mutateAsync(form);
                onDone();
              } catch (caught) {
                setError(toForgeError(caught).message);
              }
            }}
          >
            Post
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </div>
    </Card>
  );
}
