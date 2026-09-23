import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { CheckCircle2, MailCheck } from "lucide-react";
import { api, toForgeError } from "@/api/client";
import { useReference } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import { Button, Field, FormError, Input, Select } from "@/components/ui";
import { AuthFooter, AuthHeading, AuthLayout } from "@/components/layout/AuthLayout";

export function Register() {
  const { status } = useAuth();
  const { data: reference } = useReference();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    recovery_email: "",
    programme_id: "",
    year_of_study: "",
  });
  const [slug, setSlug] = useState("");
  const [slugState, setSlugState] = useState<"idle" | "checking" | "free" | "taken">("idle");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  // Ask the server for a slug suggestion once the member has typed a name.
  useEffect(() => {
    const name = form.full_name.trim();
    if (!name || slug) return;
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<{ suggestion: string }>(
          "/accounts/slug-availability/",
          { params: { name } },
        );
        setSlug(data.suggestion);
      } catch {
        /* a suggestion is a convenience; the member can type their own */
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [form.full_name, slug]);

  useEffect(() => {
    if (!slug) return setSlugState("idle");
    setSlugState("checking");
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<{ available: boolean }>(
          "/accounts/slug-availability/",
          { params: { slug } },
        );
        setSlugState(data.available ? "free" : "taken");
      } catch {
        setSlugState("idle");
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [slug]);

  if (status === "authenticated") return <Navigate to="/dashboard" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setFieldErrors({});
    try {
      await api.post("/accounts/register/", {
        full_name: form.full_name,
        email: form.email,
        recovery_email: form.recovery_email || undefined,
        programme_id: form.programme_id || undefined,
        year_of_study: form.year_of_study ? Number(form.year_of_study) : undefined,
        public_slug: slug || undefined,
      });
      setDone(true);
    } catch (caught) {
      const failure = toForgeError(caught);
      setError(failure.message);
      setFieldErrors(failure.fieldErrors);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <AuthLayout>
        <div className="text-center">
          <MailCheck className="size-12 text-brand-600 mx-auto" aria-hidden />
            <h1 className="text-2xl font-bold text-strong mt-5">Check your inbox</h1>
            <p className="text-sm text-body mt-3 leading-relaxed">
              If <strong className="text-strong">{form.email}</strong> is a valid
              University address, your sign-in details are on their way to it. You
              will choose your own password the first time you sign in.
            </p>
            <p className="text-sm text-muted mt-4 leading-relaxed">
              We email the credentials rather than letting you pick a password here,
              so that only somebody who can actually read that mailbox can open the
              account.
            </p>
            <p className="text-sm text-muted mt-3">
              Nothing after a few minutes? Check your spam folder.
            </p>
          <Link
            to="/sign-in"
            className="inline-flex items-center justify-center w-full mt-8 h-11 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700"
          >
            Go to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <AuthLayout wide>
      <AuthHeading
        title="Join FORGE"
        subtitle="Open to every student of the Open University of Kenya. Staff, alumni and partners join by invitation."
      />

      <form onSubmit={onSubmit} className="space-y-4">
            <FormError message={error} />

            <Field label="Full name" required error={fieldErrors.full_name}>
              <Input
                value={form.full_name}
                onChange={set("full_name")}
                autoComplete="name"
                required
              />
            </Field>

            <Field
              label="University email"
              required
              error={fieldErrors.email}
              hint="This is what establishes you as a member of the University."
            >
              <Input
                type="email"
                value={form.email}
                onChange={set("email")}
                autoComplete="username"
                placeholder="st12345678@students.ouk.ac.ke"
                required
              />
            </Field>

            <Field
              label="Personal email"
              error={fieldErrors.recovery_email}
              hint="Strongly recommended. Your University address stops working when you graduate — your portfolio does not."
            >
              <Input
                type="email"
                value={form.recovery_email}
                onChange={set("recovery_email")}
                placeholder="you@gmail.com"
              />
            </Field>

            <div className="grid grid-cols-3 gap-3">
              <Field label="Programme" className="col-span-2" error={fieldErrors.programme_id}>
                <Select value={form.programme_id} onChange={set("programme_id")}>
                  <option value="">Select…</option>
                  {reference?.programmes.map((programme) => (
                    <option key={programme.id} value={programme.id}>
                      {programme.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Year" error={fieldErrors.year_of_study}>
                <Select value={form.year_of_study} onChange={set("year_of_study")}>
                  <option value="">—</option>
                  {[1, 2, 3, 4, 5, 6].map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field
              label="Your portfolio address"
              error={fieldErrors.public_slug}
              hint={
                slugState === "taken"
                  ? undefined
                  : "Where employers will find your record. Choose carefully — changing it later breaks links you have shared."
              }
            >
              <div className="flex items-center rounded-lg border border-line bg-card focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20">
                <span className="pl-3 text-sm text-muted shrink-0">forge.ouk.ac.ke/p/</span>
                <input
                  value={slug}
                  onChange={(event) =>
                    setSlug(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))
                  }
                  className="flex-1 min-w-0 bg-transparent h-10 pr-3 text-sm text-strong focus:outline-none"
                  placeholder="your-name"
                />
                {slugState === "free" ? (
                  <CheckCircle2 className="size-4 text-emerald-500 mr-3 shrink-0" aria-hidden />
                ) : null}
              </div>
              {slugState === "taken" ? (
                <span className="block text-sm text-red-600 mt-1.5">
                  That address is taken. Try another.
                </span>
              ) : null}
            </Field>

            <p className="text-sm text-body rounded-lg bg-sunken p-3.5 leading-relaxed">
              You do not choose a password here. We generate one and email it to your
              University address, so that only somebody who can read that mailbox can
              open the account. You will replace it the first time you sign in.
            </p>

            <Button
              type="submit"
              loading={busy}
              className="w-full"
              size="lg"
              disabled={slugState === "taken"}
            >
              Email me my sign-in details
            </Button>
          </form>

      <AuthFooter>
        <p className="text-sm text-muted">
          Already a member?{" "}
          <Link to="/sign-in" className="text-brand-600 font-semibold hover:underline">
            Sign in
          </Link>
        </p>
      </AuthFooter>
    </AuthLayout>
  );
}
