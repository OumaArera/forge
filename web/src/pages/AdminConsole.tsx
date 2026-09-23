import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, CheckCircle2, KeyRound, Mail, MailWarning, Send, ShieldCheck,
  Trash2, Unlock, UserPlus, Users, X,
} from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { toForgeError } from "@/api/client";
import {
  useAdminMembers, useAdminMutations, useAdminOverview, useEmailLog, useInvitations,
  useReference, useRoleGrants,
} from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import {
  Avatar, Button, Card, CardHeader, EmptyState, Field, FormError, Input, Loading,
  PageHeader, Pill, Select, StatTile, Textarea,
} from "@/components/ui";
import { cn } from "@/lib/cn";
import { ROLE_DESCRIPTIONS, ROLE_LABELS } from "@/api/types";

const TABS = ["Overview", "Members", "Invitations", "Roles", "Email"] as const;
type Tab = (typeof TABS)[number];

export function AdminConsole() {
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("Overview");

  if (!can("grant_roles")) {
    return (
      <Card>
        <EmptyState
          icon={<ShieldCheck className="size-10" aria-hidden />}
          title="Not your console"
          description="Administration is restricted to the faculty advisor and platform maintainers."
        />
      </Card>
    );
  }

  return (
    <div>
      <PageHeader
        title="Administration"
        description="Members, invitations, roles and access. Every action here is written to the audit log."
      />

      <div className="border-b border-line mb-6">
        <div className="flex gap-1 -mb-px overflow-x-auto" role="tablist">
          {TABS.map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={tab === name}
              onClick={() => setTab(name)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
                tab === name
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-muted hover:text-body",
              )}
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      {tab === "Overview" ? <Overview /> : null}
      {tab === "Members" ? <Members /> : null}
      {tab === "Invitations" ? <Invitations /> : null}
      {tab === "Roles" ? <Roles /> : null}
      {tab === "Email" ? <EmailTab /> : null}
    </div>
  );
}

