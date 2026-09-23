import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import {
  CheckCheck, Plus, ShieldCheck, Sparkles, TriangleAlert,
} from "lucide-react";
import { format } from "date-fns";
import { toForgeError } from "@/api/client";
import {
  useAttestationQueue, useContributionMutations, useContributions, useMyProjects,
  useMySkills,
} from "@/api/queries";
import {
  Avatar, Button, Card, CardHeader, EmptyState, Field, FormError, Input, Loading,
  PageHeader, Pill, Select, Textarea,
} from "@/components/ui";
import { cn } from "@/lib/cn";
import type { Contribution } from "@/api/types";

const DIMENSIONS = [
  { value: "delivery", label: "Delivery — work completed against an objective" },
  { value: "leadership", label: "Leadership — coordinating a team to a result" },
  { value: "research", label: "Research — investigation, field work, analysis" },
  { value: "design", label: "Design — interface, service or visual design" },
  { value: "documentation", label: "Documentation — writing it down for others" },
  { value: "mentorship", label: "Mentorship — teaching and supporting others" },
  { value: "review", label: "Review — checking and improving others' work" },
  { value: "community", label: "Community — answering, organising, moderating" },
];

const AI_OPTIONS = [
  { value: "none", label: "No AI assistance" },
  { value: "assisted", label: "AI-assisted, reviewed and understood by me" },
  { value: "generated", label: "Substantially AI-generated, curated by me" },
];

export function Contributions() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "confirm" ? "confirm" : "mine";
  const queue = useAttestationQueue();
  const mine = useContributions();

  const queueCount = queue.data?.count ?? 0;

  return (
    <div>
      <PageHeader
        title="Contributions"
        description="What you did, confirmed by two other people, recorded permanently."
      />

      <div className="border-b border-line mb-6">
        <div className="flex gap-1 -mb-px" role="tablist">
          <TabButton
            active={tab === "mine"}
            onClick={() => setParams({})}
            label="My contributions"
          />
          <TabButton
            active={tab === "confirm"}
            onClick={() => setParams({ tab: "confirm" })}
            label="Waiting on me"
            count={queueCount}
          />
        </div>
      </div>

      {tab === "mine" ? <MyContributions data={mine} /> : <AttestationQueue data={queue} />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
}) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2",
        active
          ? "border-brand-600 text-brand-600"
          : "border-transparent text-muted hover:text-body",
      )}
    >
      {label}
      {count ? (
        <span className="min-w-5 h-5 px-1.5 rounded-full bg-ember-500 text-navy-950 text-xs font-bold grid place-items-center tabular-nums">
          {count}
        </span>
      ) : null}
    </button>
  );
}

function MyContributions({ data }: { data: ReturnType<typeof useContributions> }) {
  const [composing, setComposing] = useState(false);

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button
          icon={<Plus className="size-4" aria-hidden />}
          onClick={() => setComposing((value) => !value)}
        >
          Log a contribution
        </Button>
      </div>

      {composing ? <ContributionForm onDone={() => setComposing(false)} /> : null}

      {data.isLoading ? (
        <Loading />
      ) : (data.data?.results ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={<Sparkles className="size-10" aria-hidden />}
            title="Nothing logged yet"
            description="Log work as you do it, not at the end. A record written three months later is one your lead cannot recognise, and one they will be slower to confirm."
            action={<Button onClick={() => setComposing(true)}>Log your first one</Button>}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {(data.data?.results ?? []).map((contribution) => (
            <ContributionRow key={contribution.id} contribution={contribution} />
          ))}
        </div>
      )}
    </div>
  );
}

const STATUS_TONE = {
  draft: "neutral",
  submitted: "ember",
  confirmed: "green",
  disputed: "red",
  withdrawn: "neutral",
} as const;

