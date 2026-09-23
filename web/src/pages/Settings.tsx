import { useState } from "react";
import { AlertTriangle, MailCheck, ShieldCheck } from "lucide-react";
import { api, toForgeError } from "@/api/client";
import { useAccountMutations, useMySkills, useReference } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import {
  Button, Card, CardHeader, Field, FormError, Input, PageHeader, Pill, Select,
  Textarea,
} from "@/components/ui";
import { cn } from "@/lib/cn";

export function Settings() {
  const { member, refreshMember } = useAuth();
  const { data: reference } = useReference();
  const skills = useMySkills();
  const [profile, setProfile] = useState({
    full_name: member?.full_name ?? "",
    preferred_name: member?.preferred_name ?? "",
    headline: member?.headline ?? "",
    bio: member?.bio ?? "",
    location: member?.location ?? "",
    year_of_study: String(member?.year_of_study ?? ""),
    portfolio_is_public: member?.portfolio_is_public ?? true,
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [digest, setDigest] = useState("daily");

  const set = (key: keyof typeof profile) => (event: { target: { value: string } }) =>
    setProfile((current) => ({ ...current, [key]: event.target.value }));

  async function saveProfile() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.patch("/accounts/me/", {
        ...profile,
        year_of_study: profile.year_of_study ? Number(profile.year_of_study) : null,
      });
      await refreshMember();
      setMessage("Saved.");
    } catch (caught) {
      setError(toForgeError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Profile and settings" />

      {/*
        The recovery address gets its own card at the top when it is missing,
        because losing it means losing access to the portfolio at exactly the
        moment it becomes most useful.
      */}
      <RecoveryAddressCard />

      <Card>
        <CardHeader title="Profile" />
        <div className="p-5 pt-3 space-y-4">
          <FormError message={error} />
          {message ? (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              {message}
            </p>
          ) : null}

          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Full name" required>
              <Input value={profile.full_name} onChange={set("full_name")} />
            </Field>
            <Field label="Preferred name" hint="What people call you.">
              <Input value={profile.preferred_name} onChange={set("preferred_name")} />
            </Field>
          </div>

          <Field label="Headline" hint="One line. Appears on your portfolio.">
            <Input
              value={profile.headline}
              onChange={set("headline")}
              maxLength={140}
              placeholder="Third-year cyber security student building things that get used"
            />
          </Field>

          <Field label="About you">
            <Textarea value={profile.bio} onChange={set("bio")} rows={4} maxLength={2000} />
          </Field>

          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Location" hint="County or town. Never finer than that.">
              <Input value={profile.location} onChange={set("location")} maxLength={80} />
            </Field>
            <Field label="Year of study">
              <Select value={profile.year_of_study} onChange={set("year_of_study")}>
                <option value="">—</option>
                {[1, 2, 3, 4, 5, 6].map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={profile.portfolio_is_public}
              onChange={(event) =>
                setProfile((current) => ({
                  ...current,
                  portfolio_is_public: event.target.checked,
                }))
              }
              className="mt-0.5 size-4 rounded border-line text-brand-600 focus:ring-brand-500/30"
            />
            <span>
              <span className="block text-sm font-medium text-strong">
                Keep my portfolio public
              </span>
              <span className="block text-xs text-muted mt-0.5">
                A public portfolio is the point of FORGE, but it stays your choice.
                Turning this off hides the page; it deletes nothing.
              </span>
            </span>
          </label>

          <Button loading={busy} onClick={saveProfile}>
            Save changes
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Skills"
          subtitle="Evidence counts come from confirmed contributions, not from what you claim"
        />
        <div className="p-5 pt-3">
          <div className="flex flex-wrap gap-2 mb-4">
            {(skills.data?.results ?? []).map((userSkill) => (
              <Pill
                key={userSkill.id}
                tone={userSkill.evidence_count ? "green" : "neutral"}
              >
                {userSkill.skill?.name}
                {userSkill.evidence_count ? ` · ${userSkill.evidence_count}` : ""}
              </Pill>
            ))}
            {(skills.data?.results ?? []).length === 0 ? (
              <p className="text-sm text-muted">
                None declared yet. Adding them is how FORGE matches you to open roles.
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            {(reference?.skills ?? [])
              .filter(
                (skill) =>
                  !(skills.data?.results ?? []).some(
                    (userSkill) => userSkill.skill?.id === skill.id,
                  ),
              )
              .slice(0, 30)
              .map((skill) => (
                <button
                  key={skill.id}
                  type="button"
                  onClick={async () => {
                    await api.post("/accounts/my-skills/", {
                      skill_id: skill.id,
                      self_rating: 2,
                    });
                    void skills.refetch();
                  }}
                  className={cn(
                    "rounded-full border border-dashed border-line px-2.5 py-1 text-xs",
                    "text-muted hover:border-brand-400 hover:text-brand-600",
                  )}
                >
                  + {skill.name}
                </button>
              ))}
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Email"
          subtitle="Most people are studying at a distance and many are in employment"
        />
        <div className="p-5 pt-3 space-y-4">
          <Field
            label="How often should FORGE email you?"
            hint="Urgent things — a contribution confirmed or disputed, an application decided — always go out immediately regardless."
          >
            <Select
              value={digest}
              onChange={async (event) => {
                setDigest(event.target.value);
                await api.patch("/notifications/preferences/", {
                  digest_frequency: event.target.value,
                });
              }}
            >
              <option value="immediate">As things happen</option>
              <option value="daily">One email a day</option>
              <option value="weekly">One email a week</option>
              <option value="off">Never — I will check the site</option>
            </Select>
          </Field>
        </div>
      </Card>

      <PasswordCard />

      <Card>
        <CardHeader
          title="Your data"
          subtitle="Data Protection Act, 2019"
        />
        <div className="p-5 pt-3 space-y-4">
          <p className="text-sm text-body leading-relaxed">
            FORGE holds your name, University email, programme, year of study, and
            whatever you have added yourself. No national identification number, no
            financial details.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                const { data } = await api.get("/accounts/me/data/");
                const blob = new Blob([JSON.stringify(data, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "forge-my-data.json";
                anchor.click();
                URL.revokeObjectURL(url);
              }}
              icon={<ShieldCheck className="size-4" aria-hidden />}
            >
              Download everything you hold about me
            </Button>
          </div>
          <p className="text-xs text-muted leading-relaxed">
            You can also have your personal data erased. Confirmed contributions stay
            in the ledger pseudonymously — otherwise your teammates' records, which
            reference the same projects and reviews, would silently lose their backing.
            Ask the faculty advisor to action an erasure.
          </p>
        </div>
      </Card>
    </div>
  );
}


/**
 * The recovery address, with its pending state made visible.
 *
 * The earlier version showed a form, accepted a submission, and then showed
 * exactly the same form again -- because the address is not promoted until the
 * link is followed, and nothing recorded that it was waiting. From the
 * member's side that is indistinguishable from a broken button, which is
 * precisely what it got reported as.
 */
function RecoveryAddressCard() {
  const { member, refreshMember } = useAuth();
  const { setRecoveryEmail, resendRecoveryEmail, cancelRecoveryEmail } =
    useAccountMutations();
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const pending = member?.pending_recovery_email;
  const confirmed = member?.recovery_email;

  async function submit() {
    setError(null);
    setNote(null);
    try {
      const result = await setRecoveryEmail.mutateAsync(address);
      await refreshMember();
      setNote(result.detail);
      setAddress("");
    } catch (caught) {
      setError(toForgeError(caught).message);
    }
  }

  if (confirmed && !pending) {
    return (
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <ShieldCheck className="size-5 text-emerald-600 shrink-0 mt-0.5" aria-hidden />
            <div>
              <p className="font-medium text-strong text-sm">Recovery address confirmed</p>
              <p className="text-sm text-body mt-0.5">
                {confirmed} — this is how you will reach your portfolio after you
                graduate.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setAddress(confirmed)}
          >
            Change it
          </Button>
        </div>

        {address ? (
          <div className="mt-4 pt-4 border-t border-line space-y-3">
            <FormError message={error} />
            <Field label="New personal address">
              <Input
                type="email"
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                autoFocus
              />
            </Field>
            <div className="flex gap-2">
              <Button size="sm" loading={setRecoveryEmail.isPending} onClick={submit}>
                Send confirmation link
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setAddress("")}>
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </Card>
    );
  }

  if (pending) {
    return (
      <Card className="p-5 border-brand-300 bg-brand-50/50 dark:bg-brand-900/20">
        <div className="flex items-start gap-3.5">
          <MailCheck className="size-5 text-brand-600 shrink-0 mt-0.5" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-strong text-sm">
              Waiting for you to confirm {pending}
            </p>
            <p className="text-sm text-body mt-0.5 leading-relaxed">
              We sent a link to that address. Follow it and this becomes your recovery
              address. Until then, the address on your account is unchanged.
            </p>
            {note ? <p className="text-sm text-emerald-700 mt-2">{note}</p> : null}
            <FormError message={error} />
            <div className="flex flex-wrap gap-2 mt-3">
              <Button
                size="sm"
                variant="secondary"
                loading={resendRecoveryEmail.isPending}
                onClick={async () => {
                  setError(null);
                  try {
                    const result = await resendRecoveryEmail.mutateAsync();
                    setNote(result.detail);
                  } catch (caught) {
                    setError(toForgeError(caught).message);
                  }
                }}
              >
                Send it again
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  await cancelRecoveryEmail.mutateAsync();
                  await refreshMember();
                }}
              >
                Use a different address
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-5 border-ember-300 bg-ember-50/60 dark:bg-ember-700/10">
      <div className="flex items-start gap-3.5">
        <AlertTriangle className="size-5 text-ember-600 shrink-0 mt-0.5" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-strong text-sm">Add a personal email address</p>
          <p className="text-sm text-body mt-0.5 mb-3 leading-relaxed">
            Your University address stops working when you graduate. Your portfolio
            does not — but without a recovery address you will not be able to reach it.
          </p>
          <FormError message={error} />
          {note ? <p className="text-sm text-emerald-700 mb-2">{note}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Input
              type="email"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              placeholder="you@gmail.com"
              className="flex-1 min-w-48"
              aria-label="Personal email address"
            />
            <Button
              loading={setRecoveryEmail.isPending}
              disabled={!address.trim()}
              onClick={submit}
            >
              Send confirmation link
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

function PasswordCard() {
  const { member } = useAuth();
  const { changePassword } = useAccountMutations();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  return (
    <Card className={member?.must_change_password ? "border-ember-300" : undefined}>
      <CardHeader
        title="Password"
        subtitle={
          member?.must_change_password
            ? "You are still using the one we emailed you"
            : undefined
        }
      />
      <div className="p-5 pt-3 space-y-4">
        <FormError message={error} />
        {note ? (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
            {note}
          </p>
        ) : null}

        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Current password" required>
            <Input
              type="password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              autoComplete="current-password"
            />
          </Field>
          <Field label="New password" required hint="At least 10 characters.">
            <Input
              type="password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              autoComplete="new-password"
              minLength={10}
            />
          </Field>
        </div>

        <Button
          loading={changePassword.isPending}
          disabled={!current || next.length < 10}
          onClick={async () => {
            setError(null);
            setNote(null);
            try {
              await changePassword.mutateAsync({
                current_password: current,
                new_password: next,
              });
              setCurrent("");
              setNext("");
              setNote("Password changed.");
            } catch (caught) {
              setError(toForgeError(caught).message);
            }
          }}
        >
          Change password
        </Button>

        <p className="text-xs text-muted leading-relaxed">
          FORGE has no self-service password reset. A reset link is a second
          credential travelling by email, and your account can already be recovered
          through the same mailbox. If you are locked out, ask the faculty advisor to
          reissue your credentials.
        </p>
      </div>
    </Card>
  );
}