function Overview() {
  const { data, isLoading } = useAdminOverview();
  if (isLoading || !data) return <Loading />;

  const failed = data.email.failed_this_week;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Members"
          value={data.members.total}
          icon={<Users className="size-5" aria-hidden />}
          hint={`${data.members.joined_this_week} joined this week`}
        />
        <StatTile
          label="Active"
          value={data.members.active}
          icon={<CheckCircle2 className="size-5" aria-hidden />}
          tone="green"
          hint={`${data.members.alumni} alumni`}
        />
        <StatTile
          label="Suspended"
          value={data.members.suspended}
          icon={<AlertTriangle className="size-5" aria-hidden />}
          tone={data.members.suspended ? "red" : "neutral"}
        />
        <StatTile
          label="Confirmed contributions"
          value={data.evidence.ledger_entries}
          icon={<ShieldCheck className="size-5" aria-hidden />}
          tone="ember"
          hint={`${data.evidence.awaiting_confirmation} awaiting`}
        />
      </div>

      {/*
        Mail health sits on the first screen rather than three clicks away,
        because it is the thing most likely to be quietly broken, and a
        platform that cannot send a verification link is a platform nobody
        new can join.
      */}
      <Card
        className={cn(
          "p-5",
          failed > 0
            ? "border-red-300 bg-red-50/50 dark:bg-red-950/20"
            : "border-emerald-300 bg-emerald-50/50 dark:bg-emerald-950/20",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            {failed > 0 ? (
              <MailWarning className="size-6 text-red-600 shrink-0" aria-hidden />
            ) : (
              <Mail className="size-6 text-emerald-600 shrink-0" aria-hidden />
            )}
            <div>
              <p className="font-semibold text-strong">
                {failed > 0
                  ? `${failed} message${failed === 1 ? "" : "s"} failed this week`
                  : "Email is going out"}
              </p>
              <p className="text-sm text-body mt-0.5">
                {data.email.sent_this_week} accepted by the mail server in the last
                seven days.
                {failed > 0
                  ? " Failures usually mean the host is unreachable or the credentials changed."
                  : ""}
              </p>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader title="Accounts by status" />
          <div className="p-5 pt-3 space-y-2">
            <Row label="Active" value={data.members.active} />
            <Row label="Alumni" value={data.members.alumni} />
            <Row label="Pending" value={data.members.pending} />
            <Row label="Suspended" value={data.members.suspended} tone="red" />
            <Row
              label="Never signed in"
              value={data.members.never_signed_in}
              hint="Credentials sent but never used"
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Roles held" subtitle="Active grants" />
          <div className="p-5 pt-3 space-y-2">
            {Object.entries(data.roles).length === 0 ? (
              <p className="text-sm text-muted">No roles granted yet.</p>
            ) : (
              Object.entries(data.roles).map(([role, count]) => (
                <Row key={role} label={ROLE_LABELS[role] ?? role} value={count} />
              ))
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Invitations" />
          <div className="p-5 pt-3 space-y-2">
            {Object.entries(data.invitations).length === 0 ? (
              <p className="text-sm text-muted">None issued.</p>
            ) : (
              Object.entries(data.invitations).map(([status, count]) => (
                <Row key={status} label={status} value={count} />
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint?: string;
  tone?: "red";
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-sm text-body">
        {/* first-letter only: `capitalize` title-cases every word, which turned
            "Never signed in" into "Never Signed In" and the hint with it. */}
        <span className="first-letter:uppercase">{label}</span>
        {hint ? <span className="block text-xs text-muted">{hint}</span> : null}
      </span>
      <span
        className={cn(
          "text-sm font-semibold tabular-nums",
          tone === "red" && value > 0 ? "text-red-600" : "text-strong",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function Members() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const { data, isLoading } = useAdminMembers({
    search: search || undefined,
    status: status || undefined,
  });
  const { suspend, reinstate, resetPassword, unlock } = useAdminMutations();
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suspending, setSuspending] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  async function run(slug: string, action: () => Promise<unknown>, message?: string) {
    setBusy(slug);
    setError(null);
    setNote(null);
    try {
      const result = (await action()) as { detail?: string } | undefined;
      setNote(result?.detail ?? message ?? "Done.");
    } catch (caught) {
      setError(toForgeError(caught).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name or email…"
            className="flex-1"
            aria-label="Search members"
          />
          <Select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="sm:w-48"
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="alumnus">Alumni</option>
            <option value="suspended">Suspended</option>
            <option value="pending">Pending</option>
            <option value="closed">Closed</option>
          </Select>
        </div>
      </Card>

      <FormError message={error} />
      {note ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
          {note}
        </p>
      ) : null}

      {isLoading ? (
        <Loading />
      ) : (
        <div className="space-y-2">
          {(data?.results ?? []).map((member) => (
            <Card key={member.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-start gap-3.5 min-w-0">
                  <Avatar name={member.display_name ?? "?"} src={member.avatar} size={40} />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/p/${member.public_slug}`}
                        className="font-medium text-strong hover:text-brand-600"
                      >
                        {member.display_name}
                      </Link>
                      <Pill
                        tone={
                          member.status === "active"
                            ? "green"
                            : member.status === "suspended"
                              ? "red"
                              : "neutral"
                        }
                      >
                        {member.status}
                      </Pill>
                      {member.must_change_password ? (
                        <Pill tone="ember">Password not yet chosen</Pill>
                      ) : null}
                    </div>
                    <p className="text-sm text-muted truncate">{member.email}</p>
                    <p className="text-xs text-muted mt-0.5">
                      {member.programme?.name ?? member.school?.name ?? "—"}
                      {member.last_seen_at
                        ? ` · last seen ${formatDistanceToNow(new Date(member.last_seen_at), { addSuffix: true })}`
                        : " · never signed in"}
                    </p>
                    {(member.roles ?? []).length ? (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {(member.roles ?? []).map((role) => (
                          <Pill key={role} tone="brand">
                            {ROLE_LABELS[role] ?? role}
                          </Pill>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={busy === member.public_slug}
                    onClick={() =>
                      run(member.public_slug!, () =>
                        resetPassword.mutateAsync(member.public_slug!),
                      )
                    }
                    icon={<KeyRound className="size-3.5" aria-hidden />}
                  >
                    Reissue credentials
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      run(member.public_slug!, () => unlock.mutateAsync(member.public_slug!))
                    }
                    icon={<Unlock className="size-3.5" aria-hidden />}
                  >
                    Unlock
                  </Button>
                  {member.status === "suspended" ? (
                    <Button
                      size="sm"
                      onClick={() =>
                        run(member.public_slug!, () =>
                          reinstate.mutateAsync(member.public_slug!),
                        "Reinstated.")
                      }
                    >
                      Reinstate
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => {
                        setSuspending(
                          suspending === member.public_slug ? null : member.public_slug!,
                        );
                        setReason("");
                      }}
                    >
                      Suspend
                    </Button>
                  )}
                </div>
              </div>

              {suspending === member.public_slug ? (
                <div className="mt-4 pt-4 border-t border-line space-y-3">
                  <Field
                    label="Why is this account being suspended?"
                    required
                    hint="Written to the audit log, and it is what you would have to justify if the decision is appealed."
                  >
                    <Textarea
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      rows={2}
                      autoFocus
                    />
                  </Field>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={reason.trim().length < 10}
                      onClick={async () => {
                        await run(member.public_slug!, () =>
                          suspend.mutateAsync({ slug: member.public_slug!, reason }),
                        "Account suspended.");
                        setSuspending(null);
                      }}
                    >
                      Confirm suspension
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setSuspending(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Invitations() {
  const { data, isLoading } = useInvitations();
  const { invite, resendInvitation, revokeInvitation } = useAdminMutations();
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    kind: "external",
    role: "",
    message: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,380px)_1fr] items-start">
      <Card>
        <CardHeader
          title="Invite somebody"
          subtitle="For people who cannot use the open route"
        />
        <div className="p-5 pt-3 space-y-4">
          <p className="text-sm text-muted">
            Students with a University address register themselves and are never
            invited. This is for staff, alumni returning to mentor, and external
            partners — whose accounts skip the domain check, which is why each one
            is issued by a named person.
          </p>

          <FormError message={error} />
          {note ? (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              {note}
            </p>
          ) : null}

          <Field label="Email address" required>
            <Input type="email" value={form.email} onChange={set("email")} />
          </Field>
          <Field label="Name" hint="Optional — they can set it themselves.">
            <Input value={form.full_name} onChange={set("full_name")} />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Account type" required>
              <Select value={form.kind} onChange={set("kind")}>
                <option value="external">External partner</option>
                <option value="staff">University staff</option>
                <option value="alumnus">Alumnus</option>
                <option value="student">Student</option>
              </Select>
            </Field>
            <Field label="Grant a role">
              <Select value={form.role} onChange={set("role")}>
                <option value="">No role</option>
                {Object.entries(ROLE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          {form.role ? (
            <p className="text-xs text-body rounded-lg bg-sunken p-3">
              {ROLE_DESCRIPTIONS[form.role]}
            </p>
          ) : null}

          <Field
            label="A note to them"
            hint="Included in the email. An invitation from a stranger with no context reads like spam."
          >
            <Textarea value={form.message} onChange={set("message")} rows={3} />
          </Field>

          <Button
            className="w-full"
            loading={invite.isPending}
            disabled={!form.email.trim()}
            icon={<Send className="size-4" aria-hidden />}
            onClick={async () => {
              setError(null);
              setNote(null);
              try {
                await invite.mutateAsync({
                  ...form,
                  role: form.role || undefined,
                });
                setNote(`Invitation sent to ${form.email}.`);
                setForm({ email: "", full_name: "", kind: "external", role: "", message: "" });
              } catch (caught) {
                setError(toForgeError(caught).message);
              }
            }}
          >
            Send invitation
          </Button>
        </div>
      </Card>

      <div className="space-y-2">
        {isLoading ? (
          <Loading />
        ) : (data?.results ?? []).length === 0 ? (
          <Card>
            <EmptyState
              icon={<UserPlus className="size-10" aria-hidden />}
              title="No invitations yet"
              description="Most people join by registering with their University address. Invitations are for everybody else."
            />
          </Card>
        ) : (
          (data?.results ?? []).map((invitation) => (
            <Card key={invitation.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-strong">{invitation.email}</span>
                    <Pill
                      tone={
                        invitation.status === "accepted"
                          ? "green"
                          : invitation.status === "pending"
                            ? "ember"
                            : "neutral"
                      }
                    >
                      {invitation.status_display}
                    </Pill>
                    {invitation.role_label ? (
                      <Pill tone="brand">{invitation.role_label}</Pill>
                    ) : null}
                  </div>
                  <p className="text-xs text-muted mt-1">
                    {invitation.kind} · invited by {invitation.invited_by_display}
                    {invitation.expires_at && invitation.status === "pending"
                      ? ` · expires ${formatDistanceToNow(new Date(invitation.expires_at), { addSuffix: true })}`
                      : ""}
                    {invitation.sent_count && invitation.sent_count > 1
                      ? ` · sent ${invitation.sent_count} times`
                      : ""}
                  </p>
                  {invitation.message ? (
                    <p className="text-sm text-muted mt-1.5 italic line-clamp-2">
                      "{invitation.message}"
                    </p>
                  ) : null}
                </div>

                {invitation.is_usable ? (
                  <div className="flex gap-2 shrink-0">
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={resendInvitation.isPending}
                      onClick={() => void resendInvitation.mutateAsync(invitation.id)}
                    >
                      Resend
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void revokeInvitation.mutateAsync(invitation.id)}
                      icon={<Trash2 className="size-3.5" aria-hidden />}
                    >
                      Revoke
                    </Button>
                  </div>
                ) : null}
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

function Roles() {
  const { data, isLoading } = useRoleGrants();
  const { data: members } = useAdminMembers({ page_size: 100 });
  const { data: reference } = useReference();
  const { grantRole, revokeRole } = useAdminMutations();
  const [form, setForm] = useState({ user_id: "", role: "", discipline_area_id: "" });
  const [error, setError] = useState<string | null>(null);

  const active = (data?.results ?? []).filter((grant) => grant.is_active);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,380px)_1fr] items-start">
      <Card>
        <CardHeader title="Grant a role" subtitle="Roles are grants, not attributes" />
        <div className="p-5 pt-3 space-y-4">
          <p className="text-sm text-muted">
            Every grant records who made it and when it expires. A student-held role
            should normally expire at the end of a trimester and be renewed rather
            than left standing.
          </p>

          <FormError message={error} />

          <Field label="Member" required>
            <Select
              value={form.user_id}
              onChange={(event) => setForm((c) => ({ ...c, user_id: event.target.value }))}
            >
              <option value="">Choose a member…</option>
              {(members?.results ?? []).map((member) => (
                <option key={member.id} value={member.id}>
                  {member.display_name} — {member.email}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Role" required>
            <Select
              value={form.role}
              onChange={(event) => setForm((c) => ({ ...c, role: event.target.value }))}
            >
              <option value="">Choose a role…</option>
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>

          {form.role ? (
            <p className="text-xs text-body rounded-lg bg-sunken p-3">
              {ROLE_DESCRIPTIONS[form.role]}
            </p>
          ) : null}

          <Field
            label="Scope to a discipline"
            hint="Optional. A community lead is usually scoped to one area."
          >
            <Select
              value={form.discipline_area_id}
              onChange={(event) =>
                setForm((c) => ({ ...c, discipline_area_id: event.target.value }))
              }
            >
              <option value="">Platform-wide</option>
              {(reference?.discipline_areas ?? []).map((area) => (
                <option key={area.id} value={area.id}>
                  {area.name}
                </option>
              ))}
            </Select>
          </Field>

          <Button
            className="w-full"
            loading={grantRole.isPending}
            disabled={!form.user_id || !form.role}
            onClick={async () => {
              setError(null);
              try {
                await grantRole.mutateAsync({
                  user_id: form.user_id,
                  role: form.role,
                  discipline_area_id: form.discipline_area_id || undefined,
                });
                setForm({ user_id: "", role: "", discipline_area_id: "" });
              } catch (caught) {
                setError(toForgeError(caught).message);
              }
            }}
          >
            Grant this role
          </Button>
        </div>
      </Card>

      <div className="space-y-2">
        {isLoading ? (
          <Loading />
        ) : active.length === 0 ? (
          <Card>
            <EmptyState
              icon={<ShieldCheck className="size-10" aria-hidden />}
              title="No roles granted"
              description="Nobody holds a standing role yet."
            />
          </Card>
        ) : (
          active.map((grant) => (
            <Card key={grant.id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-strong">{grant.role_display}</span>
                    {grant.discipline_area ? (
                      <Pill tone="purple">{grant.discipline_area.name}</Pill>
                    ) : (
                      <Pill>Platform-wide</Pill>
                    )}
                  </div>
                  <p className="text-xs text-muted mt-1">
                    Granted{" "}
                    {grant.granted_at
                      ? format(new Date(grant.granted_at), "d MMM yyyy")
                      : ""}
                    {grant.granted_by_name ? ` by ${grant.granted_by_name}` : ""}
                    {grant.expires_at
                      ? ` · expires ${format(new Date(grant.expires_at), "d MMM yyyy")}`
                      : " · no expiry"}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => void revokeRole.mutateAsync(grant.id)}
                  icon={<X className="size-3.5" aria-hidden />}
                >
                  Revoke
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

function EmailTab() {
  const [status, setStatus] = useState("");
  const { data, isLoading } = useEmailLog({ status: status || undefined });

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="sm:w-48"
            aria-label="Filter by status"
          >
            <option value="">Everything</option>
            <option value="sent">Accepted</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </Select>
          <p className="text-sm text-muted">
            What the platform has tried to send. No message body is kept —
            verification links and generated passwords pass through this path.
          </p>
        </div>
      </Card>

      {isLoading ? (
        <Loading />
      ) : (data?.results ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={<Mail className="size-10" aria-hidden />}
            title="Nothing sent yet"
            description="Every message FORGE attempts appears here, whether it succeeded or not."
          />
        </Card>
      ) : (
        <div className="space-y-2">
          {(data?.results ?? []).map((entry) => (
            <Card key={entry.id} className="p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill
                      tone={
                        entry.status === "sent"
                          ? "green"
                          : entry.status === "failed"
                            ? "red"
                            : "ember"
                      }
                    >
                      {entry.status_display}
                    </Pill>
                    <span className="text-sm font-medium text-strong truncate">
                      {entry.to_address}
                    </span>
                    <Pill>{entry.template}</Pill>
                  </div>
                  <p className="text-xs text-muted mt-1 truncate">{entry.subject}</p>
                  {entry.error ? (
                    <p className="text-xs text-red-600 mt-1 font-mono">{entry.error}</p>
                  ) : null}
                </div>
                <span className="text-xs text-muted shrink-0">
                  {entry.created_at
                    ? formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })
                    : ""}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