function ContributionRow({ contribution }: { contribution: Contribution }) {
  const { submit, withdraw } = useContributionMutations();
  const [error, setError] = useState<string | null>(null);

  const confirmations = (contribution.attestations ?? []).filter(
    (attestation) => attestation.decision === "confirm",
  );

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Pill tone={STATUS_TONE[contribution.status as keyof typeof STATUS_TONE] ?? "neutral"}>
              {contribution.status}
            </Pill>
            <Pill tone="brand">{contribution.dimension_display?.split(" —")[0]}</Pill>
            {contribution.ai_assistance !== "none" ? (
              <Pill tone="purple">AI {contribution.ai_assistance}</Pill>
            ) : null}
            {contribution.is_late ? (
              <Pill tone="ember" icon={<TriangleAlert className="size-3" aria-hidden />}>
                Logged late
              </Pill>
            ) : null}
          </div>

          <p className="text-strong leading-relaxed">{contribution.description}</p>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2.5 text-xs text-muted">
            <span>{contribution.project_title}</span>
            {contribution.occurred_on ? (
              <span>{format(new Date(contribution.occurred_on), "d MMM yyyy")}</span>
            ) : null}
            {contribution.effort_hours ? <span>{contribution.effort_hours}h</span> : null}
            {contribution.ledger_sequence ? (
              <Link
                to={`/ledger?sequence=${contribution.ledger_sequence}`}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline"
              >
                <ShieldCheck className="size-3.5" aria-hidden />
                Ledger #{contribution.ledger_sequence}
              </Link>
            ) : null}
          </div>
        </div>

        <div className="shrink-0 flex flex-col items-end gap-2">
          {contribution.status === "draft" ? (
            <Button
              size="sm"
              loading={submit.isPending}
              onClick={async () => {
                setError(null);
                try {
                  await submit.mutateAsync(contribution.id);
                } catch (caught) {
                  setError(toForgeError(caught).message);
                }
              }}
            >
              Submit for confirmation
            </Button>
          ) : null}
          {contribution.status === "draft" || contribution.status === "disputed" ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => void withdraw.mutateAsync(contribution.id)}
            >
              Withdraw
            </Button>
          ) : null}
        </div>
      </div>

      {error ? <div className="mt-3"><FormError message={error} /></div> : null}

      {contribution.status !== "draft" ? (
        <div className="mt-4 pt-4 border-t border-line">
          <p className="text-xs font-medium uppercase tracking-wide text-muted mb-2">
            Confirmation — {confirmations.length} of 2
          </p>
          <div className="flex flex-wrap gap-2">
            {["lead", "mentor"].map((capacity) => {
              const attestation = (contribution.attestations ?? []).find(
                (item) => item.capacity === capacity,
              );
              return (
                <div
                  key={capacity}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm",
                    attestation?.decision === "confirm"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-800"
                      : attestation?.decision === "dispute"
                        ? "border-red-300 bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800"
                        : "border-line text-muted border-dashed",
                  )}
                >
                  <span className="capitalize font-medium">{capacity}</span>
                  <span>
                    {attestation
                      ? attestation.decision === "confirm"
                        ? `confirmed by ${attestation.attestor_name}`
                        : `disputed by ${attestation.attestor_name}`
                      : "awaiting"}
                  </span>
                </div>
              );
            })}
          </div>
          {(contribution.attestations ?? [])
            .filter((attestation) => attestation.note)
            .map((attestation) => (
              <p key={attestation.id} className="text-sm text-body mt-2.5">
                <span className="font-medium">{attestation.attestor_name}:</span>{" "}
                {attestation.note}
              </p>
            ))}
        </div>
      ) : null}
    </Card>
  );
}

