import { useState } from "react";
import { toForgeError } from "@/api/client";
import { useProjectMutations } from "@/api/queries";
import { Button, Card, CardHeader, Field, FormError, Textarea } from "@/components/ui";

/**
 * The stage-two gate.
 *
 * Four separate checks rather than one "approve" button, because they are four
 * separate judgements and a reviewer who has to consider each one individually
 * is a reviewer who has actually considered each one. The server refuses an
 * approval with any box unticked, so the UI shows that rule rather than
 * letting it arrive as an error.
 */
const CHECKS = [
  {
    key: "scope_is_realistic",
    label: "The scope is realistic",
    hint: "Can a volunteer student team deliver this in a trimester?",
  },
  {
    key: "is_lawful_and_ethical",
    label: "It is lawful and ethical",
    hint: "No offensive security, no unconsented data collection.",
  },
  {
    key: "is_not_duplicative",
    label: "It does not duplicate existing work",
    hint: "Nothing on FORGE already covers this.",
  },
  {
    key: "has_clear_objectives",
    label: "The objectives are clear and testable",
    hint: "Delivery can be reviewed against them later.",
  },
] as const;

type Checks = Record<(typeof CHECKS)[number]["key"], boolean>;

export function ReviewPanel({ slug }: { slug: string }) {
  const { review } = useProjectMutations(slug);
  const [checks, setChecks] = useState<Checks>({
    scope_is_realistic: true,
    is_lawful_and_ethical: true,
    is_not_duplicative: true,
    has_clear_objectives: true,
  });
  const [reasons, setReasons] = useState("");
  const [error, setError] = useState<string | null>(null);

  const allChecked = Object.values(checks).every(Boolean);

  async function decide(decision: "approved" | "returned" | "declined") {
    setError(null);
    try {
      await review.mutateAsync({ decision, reasons, ...checks });
    } catch (caught) {
      setError(toForgeError(caught).message);
    }
  }

  return (
    <Card className="border-brand-300">
      <CardHeader
        title="Review this proposal"
        subtitle="Stage two. Nothing recruits a team until this is done."
      />
      <div className="p-5 pt-3 space-y-4">
        <FormError message={error} />

        <fieldset className="space-y-2.5">
          <legend className="text-sm font-medium text-strong mb-1">
            Check each one
          </legend>
          {CHECKS.map((check) => (
            <label
              key={check.key}
              className="flex items-start gap-3 rounded-lg border border-line p-3 cursor-pointer hover:bg-sunken"
            >
              <input
                type="checkbox"
                checked={checks[check.key]}
                onChange={(event) =>
                  setChecks((current) => ({ ...current, [check.key]: event.target.checked }))
                }
                className="mt-0.5 size-4 rounded border-line text-brand-600 focus:ring-brand-500/30"
              />
              <span className="min-w-0">
                <span className="block text-sm font-medium text-strong">{check.label}</span>
                <span className="block text-xs text-muted mt-0.5">{check.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <Field
          label="Reasons"
          required
          hint="Required for every decision, including approval. A proposal declined without reasons teaches the student nothing."
        >
          <Textarea
            value={reasons}
            onChange={(event) => setReasons(event.target.value)}
            rows={4}
            maxLength={3000}
            placeholder="What is strong about this, and what should change?"
          />
        </Field>

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!allChecked || !reasons.trim()}
            loading={review.isPending}
            onClick={() => void decide("approved")}
          >
            Approve
          </Button>
          <Button
            variant="secondary"
            disabled={!reasons.trim()}
            loading={review.isPending}
            onClick={() => void decide("returned")}
          >
            Return for revision
          </Button>
          <Button
            variant="ghost"
            disabled={!reasons.trim()}
            loading={review.isPending}
            onClick={() => void decide("declined")}
          >
            Decline
          </Button>
        </div>

        {!allChecked ? (
          <p className="text-sm text-muted">
            A proposal cannot be approved while one of the four checks is unmet.
            Return it for revision instead.
          </p>
        ) : null}
      </div>
    </Card>
  );
}
