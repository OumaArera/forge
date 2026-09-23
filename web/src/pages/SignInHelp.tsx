import { Link } from "react-router-dom";
import { KeyRound, Mail, ShieldAlert, Timer, UserCheck } from "lucide-react";
import { AuthFooter, AuthHeading, AuthLayout } from "@/components/layout/AuthLayout";

/**
 * What to do when you cannot sign in.
 *
 * This page exists because FORGE deliberately has no "forgot password" link,
 * and a dead end with no explanation is how a platform loses somebody for
 * good. Each case below has a different cause and a different remedy, so they
 * are separated rather than collapsed into one apologetic paragraph.
 */

const CASES = [
  {
    icon: Mail,
    title: "Your sign-in details never arrived",
    body: (
      <>
        We email them to your University address when you register. Check the spam
        folder first — a new sender almost always lands there once. If it is
        genuinely missing,{" "}
        <Link to="/resend-verification" className="text-brand-600 hover:underline">
          ask us to send them again
        </Link>
        .
      </>
    ),
  },
  {
    icon: Timer,
    title: "Too many failed attempts",
    body: (
      <>
        The account locks for a few minutes after five wrong passwords, and longer if
        it keeps happening. It unlocks on its own — wait and try again. If somebody
        else is causing it, we will have emailed you about it.
      </>
    ),
  },
  {
    icon: KeyRound,
    title: "You have forgotten your password",
    body: (
      <>
        There is no self-service reset, on purpose: a reset link is a second
        credential travelling by email, and your account can already be recovered
        through that same mailbox. Ask the faculty advisor to reissue your
        credentials and a fresh password is emailed to you.
      </>
    ),
  },
  {
    icon: UserCheck,
    title: "You have graduated",
    body: (
      <>
        Your University address stops working, but your portfolio does not. Sign in
        with the personal recovery address on your account. If you never added one,
        the faculty advisor can help — this is the one case where being an alumnus
        makes it harder, which is exactly why we ask for that address early.
      </>
    ),
  },
  {
    icon: ShieldAlert,
    title: "Your account is suspended",
    body: (
      <>
        A moderator will have told you what happened and why — every suspension on
        FORGE carries a written reason. Reply to that message to appeal it.
      </>
    ),
  },
];

export function SignInHelp() {
  return (
    <AuthLayout wide>
      <AuthHeading
        title="Can't get in?"
        subtitle="Five things it usually is, and what to do about each."
      />

      <ul className="space-y-5">
        {CASES.map((item) => (
          <li key={item.title} className="flex gap-3.5">
            <span className="grid place-items-center size-9 rounded-xl bg-sunken border border-line shrink-0">
              <item.icon className="size-4.5 text-brand-600" aria-hidden />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-strong">{item.title}</h2>
              <p className="text-sm text-muted mt-1 leading-relaxed">{item.body}</p>
            </div>
          </li>
        ))}
      </ul>

      <AuthFooter>
        <Link
          to="/sign-in"
          className="inline-flex items-center justify-center w-full h-11 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700"
        >
          Back to sign in
        </Link>
      </AuthFooter>
    </AuthLayout>
  );
}
