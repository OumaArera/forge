import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { Button, Field, Input } from "@/components/ui";
import { AuthFooter, AuthHeading, AuthLayout } from "@/components/layout/AuthLayout";

export function ResendVerification() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await api.post("/accounts/resend-verification/", { email });
    } catch {
      /* The endpoint answers identically either way on purpose: whether an
         address is registered is not something an anonymous caller learns. */
    } finally {
      setBusy(false);
      setSent(true);
    }
  }

  return (
    <AuthLayout>
      <AuthHeading
        title="Send it again"
        subtitle="We will re-send your sign-in details to your University address."
      />
          {sent ? (
            <p className="text-sm text-body mt-4 leading-relaxed">
              If that address has an unconfirmed FORGE account, a new link is on its
              way. It is good for 24 hours.
            </p>
          ) : (
            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <Field label="University email" required>
                <Input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoFocus
                />
              </Field>
              <Button type="submit" loading={busy} className="w-full" size="lg">
                Send the link
              </Button>
            </form>
          )}
      <AuthFooter>
        <Link
          to="/sign-in"
          className="text-sm text-brand-600 font-semibold hover:underline"
        >
          Back to sign in
        </Link>
      </AuthFooter>
    </AuthLayout>
  );
}
