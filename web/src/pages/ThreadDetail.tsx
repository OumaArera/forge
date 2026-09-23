import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowBigDown, ArrowBigUp, CheckCircle2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toForgeError } from "@/api/client";
import { useCommunityMutations, useThread } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import {
  Avatar, Button, Card, ErrorState, FormError, Loading, Pill, Textarea,
} from "@/components/ui";
import { cn } from "@/lib/cn";

export function ThreadDetail() {
  const { id = "" } = useParams();
  const { member } = useAuth();
  const { data: thread, isLoading, isError, refetch } = useThread(id);
  const { reply, acceptAnswer, vote } = useCommunityMutations(id);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <Loading />;
  if (isError || !thread)
    return <ErrorState message="That discussion could not be loaded." onRetry={() => void refetch()} />;

  const isAsker = thread.author?.id === member?.id;
  const isQuestion = thread.kind === "question";

  return (
    <div className="max-w-3xl space-y-4">
      <nav className="text-sm text-muted" aria-label="Breadcrumb">
        <Link to="/community" className="hover:text-brand-600">
          Community
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-body">{thread.space_name}</span>
      </nav>

      <Card className="p-5">
        <div className="flex items-start gap-3.5">
          <Avatar
            name={thread.author?.display_name ?? "?"}
            src={thread.author?.avatar}
            size={40}
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold text-strong">{thread.title}</h1>
              {isQuestion && thread.is_resolved ? (
                <Pill tone="green" icon={<CheckCircle2 className="size-3" aria-hidden />}>
                  Answered
                </Pill>
              ) : null}
            </div>
            <p className="text-xs text-muted mt-1">
              {thread.author?.display_name}
              {thread.created_at
                ? ` · ${formatDistanceToNow(new Date(thread.created_at), { addSuffix: true })}`
                : ""}
            </p>
            <p className="text-body mt-4 whitespace-pre-line leading-relaxed">
              {thread.body}
            </p>
          </div>
        </div>
      </Card>

      <h2 className="text-sm font-semibold text-strong pt-2">
        {thread.reply_count ?? 0} {thread.reply_count === 1 ? "reply" : "replies"}
        {isQuestion ? " — most useful first" : ""}
      </h2>

      {(thread.posts ?? []).map((post) => {
        const accepted = thread.accepted_answer === post.id;
        return (
          <Card
            key={post.id}
            className={cn("p-5", accepted && "border-emerald-300 bg-emerald-50/40 dark:bg-emerald-950/20")}
          >
            <div className="flex gap-3.5">
              {isQuestion ? (
                <div className="flex flex-col items-center gap-0.5 shrink-0">
                  <button
                    onClick={() =>
                      void vote.mutateAsync({ postId: post.id, value: post.my_vote === 1 ? 0 : 1 })
                    }
                    aria-label="Upvote"
                    className={cn(
                      "p-1 rounded hover:bg-sunken",
                      post.my_vote === 1 ? "text-brand-600" : "text-muted",
                    )}
                  >
                    <ArrowBigUp className="size-5" />
                  </button>
                  <span className="text-sm font-semibold text-strong tabular-nums">
                    {post.vote_score ?? 0}
                  </span>
                  <button
                    onClick={() =>
                      void vote.mutateAsync({ postId: post.id, value: post.my_vote === -1 ? 0 : -1 })
                    }
                    aria-label="Downvote"
                    className={cn(
                      "p-1 rounded hover:bg-sunken",
                      post.my_vote === -1 ? "text-red-600" : "text-muted",
                    )}
                  >
                    <ArrowBigDown className="size-5" />
                  </button>
                </div>
              ) : (
                <Avatar name={post.author_name ?? "?"} src={post.author?.avatar} size={36} />
              )}

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-strong">
                    {post.author_name ?? "Former member"}
                  </span>
                  {accepted ? (
                    <Pill tone="green" icon={<CheckCircle2 className="size-3" aria-hidden />}>
                      Accepted answer
                    </Pill>
                  ) : null}
                  <span className="text-xs text-muted">
                    {post.created_at
                      ? formatDistanceToNow(new Date(post.created_at), { addSuffix: true })
                      : ""}
                  </span>
                </div>
                <p className="text-body mt-2 whitespace-pre-line leading-relaxed">
                  {post.body}
                </p>

                {isQuestion && isAsker && !accepted ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="mt-3"
                    onClick={() =>
                      void acceptAnswer.mutateAsync({ id, postId: post.id })
                    }
                  >
                    This answered it
                  </Button>
                ) : null}
              </div>
            </div>
          </Card>
        );
      })}

      {thread.is_locked ? (
        <Card className="p-4 text-sm text-muted text-center">
          This thread is locked.
        </Card>
      ) : (
        <Card className="p-5">
          <FormError message={error} />
          <Textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={4}
            placeholder={isQuestion ? "Answer the question…" : "Add to the discussion…"}
            maxLength={8000}
          />
          <Button
            className="mt-3"
            disabled={!body.trim()}
            loading={reply.isPending}
            onClick={async () => {
              setError(null);
              try {
                await reply.mutateAsync({ id, body });
                setBody("");
              } catch (caught) {
                setError(toForgeError(caught).message);
              }
            }}
          >
            Post reply
          </Button>
        </Card>
      )}
    </div>
  );
}
