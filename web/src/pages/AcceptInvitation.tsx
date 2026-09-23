import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MailCheck, XCircle } from "lucide-react";
import { api, toForgeError } from "@/api/client";
import { useReference } from "@/api/queries";
import { AuthFooter, AuthLayout } from "@/components/layout/AuthLayout";
import { Button, Field, FormError, Input, Loading, Pill, Select } from "@/components/ui";
import type { InvitationPreview } from "@/api/types";

/**
 * Accepting an invitation.
 *
 * The invitation is previewed before anything is filled in — who sent it, in
 * what capacity, and what they wrote. Nobody should have to commit to an
 * account before seeing what they are being asked to join, and a bare form
 * behind a link from a stranger reads like a phishing page.
 */
export function AcceptInvitation() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { data: reference } = useReference();

  const [invitation, setInvitation] = useState<InvitationPreview | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "invalid" | "done">("loading");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({ full_name: "", programme_id: "", year_of_study: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setState("invalid");
      setMessage("That link is missing its token. Use the link from your email exactly as it was sent.");
      return;
    }
    api
      .get<InvitationPreview>("/accounts/accept-invitation/", { params: { token } })
      .then(({ data }) => {
        setInvitation(data);
        setForm((current) => ({ ...current, full_name: data.full_name || "" }));
        setState("ready");
      })
      .catch((caught) => {
        setState("invalid");
        setMessage(toForgeError(caught).message);
      });
  }, [token]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/accounts/accept-invitation/", {
        token,
        full_name: form.full_name,
        programme_id: form.programme_id || undefined,
        year_of_study: form.year_of_study ? Number(form.year_of_study) : undefined,
      });
      setState("done");
    } catch (caught) {
      setError(toForgeError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout wide>
      <div>
          {state === "loading" ? <Loading label="Checking your invitation" /> : null}

          {state === "invalid" ? (
            <div className="text-center">
              <XCircle className="size-12 text-red-500 mx-auto" aria-hidden />
              <h1 className="text-2xl font-bold text-strong mt-5">
                That invitation is not valid
              </h1>
              <p className="text-sm text-body mt-3">{message}</p>
              <p className="text-sm text-muted mt-4">
                Ask whoever invited you to send it again.
              </p>
              <Link
                to="/sign-in"
                className="inline-block mt-7 text-sm text-brand-600 font-medium hover:underline"
              >
                Back to sign in
              </Link>
            </div>
          ) : null}

          {state === "done" ? (
            <div className="text-center">
              <MailCheck className="size-12 text-brand-600 mx-auto" aria-hidden />
              <h1 className="text-2xl font-bold text-strong mt-5">Your account is ready</h1>
              <p className="text-sm text-body mt-3 leading-relaxed">
                We have sent your sign-in details to{" "}
                <strong className="text-strong">{invitation?.email}</strong>. You will
                choose your own password the first time you sign in.
              </p>
              <Link
                to="/sign-in"
                className="inline-flex items-center justify-center mt-7 h-11 px-6 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700"
              >
                Go to sign in
              </Link>
            </div>
          ) : null}

          {state === "ready" && invitation ? (
            <>
              <img src="/forge-logo.png" srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x" alt="" className="size-12 mb-6 lg:hidden" />
              <h1 className="text-2xl font-bold text-strong">
                {invitation.invited_by_name} invited you
              </h1>
              <p className="text-sm text-muted mt-1.5">
                Joining as <strong className="text-strong">{invitation.email}</strong>
              </p>

              {invitation.role_label ? (
                <div className="mt-4">
                  <Pill tone="brand">{invitation.role_label}</Pill>
                </div>
              ) : null}

              {invitation.message ? (
                <blockquote className="mt-4 border-l-3 border-brand-500 bg-sunken rounded-r-lg px-4 py-3 text-sm text-body italic">
                  {invitation.message}
                </blockquote>
              ) : null}

              <form onSubmit={onSubmit} className="mt-6 space-y-4">
                <FormError message={error} />

                <Field label="Your name" required>
                  <Input
                    value={form.full_name}
                    onChange={(event) =>
                      setForm((c) => ({ ...c, full_name: event.target.value }))
                    }
                    required
                  />
                </Field>

                {invitation.kind === "student" ? (
                  <div className="grid grid-cols-3 gap-3">
                    <Field label="Programme" className="col-span-2">
                      <Select
                        value={form.programme_id}
                        onChange={(event) =>
                          setForm((c) => ({ ...c, programme_id: event.target.value }))
                        }
                      >
                        <option value="">Select…</option>
                        {(reference?.programmes ?? []).map((programme) => (
                          <option key={programme.id} value={programme.id}>
                            {programme.name}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label="Year">
                      <Select
                        value={form.year_of_study}
                        onChange={(event) =>
                          setForm((c) => ({ ...c, year_of_study: event.target.value }))
                        }
                      >
                        <option value="">—</option>
                        {[1, 2, 3, 4, 5, 6].map((year) => (
                          <option key={year} value={year}>
                            {year}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                ) : null}

                <Button type="submit" loading={busy} className="w-full" size="lg">
                  Accept and create my account
                </Button>

                <p className="text-xs text-muted leading-relaxed">
                  We will email your sign-in details to {invitation.email}. You choose
                  your own password the first time you sign in.
                </p>
              </form>
            </>
        ) : null}
      </div>
      <AuthFooter />
    </AuthLayout>
  );
}
