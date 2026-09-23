import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, KeyRound, LogIn, ShieldCheck } from "lucide-react";
import { apiOrigin, toForgeError } from "@/api/client";
import { useReference } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import { AuthFooter, AuthHeading, AuthLayout } from "@/components/layout/AuthLayout";
import { Button, Field, FormError, Input } from "@/components/ui";

export function SignIn() {
  const { signIn, status } = useAuth();
  const { data: reference } = useReference();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState<"unverified" | "locked" | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/dashboard" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setProblem(null);
    try {
      await signIn(email, password);
      const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";
      navigate(from, { replace: true });
    } catch (caught) {
      const failure = toForgeError(caught);
      setError(failure.message);
      // The server distinguishes these, and they have different remedies —
      // "wrong password" and "locked out" want very different next steps.
      const raw = JSON.stringify(failure);
      if (/account_locked|Too many failed/i.test(raw)) setProblem("locked");
      else if (/email_not_verified|Confirm your University email/i.test(raw))
        setProblem("unverified");
    } finally {
      setBusy(false);
    }
  }

  const domain = reference?.identity?.university_email_domains?.[0] ?? "students.ouk.ac.ke";

  return (
    <AuthLayout>
      <AuthHeading
        title={<>Welcome back</>}
        subtitle="Sign in with your University email address."
      />

      <form onSubmit={onSubmit} className="space-y-4">
        <FormError message={error} />

        {problem === "unverified" ? (
          <p className="text-sm text-body">
            Not received your details?{" "}
            <Link
              to="/resend-verification"
              className="text-brand-600 font-medium hover:underline"
            >
              Send them again
            </Link>
            .
          </p>
        ) : null}

        {problem === "locked" ? (
          <p className="rounded-lg border border-ember-300 bg-ember-50 px-3.5 py-2.5 text-sm text-ember-800 dark:border-ember-700 dark:bg-ember-700/15 dark:text-ember-200">
            The lock lifts on its own. If you cannot wait, a faculty advisor can clear
            it and email you fresh credentials.
          </p>
        ) : null}

        <Field label="University email" required>
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            placeholder={`st12345678@${domain}`}
            required
            autoFocus
          />
        </Field>

        <Field label="Password" required>
          <div className="relative">
            <Input
              type={reveal ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              className="pr-11"
              required
            />
            <button
              type="button"
              onClick={() => setReveal((value) => !value)}
              className="absolute right-1 top-1/2 -translate-y-1/2 p-2 rounded-md text-muted hover:text-body hover:bg-sunken transition-colors"
              aria-label={reveal ? "Hide password" : "Show password"}
            >
              {reveal ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </Field>

        {/*
          Not "Forgot password?" — FORGE has no self-service reset, by design.
          A reset link is a second credential travelling by email, and the
          account is already recoverable through the same mailbox. Linking to
          a flow that does not exist would be worse than saying so plainly.
        */}
        <div className="flex justify-end -mt-1">
          <Link
            to="/help/signing-in"
            className="text-sm text-brand-600 hover:underline"
          >
            Can't get in?
          </Link>
        </div>

        <Button type="submit" loading={busy} className="w-full" size="lg"
                icon={<LogIn className="size-4" aria-hidden />}>
          Sign in
        </Button>

        {/* Shown only when the University has actually exposed single sign-on.
            A button that merely pretends to work is worse than no button. */}
        {reference?.identity?.oidc_enabled ? (
          <>
            <div className="flex items-center gap-3 py-1">
              <span className="flex-1 h-px bg-line" />
              <span className="text-xs text-muted">or</span>
              <span className="flex-1 h-px bg-line" />
            </div>
            <a
              href={`${apiOrigin}/api/v1/accounts/oidc/start/`}
              className="flex items-center justify-center gap-2.5 w-full h-12 rounded-lg border border-line bg-card text-sm font-medium text-strong hover:bg-sunken transition-colors"
            >
              <ShieldCheck className="size-4.5 text-brand-600" aria-hidden />
              Continue with University sign-on
            </a>
          </>
        ) : null}
      </form>

      <AuthFooter>
        <p className="text-sm text-muted">
          No account yet?{" "}
          <Link to="/register" className="text-brand-600 font-semibold hover:underline">
            Join FORGE
          </Link>
        </p>
        <p className="flex items-start gap-2 text-xs text-muted mt-3 leading-relaxed">
          <KeyRound className="size-3.5 shrink-0 mt-0.5" aria-hidden />
          Graduated? Sign in with the personal recovery address on your account — your
          portfolio does not expire when your University address does.
        </p>
      </AuthFooter>
    </AuthLayout>
  );
}
