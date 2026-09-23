import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Info, Plus, X } from "lucide-react";
import { toForgeError } from "@/api/client";
import { useProjectMutations, useReference } from "@/api/queries";
import {
  Button, Card, CardHeader, Field, FormError, Input, PageHeader, Pill, Select,
  Textarea,
} from "@/components/ui";
import { cn } from "@/lib/cn";

type DraftRole = {
  title: string;
  description: string;
  slots: number;
  open_to_beginners: boolean;
  required_skill_ids: string[];
};

export function NewProject() {
  const navigate = useNavigate();
  const { data: reference } = useReference();
  const { create, addRole } = useProjectMutations();

  const [form, setForm] = useState({
    title: "",
    summary: "",
    problem_statement: "",
    objectives: "",
    effort_hours_per_week: "6",
    target_completion_on: "",
    is_open_source: false,
    licence: "",
  });
  const [areas, setAreas] = useState<string[]>([]);
  const [roles, setRoles] = useState<DraftRole[]>([
    { title: "", description: "", slots: 1, open_to_beginners: false, required_skill_ids: [] },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    try {
      const project = await create.mutateAsync({
        ...form,
        effort_hours_per_week: form.effort_hours_per_week
          ? Number(form.effort_hours_per_week)
          : undefined,
        target_completion_on: form.target_completion_on || undefined,
        licence: form.is_open_source ? form.licence : "",
        discipline_area_ids: areas,
      });

      // Roles are created against the project once it exists. A proposal with
      // no roles cannot be submitted, so we create them here rather than
      // leaving the member to discover that on the next screen.
      const slug = (project as { slug?: string }).slug;
      for (const role of roles.filter((item) => item.title.trim())) {
        await addRole.mutateAsync({ ...role, slug });
      }
      navigate(`/projects/${slug}`);
    } catch (caught) {
      const failure = toForgeError(caught);
      setError(failure.message);
      setFieldErrors(failure.fieldErrors);
    }
  }

  return (
    <form onSubmit={onSubmit} className="max-w-3xl">
      <PageHeader
        title="Propose a project"
        description="A mentor reviews this before anyone can join. Be specific — a vague proposal gets returned, which costs you a week."
      />

      <div className="space-y-6">
        <FormError message={error} />

        <Card>
          <CardHeader title="The idea" />
          <div className="p-5 pt-3 space-y-4">
            <Field label="Title" required error={fieldErrors.title}>
              <Input
                value={form.title}
                onChange={set("title")}
                maxLength={140}
                placeholder="Clinic queue tracker for rural health centres"
                required
              />
            </Field>

            <Field
              label="One-line summary"
              required
              error={fieldErrors.summary}
              hint="This is what appears in listings. One or two sentences."
            >
              <Input
                value={form.summary}
                onChange={set("summary")}
                maxLength={300}
                placeholder="Let patients see how long the queue is before they travel."
                required
              />
            </Field>

            <Field
              label="What problem does this address, and for whom?"
              required
              error={fieldErrors.problem_statement}
            >
              <Textarea
                value={form.problem_statement}
                onChange={set("problem_statement")}
                rows={4}
                maxLength={4000}
                required
              />
            </Field>

            <Field
              label="Objectives"
              required
              error={fieldErrors.objectives}
              hint="What will exist at the end that does not exist now? Your delivery gets reviewed against exactly this."
            >
              <Textarea
                value={form.objectives}
                onChange={set("objectives")}
                rows={4}
                maxLength={4000}
                required
              />
            </Field>

            <Field
              label="Discipline areas"
              required
              error={fieldErrors.discipline_area_ids}
              hint="Tag at least one so the right students and the right mentor can find this. More than one is encouraged."
            >
              <div className="flex flex-wrap gap-2">
                {reference?.discipline_areas.map((area) => {
                  const active = areas.includes(area.id);
                  return (
                    <button
                      key={area.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() =>
                        setAreas((current) =>
                          active
                            ? current.filter((item) => item !== area.id)
                            : [...current, area.id],
                        )
                      }
                      className={cn(
                        "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                        active
                          ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200"
                          : "border-line text-muted hover:border-brand-300",
                      )}
                    >
                      {area.name}
                    </button>
                  );
                })}
              </div>
            </Field>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Commitment"
            subtitle="Say honestly what this costs someone's week"
          />
          <div className="p-5 pt-3 grid sm:grid-cols-2 gap-4">
            <Field
              label="Hours per week, per member"
              error={fieldErrors.effort_hours_per_week}
              hint="Most members study at a distance and many are in employment."
            >
              <Input
                type="number"
                min={1}
                max={40}
                value={form.effort_hours_per_week}
                onChange={set("effort_hours_per_week")}
              />
            </Field>
            <Field
              label="Target completion"
              error={fieldErrors.target_completion_on}
              hint="Indicative. Nothing punishes you for missing it."
            >
              <Input
                type="date"
                value={form.target_completion_on}
                onChange={set("target_completion_on")}
              />
            </Field>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Roles you need"
            subtitle="Students apply to a role, not to a project in the abstract"
            action={
              <Button
                type="button"
                size="sm"
                variant="secondary"
                icon={<Plus className="size-4" aria-hidden />}
                onClick={() =>
                  setRoles((current) => [
                    ...current,
                    {
                      title: "",
                      description: "",
                      slots: 1,
                      open_to_beginners: false,
                      required_skill_ids: [],
                    },
                  ])
                }
              >
                Add role
              </Button>
            }
          />
          <div className="p-5 pt-3 space-y-4">
            <p className="flex items-start gap-2 text-sm text-muted">
              <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
              Carry at least one role open to beginners if you can. A first-year with
              no track record who cannot find a way in is the person most likely to
              give up on FORGE.
            </p>

            {roles.map((role, index) => (
              <div key={index} className="rounded-lg border border-line p-4 space-y-3">
                <div className="flex items-start gap-3">
                  <Field label="Role title" className="flex-1">
                    <Input
                      value={role.title}
                      onChange={(event) =>
                        setRoles((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, title: event.target.value }
                              : item,
                          ),
                        )
                      }
                      placeholder="Backend developer"
                    />
                  </Field>
                  <Field label="Slots" className="w-20">
                    <Input
                      type="number"
                      min={1}
                      max={20}
                      value={role.slots}
                      onChange={(event) =>
                        setRoles((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, slots: Number(event.target.value) }
                              : item,
                          ),
                        )
                      }
                    />
                  </Field>
                  {roles.length > 1 ? (
                    <button
                      type="button"
                      onClick={() =>
                        setRoles((current) =>
                          current.filter((_, itemIndex) => itemIndex !== index),
                        )
                      }
                      className="mt-7 p-2 rounded-lg text-muted hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40"
                      aria-label={`Remove role ${index + 1}`}
                    >
                      <X className="size-4" />
                    </button>
                  ) : null}
                </div>

                <Field label="What does this role do?">
                  <Textarea
                    value={role.description}
                    onChange={(event) =>
                      setRoles((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, description: event.target.value }
                            : item,
                        ),
                      )
                    }
                    rows={2}
                  />
                </Field>

                <div className="flex flex-wrap gap-2">
                  {(reference?.skills ?? []).slice(0, 24).map((skill) => {
                    const active = role.required_skill_ids.includes(skill.id);
                    return (
                      <button
                        key={skill.id}
                        type="button"
                        aria-pressed={active}
                        onClick={() =>
                          setRoles((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? {
                                    ...item,
                                    required_skill_ids: active
                                      ? item.required_skill_ids.filter((id) => id !== skill.id)
                                      : [...item.required_skill_ids, skill.id],
                                  }
                                : item,
                            ),
                          )
                        }
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-xs transition-colors",
                          active
                            ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200"
                            : "border-line text-muted hover:border-brand-300",
                        )}
                      >
                        {skill.name}
                      </button>
                    );
                  })}
                </div>

                <label className="flex items-center gap-2.5 text-sm text-body cursor-pointer">
                  <input
                    type="checkbox"
                    checked={role.open_to_beginners}
                    onChange={(event) =>
                      setRoles((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, open_to_beginners: event.target.checked }
                            : item,
                        ),
                      )
                    }
                    className="size-4 rounded border-line text-brand-600 focus:ring-brand-500/30"
                  />
                  Someone with no track record can take this role
                  {role.open_to_beginners ? <Pill tone="green">Beginner</Pill> : null}
                </label>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Openness" subtitle="Encouraged, never required" />
          <div className="p-5 pt-3 space-y-4">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_open_source}
                onChange={(event) =>
                  setForm((current) => ({ ...current, is_open_source: event.target.checked }))
                }
                className="mt-0.5 size-4 rounded border-line text-brand-600 focus:ring-brand-500/30"
              />
              <span>
                <span className="block text-sm font-medium text-strong">
                  Release this work openly
                </span>
                <span className="block text-xs text-muted mt-0.5">
                  You keep the right to commercialise your work. Nothing here transfers
                  ownership to FORGE or to the University.
                </span>
              </span>
            </label>

            {form.is_open_source ? (
              <Field
                label="Licence"
                required
                error={fieldErrors.licence}
                hint="Work published without one is not usable by anyone."
              >
                <Select value={form.licence} onChange={set("licence")}>
                  <option value="">Choose a licence…</option>
                  <option value="MIT">MIT — permissive, simplest</option>
                  <option value="Apache-2.0">Apache 2.0 — permissive, patent grant</option>
                  <option value="GPL-3.0">GPL 3.0 — derivatives stay open</option>
                  <option value="CC-BY-4.0">CC BY 4.0 — for writing and media</option>
                </Select>
              </Field>
            ) : null}
          </div>
        </Card>

        <div className="flex gap-3">
          <Button type="submit" size="lg" loading={create.isPending || addRole.isPending}>
            Save as draft
          </Button>
          <Button type="button" size="lg" variant="ghost" onClick={() => navigate(-1)}>
            Cancel
          </Button>
        </div>
        <p className="text-sm text-muted">
          Saving creates a draft. You submit it for review from the project page, once
          you are happy with it.
        </p>
      </div>
    </form>
  );
}
