import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound } from "lucide-react";
import { toForgeError } from "@/api/client";
import { useAccountMutations } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import { AuthFooter, AuthLayout } from "@/components/layout/AuthLayout";
import { Button, Field, FormError, Input } from "@/components/ui";

/**
 * The forced password change.
 *
 * A member signed in with a generated password is held here until they choose
 * their own. The point is that a credential which has travelled through email
 * — and is therefore sitting in an inbox, possibly forwarded, possibly still
 * in a sent folder somewhere — does not stay valid indefinitely.
 */
export function ChangePassword() {
  const { member, refreshMember } = useAuth();
  const { changePassword } = useAccountMutations();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const mismatch = confirm.length > 0 && next !== confirm;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    try {
      await changePassword.mutateAsync({
        current_password: current,
        new_password: next,
      });
      await refreshMember();
      navigate("/dashboard", { replace: true });
    } catch (caught) {
      const failure = toForgeError(caught);
      setError(failure.message);
      setFieldErrors(failure.fieldErrors);
    }
  }

  return (
    <AuthLayout>
      <div>
        <span className="grid place-items-center size-12 rounded-xl bg-brand-600 text-white mb-5">
            <KeyRound className="size-6" aria-hidden />
          </span>
          <h1 className="text-2xl font-bold text-strong">Choose your own password</h1>
          <p className="text-sm text-muted mt-1.5 leading-relaxed">
            You are signed in with the password we emailed to {member?.email}. Replace
            it and that one stops working.
          </p>

          <form onSubmit={onSubmit} className="mt-7 space-y-4">
            <FormError message={error} />

            <Field
              label="The password we emailed you"
              required
              error={fieldErrors.current_password}
            >
              <Input
                type="password"
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
                autoComplete="current-password"
                required
                autoFocus
              />
            </Field>

            <Field
              label="Your new password"
              required
              error={fieldErrors.new_password}
              hint="At least 10 characters. Not something you use elsewhere."
            >
              <Input
                type="password"
                value={next}
                onChange={(event) => setNext(event.target.value)}
                autoComplete="new-password"
                minLength={10}
                required
              />
            </Field>

            <Field
              label="Type it again"
              required
              error={mismatch ? "Those do not match." : undefined}
            >
              <Input
                type="password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                autoComplete="new-password"
                required
              />
            </Field>

            <Button
              type="submit"
              loading={changePassword.isPending}
              disabled={mismatch || next.length < 10}
              className="w-full"
              size="lg"
            >
              Set my password
            </Button>
        </form>
      </div>
      <AuthFooter />
    </AuthLayout>
  );
}