function ContributionForm({ onDone }: { onDone: () => void }) {
  const projects = useMyProjects();
  const skills = useMySkills();
  const { create } = useContributionMutations();
  const [form, setForm] = useState({
    project: "",
    dimension: "delivery",
    description: "",
    evidence_url: "",
    effort_hours: "",
    occurred_on: new Date().toISOString().slice(0, 10),
    ai_assistance: "none",
    ai_assistance_note: "",
  });
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  async function save() {
    setError(null);
    setFieldErrors({});
    try {
      await create.mutateAsync({
        ...form,
        effort_hours: form.effort_hours || undefined,
        evidence_url: form.evidence_url || undefined,
        skill_ids: selectedSkills,
      });
      onDone();
    } catch (caught) {
      const failure = toForgeError(caught);
      setError(failure.message);
      setFieldErrors(failure.fieldErrors);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Log a contribution"
        subtitle="Specific enough that your lead and mentor will recognise it."
      />
      <div className="p-5 pt-3 space-y-4">
        <FormError message={error} />

        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Project" required error={fieldErrors.project}>
            <Select value={form.project} onChange={set("project")} required>
              <option value="">Select a project…</option>
              {(projects.data?.results ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.title}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Kind of contribution" required error={fieldErrors.dimension}>
            <Select value={form.dimension} onChange={set("dimension")}>
              {DIMENSIONS.map((dimension) => (
                <option key={dimension.value} value={dimension.value}>
                  {dimension.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field
          label="What did you do?"
          required
          error={fieldErrors.description}
          hint={'"Worked on the backend" is not a contribution record. "Built and tested the contribution ledger, including the hash chain" is.'}
        >
          <Textarea
            value={form.description}
            onChange={set("description")}
            rows={4}
            maxLength={2000}
          />
        </Field>

        <div className="grid sm:grid-cols-3 gap-4">
          <Field
            label="Evidence"
            className="sm:col-span-2"
            error={fieldErrors.evidence_url}
            hint="A commit, a pull request, a document, a recording. Optional, but it makes confirmation quick."
          >
            <Input
              type="url"
              value={form.evidence_url}
              onChange={set("evidence_url")}
              placeholder="https://…"
            />
          </Field>
          <Field label="Hours" error={fieldErrors.effort_hours} hint="Approximate.">
            <Input
              type="number"
              min={0}
              step={0.5}
              value={form.effort_hours}
              onChange={set("effort_hours")}
            />
          </Field>
        </div>

        <Field label="When" required error={fieldErrors.occurred_on}>
          <Input type="date" value={form.occurred_on} onChange={set("occurred_on")} />
        </Field>

        {(skills.data?.results ?? []).length > 0 ? (
          <Field
            label="Skills used"
            hint="Confirming this contribution puts evidence behind the skills you tag."
          >
            <div className="flex flex-wrap gap-2">
              {(skills.data?.results ?? []).map((userSkill) => {
                const id = userSkill.skill?.id ?? "";
                const active = selectedSkills.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={active}
                    onClick={() =>
                      setSelectedSkills((current) =>
                        active ? current.filter((item) => item !== id) : [...current, id],
                      )
                    }
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                      active
                        ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200"
                        : "border-line text-muted hover:border-brand-300",
                    )}
                  >
                    {userSkill.skill?.name}
                  </button>
                );
              })}
            </div>
          </Field>
        ) : null}

        <Field
          label="AI assistance"
          error={fieldErrors.ai_assistance}
          hint="Disclosure, not prohibition. An attestor who finds undisclosed assistance has grounds to dispute."
        >
          <Select value={form.ai_assistance} onChange={set("ai_assistance")}>
            {AI_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>

        {form.ai_assistance !== "none" ? (
          <Field
            label="What did the tool do, and what did you do?"
            required
            error={fieldErrors.ai_assistance_note}
          >
            <Input
              value={form.ai_assistance_note}
              onChange={set("ai_assistance_note")}
              maxLength={300}
              placeholder="Generated the first draft of the serialisers; I rewrote the validation and wrote all the tests."
            />
          </Field>
        ) : null}

        <div className="flex gap-2 pt-1">
          <Button loading={create.isPending} onClick={save}>
            Save as draft
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </div>
    </Card>
  );
}

function AttestationQueue({ data }: { data: ReturnType<typeof useAttestationQueue> }) {
  if (data.isLoading) return <Loading />;
  const items = data.data?.results ?? [];

  if (items.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<CheckCheck className="size-10" aria-hidden />}
          title="Nothing waiting on you"
          description="When a member of a project you lead or mentor logs a contribution, it appears here for your confirmation."
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4 bg-sunken border-dashed">
        <p className="text-sm text-body">
          <strong className="text-strong">You are one of two signatures.</strong> Nothing
          enters a member's portfolio until both the project lead and the mentor have
          confirmed it — and you cannot confirm your own work.
        </p>
      </Card>
      {items.map((contribution) => (
        <AttestationCard key={contribution.id} contribution={contribution} />
      ))}
    </div>
  );
}

function AttestationCard({ contribution }: { contribution: Contribution }) {
  const { attest } = useContributionMutations();
  const [note, setNote] = useState("");
  const [disputing, setDisputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(confirm: boolean) {
    setError(null);
    try {
      await attest.mutateAsync({ id: contribution.id, confirm, note });
    } catch (caught) {
      setError(toForgeError(caught).message);
    }
  }

  return (
    <Card className="p-5">
      <div className="flex items-start gap-3.5">
        <Avatar
          name={contribution.contributor?.display_name ?? "?"}
          src={contribution.contributor?.avatar}
          size={40}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-strong">
              {contribution.contributor?.display_name}
            </span>
            <Pill tone="brand">{contribution.dimension_display?.split(" —")[0]}</Pill>
            {contribution.ai_assistance !== "none" ? (
              <Pill tone="purple">AI {contribution.ai_assistance}</Pill>
            ) : null}
            {contribution.is_late ? <Pill tone="ember">Logged late</Pill> : null}
          </div>
          <p className="text-xs text-muted mt-0.5">
            {contribution.project_title}
            {contribution.occurred_on
              ? ` · ${format(new Date(contribution.occurred_on), "d MMM yyyy")}`
              : ""}
            {contribution.effort_hours ? ` · ${contribution.effort_hours}h` : ""}
          </p>

          <p className="text-body mt-3 leading-relaxed">{contribution.description}</p>

          {contribution.ai_assistance_note ? (
            <p className="text-sm text-muted mt-2 italic">
              AI disclosure: {contribution.ai_assistance_note}
            </p>
          ) : null}

          {contribution.evidence_url ? (
            <a
              href={contribution.evidence_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-block text-sm text-brand-600 hover:underline mt-2"
            >
              View the evidence →
            </a>
          ) : null}

          <FormError message={error} />

          {disputing ? (
            <div className="mt-4 space-y-3">
              <Field label="What is wrong with this claim?" required>
                <Textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={3}
                  autoFocus
                  placeholder="Be specific. The contributor will see this and can correct and resubmit."
                />
              </Field>
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  size="sm"
                  disabled={!note.trim()}
                  loading={attest.isPending}
                  onClick={() => void decide(false)}
                >
                  Dispute this
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDisputing(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2 mt-4">
              <Button
                size="sm"
                loading={attest.isPending}
                onClick={() => void decide(true)}
                icon={<CheckCheck className="size-4" aria-hidden />}
              >
                Confirm
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setDisputing(true)}>
                Something's not right
              </Button>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
