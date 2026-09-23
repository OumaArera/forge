import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, XCircle } from "lucide-react";
import { api, toForgeError } from "@/api/client";
import { AuthFooter, AuthLayout } from "@/components/layout/AuthLayout";
import { Loading } from "@/components/ui";

type Outcome = {
  already_confirmed: boolean;
  purpose: "recovery_email" | "registration";
  confirmed_address: string;
};

export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "done" | "failed">("working");
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [message, setMessage] = useState("");
  const [code, setCode] = useState("");

  /**
   * A verification link is single-use, so this request must fire exactly once.
   *
   * Without the guard, React's development StrictMode runs the effect twice:
   * the first request consumes the token and succeeds, the second finds it
   * consumed and fails, and because the failure resolves last it is the one
   * the member sees. The link worked; the screen said it had not.
   *
   * The server now also reports an already-confirmed link as success, so this
   * is belt and braces — but a token should not be spent twice regardless,
   * and the same double-fire happens on a double-click in production.
   */
  const attempted = useRef<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("failed");
      setCode("missing_token");
      setMessage(
        "That link is missing its token. Open the link from your email exactly " +
          "as it was sent, without editing it.",
      );
      return;
    }
    if (attempted.current === token) return;
    attempted.current = token;

    api
      .post<Outcome>("/accounts/verify-email/", { token })
      .then(({ data }) => {
        setOutcome(data);
        setState("done");
      })
      .catch((caught) => {
        const failure = toForgeError(caught);
        setState("failed");
        setCode(failure.code);
        setMessage(failure.message);
      });
  }, [token]);

  const isRecovery = outcome?.purpose === "recovery_email";

  return (
    <AuthLayout>
      <div className="text-center">
        {state === "working" ? <Loading label="Confirming your address" /> : null}

        {state === "done" ? (
          <>
            <CheckCircle2 className="size-12 text-emerald-500 mx-auto" aria-hidden />
            <h1 className="text-2xl font-bold text-strong mt-5">
              {isRecovery ? "Recovery address confirmed" : "You're in"}
            </h1>
            <p className="text-sm text-body mt-3 leading-relaxed">
              {isRecovery ? (
                <>
                  <strong className="text-strong">{outcome?.confirmed_address}</strong>{" "}
                  is now the recovery address on your account. It will still work
                  after you graduate, which is when your portfolio matters most.
                </>
              ) : (
                <>Your email address is confirmed. Sign in and propose something.</>
              )}
            </p>
            {outcome?.already_confirmed ? (
              <p className="text-xs text-muted mt-3">
                This link had already been used — nothing has changed.
              </p>
            ) : null}
            <Link
              to={isRecovery ? "/settings" : "/sign-in"}
              className="inline-flex items-center justify-center w-full mt-7 h-11 px-6 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700"
            >
              {isRecovery ? "Back to settings" : "Sign in"}
            </Link>
          </>
        ) : null}

        {state === "failed" ? (
          <>
            <XCircle className="size-12 text-red-500 mx-auto" aria-hidden />
            <h1 className="text-2xl font-bold text-strong mt-5">
              {code === "expired_verification"
                ? "That link has expired"
                : code === "superseded_verification"
                  ? "A newer link was sent"
                  : "That link did not work"}
            </h1>
            <p className="text-sm text-body mt-3 leading-relaxed">{message}</p>

            {/*
              The remedy depends on what the link was for, and an earlier
              version always pointed at the registration resend — the wrong
              door for somebody confirming a recovery address, who simply
              needs to ask again from their settings.
            */}
            <div className="mt-7 space-y-2.5">
              {code === "superseded_verification" ? (
                <p className="text-sm text-muted">
                  Check your inbox for the most recent message and open that link
                  instead.
                </p>
              ) : (
                <>
                  <Link
                    to="/settings"
                    className="inline-flex items-center justify-center w-full h-11 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700"
                  >
                    Request it again from settings
                  </Link>
                  <p className="text-xs text-muted">
                    Adding a recovery address? Sign in first, then ask for a new
                    link from Settings.
                  </p>
                  <Link
                    to="/resend-verification"
                    className="inline-block text-sm text-brand-600 hover:underline"
                  >
                    Never received your sign-in details instead?
                  </Link>
                </>
              )}
            </div>
          </>
        ) : null}
      </div>
      <AuthFooter />
    </AuthLayout>
  );
}
