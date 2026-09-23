import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, BadgeCheck, ChevronRight, FileCheck2, GitBranch, GraduationCap,
  Menu, Search, ShieldCheck, Sparkles, Users, X,
} from "lucide-react";
import { useAuth } from "@/features/auth/useAuth";
import { cn } from "@/lib/cn";

/**
 * The public landing page.
 *
 * Written for somebody who has never heard of FORGE — most likely a student
 * who followed a link from a classmate, or an employer who was handed a
 * certificate. Both need the same first sentence: what this is, and why
 * anything on it is worth believing.
 *
 * The page never claims FORGE awards credit. That line appears above the fold
 * rather than in a footer, because it is the first thing a student needs to
 * know before deciding whether this affects their degree.
 */

const NAV = [
  { label: "How it works", href: "#how" },
  { label: "Why believe it", href: "#evidence" },
  { label: "For employers", href: "#employers" },
  { label: "Showcase", to: "/showcase" },
];

const PILLARS = [
  {
    icon: Search,
    title: "Find real work",
    body: "Projects across every school, with roles you can actually apply for — including ones open to people with no track record yet.",
    tone: "brand" as const,
  },
  {
    icon: Users,
    title: "Build in a team",
    body: "A Nursing student and a Cyber Security student on the same problem. Cross-school teams are the normal case here, not the exception.",
    tone: "purple" as const,
  },
  {
    icon: GraduationCap,
    title: "Guided, not graded",
    body: "A volunteer academic mentor reviews the proposal, follows the build, and countersigns what you did. No marks, no compulsion.",
    tone: "green" as const,
  },
  {
    icon: BadgeCheck,
    title: "Keep the record",
    body: "Every contribution confirmed by two other people, in a ledger you can export, sign and show — long after you graduate.",
    tone: "ember" as const,
  },
];

const STAGES = [
  ["Propose", "You write down the problem and what will exist at the end."],
  ["Review", "A mentor checks it is realistic, lawful, ethical and not a duplicate."],
  ["Team", "You advertise roles. People apply. You pick."],
  ["Build", "Work in milestones. Log contributions as you go, not at the end."],
  ["Test", "Peers and your mentor review it against the objectives you set."],
  ["Document", "Write it up — including what went wrong."],
  ["Recognition", "Two people confirm your work. It enters the record permanently."],
];

export function Landing() {
  const { status } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const signedIn = status === "authenticated";

  return (
    <div className="min-h-dvh bg-[#07101f] text-white overflow-x-hidden">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-3 focus:left-3 focus:rounded-lg focus:bg-brand-600 focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      {/* ---------------------------------------------------------------- nav */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-[#07101f]/80 border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <img src="/forge-logo.png" srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x" alt="" className="size-8" />
            <span className="text-lg font-bold tracking-tight">FORGE</span>
          </Link>

          <nav className="hidden lg:flex items-center gap-1" aria-label="Main">
            {NAV.map((item) =>
              item.to ? (
                <Link
                  key={item.label}
                  to={item.to}
                  className="px-3 py-2 text-sm text-navy-200 hover:text-white transition-colors"
                >
                  {item.label}
                </Link>
              ) : (
                <a
                  key={item.label}
                  href={item.href}
                  className="px-3 py-2 text-sm text-navy-200 hover:text-white transition-colors"
                >
                  {item.label}
                </a>
              ),
            )}
          </nav>

          <div className="hidden sm:flex items-center gap-2 shrink-0">
            <Link
              to="/verify-certificate"
              className="px-3.5 py-2 text-sm text-navy-200 hover:text-white transition-colors"
            >
              Verify a certificate
            </Link>
            {signedIn ? (
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 h-10 px-5 rounded-lg bg-brand-600 text-sm font-semibold hover:bg-brand-500 transition-colors"
              >
                Go to dashboard <ArrowRight className="size-4" aria-hidden />
              </Link>
            ) : (
              <>
                <Link
                  to="/sign-in"
                  className="px-3.5 py-2 text-sm text-navy-200 hover:text-white transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center gap-1.5 h-10 px-5 rounded-lg bg-brand-600 text-sm font-semibold hover:bg-brand-500 transition-colors shadow-lg shadow-brand-600/25"
                >
                  Join FORGE <ArrowRight className="size-4" aria-hidden />
                </Link>
              </>
            )}
          </div>

          <button
            onClick={() => setMenuOpen((open) => !open)}
            className="lg:hidden p-2 -mr-2 text-navy-200"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>

        {menuOpen ? (
          <div className="lg:hidden border-t border-white/5 px-4 py-4 space-y-1 bg-[#07101f]">
            {NAV.map((item) =>
              item.to ? (
                <Link
                  key={item.label}
                  to={item.to}
                  onClick={() => setMenuOpen(false)}
                  className="block px-3 py-2.5 rounded-lg text-sm text-navy-200 hover:bg-white/5"
                >
                  {item.label}
                </Link>
              ) : (
                <a
                  key={item.label}
                  href={item.href}
                  onClick={() => setMenuOpen(false)}
                  className="block px-3 py-2.5 rounded-lg text-sm text-navy-200 hover:bg-white/5"
                >
                  {item.label}
                </a>
              ),
            )}
            <Link
              to="/verify-certificate"
              onClick={() => setMenuOpen(false)}
              className="block px-3 py-2.5 rounded-lg text-sm text-navy-200 hover:bg-white/5"
            >
              Verify a certificate
            </Link>
            <div className="flex gap-2 pt-3">
              <Link
                to={signedIn ? "/dashboard" : "/sign-in"}
                className="flex-1 text-center h-11 leading-[2.75rem] rounded-lg border border-white/15 text-sm font-medium"
              >
                {signedIn ? "Dashboard" : "Sign in"}
              </Link>
              {!signedIn ? (
                <Link
                  to="/register"
                  className="flex-1 text-center h-11 leading-[2.75rem] rounded-lg bg-brand-600 text-sm font-semibold"
                >
                  Join FORGE
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
      </header>

      <main id="main">
        {/* -------------------------------------------------------------- hero */}
        <section className="relative">
          {/* The photograph is atmosphere, never information. It sits under a
              heavy gradient and the section reads correctly without it, which
              matters on a connection where it will not arrive quickly. */}
          <div className="absolute inset-0 overflow-hidden" aria-hidden>
            <img
              src="/img/collaboration.webp"
              alt=""
              className="size-full object-cover opacity-[0.22]"
              loading="eager"
              fetchPriority="high"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-[#07101f]/70 via-[#07101f]/90 to-[#07101f]" />
            <div className="absolute -top-32 left-1/4 size-[32rem] rounded-full bg-brand-600/25 blur-[120px]" />
            <div className="absolute top-40 -right-20 size-[28rem] rounded-full bg-ember-500/15 blur-[120px]" />
          </div>

          <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-16 pb-20 sm:pt-24 sm:pb-28 text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-navy-100 backdrop-blur">
              <Sparkles className="size-3.5 text-ember-400" aria-hidden />
              Powered by The Open University of Kenya
            </span>

            <h1 className="mt-7 text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.08]">
              <span className="block text-ember-400 text-2xl sm:text-3xl font-bold tracking-normal mb-3">
                Don't just learn.
              </span>
              Turn what you know into
              <br className="hidden sm:block" />{" "}
              <span className="bg-gradient-to-r from-brand-400 via-brand-300 to-ember-400 bg-clip-text text-transparent">
                something you can show.
              </span>
            </h1>

            <p className="mt-6 max-w-2xl mx-auto text-base sm:text-lg text-navy-200 leading-relaxed">
              A student project and collaboration ecosystem. Propose real work,
              build it with people from any school, and walk away with a record two
              other people have confirmed.
            </p>

            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link
                to={signedIn ? "/dashboard" : "/register"}
                className="inline-flex items-center gap-2 h-12 px-7 rounded-xl bg-brand-600 font-semibold hover:bg-brand-500 transition-all shadow-xl shadow-brand-600/30 hover:shadow-brand-500/40 hover:-translate-y-0.5"
              >
                {signedIn ? `Back to your dashboard` : "Join with your University email"}
                <ArrowRight className="size-4.5" aria-hidden />
              </Link>
              <a
                href="#how"
                className="inline-flex items-center gap-2 h-12 px-6 rounded-xl border border-white/15 bg-white/5 font-medium backdrop-blur hover:bg-white/10 transition-colors"
              >
                See how it works
              </a>
            </div>

            <p className="mt-5 text-xs text-navy-400">
              Voluntary. No academic credit. Not part of your assessment.
            </p>

            <ProductMockup />
          </div>
        </section>

        {/* ------------------------------------------------------------ pillars */}
        <section className="relative max-w-6xl mx-auto px-4 sm:px-6 -mt-10 sm:-mt-16 pb-20">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PILLARS.map((pillar, index) => (
              <PillarCard key={pillar.title} {...pillar} featured={index === 1} />
            ))}
          </div>
        </section>

        {/* --------------------------------------------------------------- how */}
        <section id="how" className="relative py-20 border-t border-white/5">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <SectionHeading
              eyebrow="How it works"
              title="Seven stages, and you cannot skip one"
              body="The lifecycle is what separates this from a group chat. Each stage produces something, and nothing reaches your record until the last one."
            />

            <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {STAGES.map(([title, body], index) => (
                <li
                  key={title}
                  className={cn(
                    "relative rounded-2xl border border-white/8 bg-white/[0.03] p-5 backdrop-blur",
                    "hover:border-brand-500/40 hover:bg-white/[0.06] transition-colors",
                    index === STAGES.length - 1 &&
                      "sm:col-span-2 lg:col-span-1 border-ember-500/30 bg-ember-500/[0.07]",
                  )}
                >
                  <span
                    className={cn(
                      "grid place-items-center size-9 rounded-xl text-sm font-bold",
                      index === STAGES.length - 1
                        ? "bg-ember-500 text-navy-950"
                        : "bg-brand-600/20 text-brand-300 border border-brand-500/30",
                    )}
                  >
                    {index + 1}
                  </span>
                  <h3 className="mt-3.5 font-semibold">{title}</h3>
                  <p className="mt-1.5 text-sm text-navy-300 leading-relaxed">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---------------------------------------------------------- evidence */}
        <section id="evidence" className="relative py-20 border-t border-white/5">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 grid gap-12 lg:grid-cols-2 items-center">
            <div>
              <SectionHeading
                align="left"
                eyebrow="Why believe any of it"
                title="Nobody can confirm their own work"
                body="Anyone can write a good CV. The difference here is that every claim on a FORGE record was confirmed independently by two other named people, and the record is built so that altering it afterwards is visible."
              />

              <ul className="mt-8 space-y-5">
                <EvidencePoint
                  icon={Users}
                  title="Two signatures, neither of them yours"
                  body="Your project lead and the assigned mentor each confirm a contribution before it counts. You cannot sign your own — and if you are the lead, a community lead signs in your place."
                />
                <EvidencePoint
                  icon={ShieldCheck}
                  title="Append-only and hash-chained"
                  body="Each confirmed contribution links to the one before it. Altering a historical entry invalidates every entry recorded after it, so tampering cannot be quiet."
                />
                <EvidencePoint
                  icon={FileCheck2}
                  title="Signed, and checkable by anyone"
                  body="Export your record signed with a key the platform publishes. An employer verifies it without an account, and without having to trust whoever handed it to them."
                />
              </ul>

              <Link
                to="/ledger"
                className="inline-flex items-center gap-2 mt-8 text-sm font-semibold text-brand-300 hover:text-brand-200"
              >
                Read the live ledger yourself
                <ChevronRight className="size-4" aria-hidden />
              </Link>
            </div>

            <LedgerIllustration />
          </div>
        </section>

        {/* --------------------------------------------------------- employers */}
        <section id="employers" className="relative py-20 border-t border-white/5">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            <div className="relative overflow-hidden rounded-3xl border border-white/8">
              <img
                src="/img/mentorship.webp"
                alt=""
                aria-hidden
                className="absolute inset-0 size-full object-cover opacity-20"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-[#07101f] via-[#07101f]/92 to-[#07101f]/70" />

              <div className="relative p-8 sm:p-12 grid gap-8 lg:grid-cols-[1.2fr_1fr] items-center">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-ember-400">
                    For employers and internship providers
                  </span>
                  <h2 className="mt-3 text-2xl sm:text-3xl font-bold leading-tight">
                    Handed a FORGE certificate? Check it in ten seconds.
                  </h2>
                  <p className="mt-4 text-navy-200 leading-relaxed max-w-xl">
                    Type the code printed on it. You will see who it was issued to,
                    what work it records, who confirmed that work, and whether it has
                    been withdrawn. No account, no sign-up, and you do not have to take
                    the candidate's word for it.
                  </p>
                  <p className="mt-4 text-sm text-navy-400">
                    A valid result means FORGE issued it and it has not been altered.
                    It is not a University award and carries no academic credit — we
                    say so on the certificate itself.
                  </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur">
                  <label className="block text-xs font-medium uppercase tracking-wide text-navy-300">
                    Verification code
                  </label>
                  <div className="mt-2 rounded-lg border border-white/12 bg-[#07101f]/70 px-4 py-3 font-mono tracking-[0.2em] text-lg text-white/85">
                    H7KM-P3QR-9TWX
                  </div>
                  <Link
                    to="/verify-certificate"
                    className="mt-4 w-full inline-flex items-center justify-center gap-2 h-11 rounded-lg bg-ember-500 text-navy-950 font-semibold hover:bg-ember-400 transition-colors"
                  >
                    Check a certificate
                    <ArrowRight className="size-4" aria-hidden />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* -------------------------------------------------------------- join */}
        <section className="relative py-20 border-t border-white/5">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 text-center">
            <div
              aria-hidden
              className="absolute left-1/2 -translate-x-1/2 top-10 size-[24rem] rounded-full bg-brand-600/20 blur-[100px]"
            />
            <div className="relative">
              <GitBranch className="size-9 text-ember-400 mx-auto" aria-hidden />
              <h2 className="mt-5 text-3xl sm:text-4xl font-extrabold tracking-tight">
                Every school. No prerequisite.
              </h2>
              <p className="mt-4 text-navy-200 leading-relaxed">
                Nursing, Education, Agri-Technology, Business, Cyber Security — FORGE
                is not a computing club. If you are a student of the Open University of
                Kenya, you can join today and start by helping with something small.
              </p>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link
                  to={signedIn ? "/discover" : "/register"}
                  className="inline-flex items-center gap-2 h-12 px-7 rounded-xl bg-brand-600 font-semibold hover:bg-brand-500 transition-all shadow-xl shadow-brand-600/30 hover:-translate-y-0.5"
                >
                  {signedIn ? "Find a project" : "Join with your University email"}
                  <ArrowRight className="size-4.5" aria-hidden />
                </Link>
                <Link
                  to="/showcase"
                  className="inline-flex items-center gap-2 h-12 px-6 rounded-xl border border-white/15 bg-white/5 font-medium hover:bg-white/10 transition-colors"
                >
                  See what students built
                </Link>
              </div>

              {!signedIn ? (
                <p className="mt-5 text-xs text-navy-400 max-w-md mx-auto leading-relaxed">
                  You do not pick a password. We email your sign-in details to your
                  University address, so only somebody who can read that mailbox can
                  open the account.
                </p>
              ) : null}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/5 py-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <img src="/forge-logo.png" srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x" alt="" className="size-7" />
            <div>
              <p className="font-bold text-sm">FORGE</p>
              <p className="text-xs text-navy-400">The Open University of Kenya</p>
            </div>
          </div>
          <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-navy-300">
            <Link to="/showcase" className="hover:text-white">Showcase</Link>
            <Link to="/ledger" className="hover:text-white">The ledger</Link>
            <Link to="/verify-certificate" className="hover:text-white">Verify a certificate</Link>
            <Link to="/sign-in" className="hover:text-white">Sign in</Link>
          </nav>
          <p className="text-xs text-navy-500 w-full lg:w-auto">
            A voluntary student initiative. No academic credit.
          </p>
        </div>
      </footer>
    </div>
  );
}

/* ----------------------------------------------------------------- pieces */

function SectionHeading({
  eyebrow,
  title,
  body,
  align = "center",
}: {
  eyebrow: string;
  title: string;
  body: string;
  align?: "center" | "left";
}) {
  return (
    <div className={cn("max-w-2xl", align === "center" && "mx-auto text-center")}>
      <span className="text-xs font-semibold uppercase tracking-wider text-brand-400">
        {eyebrow}
      </span>
      <h2 className="mt-3 text-2xl sm:text-3xl font-bold tracking-tight leading-tight">
        {title}
      </h2>
      <p className="mt-4 text-navy-300 leading-relaxed">{body}</p>
    </div>
  );
}

function PillarCard({
  icon: Icon,
  title,
  body,
  tone,
  featured,
}: {
  icon: typeof Users;
  title: string;
  body: string;
  tone: "brand" | "purple" | "green" | "ember";
  featured?: boolean;
}) {
  const badge = {
    brand: "bg-brand-600/20 text-brand-300 border-brand-500/30",
    purple: "bg-violet-600/20 text-violet-300 border-violet-500/30",
    green: "bg-emerald-600/20 text-emerald-300 border-emerald-500/30",
    ember: "bg-ember-500/20 text-ember-300 border-ember-500/30",
  }[tone];

  return (
    <div
      className={cn(
        "group rounded-2xl border p-6 backdrop-blur-xl transition-all hover:-translate-y-1",
        featured
          ? "border-brand-500/40 bg-gradient-to-b from-brand-600/20 to-brand-900/10 shadow-xl shadow-brand-950/40"
          : "border-white/8 bg-white/[0.04] hover:border-white/15 hover:bg-white/[0.07]",
      )}
    >
      <span className={cn("inline-grid place-items-center size-11 rounded-xl border", badge)}>
        <Icon className="size-5" aria-hidden />
      </span>
      <h3 className="mt-4 font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-navy-300 leading-relaxed">{body}</p>
      <span
        aria-hidden
        className="mt-4 flex gap-1 opacity-60 group-hover:opacity-100 transition-opacity"
      >
        <span className="size-1.5 rounded-full bg-brand-400" />
        <span className="size-1.5 rounded-full bg-brand-400/60" />
        <span className="size-1.5 rounded-full bg-brand-400/30" />
      </span>
    </div>
  );
}

function EvidencePoint({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Users;
  title: string;
  body: string;
}) {
  return (
    <li className="flex gap-4">
      <span className="grid place-items-center size-10 rounded-xl bg-white/5 border border-white/10 shrink-0">
        <Icon className="size-5 text-brand-300" aria-hidden />
      </span>
      <div className="min-w-0">
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-navy-300 leading-relaxed">{body}</p>
      </div>
    </li>
  );
}

/**
 * A stylised view of the real dashboard.
 *
 * Built in markup rather than screenshotted. A screenshot goes stale the day
 * the interface changes and nobody notices for a year; this cannot show
 * something the product does not do, weighs nothing, and stays sharp at any
 * density.
 */
function ProductMockup() {
  return (
    <div className="mt-14 sm:mt-16 relative max-w-4xl mx-auto" aria-hidden>
      <div
        className="absolute -inset-x-8 -top-6 bottom-10 rounded-[2rem] bg-gradient-to-b from-brand-500/20 to-transparent blur-2xl"
      />
      <div className="relative rounded-2xl border border-white/12 bg-[#0b1728] shadow-2xl shadow-black/60 overflow-hidden">
        {/* window chrome */}
        <div className="flex items-center gap-2 px-4 h-10 border-b border-white/6 bg-white/[0.03]">
          <span className="size-2.5 rounded-full bg-red-400/70" />
          <span className="size-2.5 rounded-full bg-ember-400/70" />
          <span className="size-2.5 rounded-full bg-emerald-400/70" />
          <span className="ml-3 text-[11px] text-navy-400 font-mono">
            forge.ouk.ac.ke
          </span>
        </div>

        <div className="grid grid-cols-[132px_1fr] sm:grid-cols-[168px_1fr] text-left">
          <div className="border-r border-white/6 bg-[#081221] p-3 space-y-1.5">
            {["Dashboard", "Discover", "My projects", "Contributions", "The ledger", "Portfolio"].map(
              (label, index) => (
                <div
                  key={label}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px]",
                    index === 0 ? "bg-brand-600/25 text-white" : "text-navy-400",
                  )}
                >
                  <span className="size-1.5 rounded-sm bg-current opacity-60" />
                  <span className="truncate">{label}</span>
                </div>
              ),
            )}
          </div>

          <div className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="h-2.5 w-28 rounded bg-white/25" />
                <div className="mt-1.5 h-2 w-20 rounded bg-white/10" />
              </div>
              <div className="h-7 w-24 rounded-md bg-brand-600/80" />
            </div>

            <div className="grid grid-cols-4 gap-2">
              {[
                ["3", "Projects", "bg-brand-500/25"],
                ["125", "Points", "bg-emerald-500/25"],
                ["4", "Tasks", "bg-violet-500/25"],
                ["Builder", "Level", "bg-ember-500/30"],
              ].map(([value, label, tint]) => (
                <div
                  key={label}
                  className="rounded-lg border border-white/8 bg-white/[0.03] p-2.5"
                >
                  <div className={cn("size-5 rounded-md mb-1.5", tint)} />
                  <div className="text-[13px] font-bold text-white/90 leading-none">
                    {value}
                  </div>
                  <div className="text-[9px] text-navy-400 mt-1">{label}</div>
                </div>
              ))}
            </div>

            <div className="rounded-lg border border-ember-500/35 bg-ember-500/10 p-2.5 flex items-center gap-2.5">
              <span className="size-6 rounded-md bg-ember-500/80 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="h-2 w-40 rounded bg-ember-200/50" />
                <div className="mt-1.5 h-1.5 w-52 rounded bg-white/10" />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[68, 34, 92].map((percent, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-white/8 bg-white/[0.03] overflow-hidden"
                >
                  <div
                    className={cn(
                      "h-9",
                      index === 0 && "bg-gradient-to-br from-brand-700 to-brand-500",
                      index === 1 && "bg-gradient-to-br from-emerald-800 to-emerald-500",
                      index === 2 && "bg-gradient-to-br from-violet-800 to-violet-500",
                    )}
                  />
                  <div className="p-2">
                    <div className="h-1.5 w-full rounded bg-white/18" />
                    <div className="mt-1 h-1.5 w-2/3 rounded bg-white/10" />
                    <div className="mt-2 h-1 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-brand-400"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** The ledger, shown as a chain of linked entries. */
function LedgerIllustration() {
  const entries = [
    { seq: 3, who: "Grace Njeri", what: "Built the ingest job and its tests", pts: 12 },
    { seq: 2, who: "Kevin Otieno", what: "Interviewed patients and wrote it up", pts: 11 },
    { seq: 1, who: "Mary Wanjiru", what: "Documented the deployment", pts: 9 },
  ];

  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute -inset-6 rounded-3xl bg-gradient-to-br from-emerald-500/10 via-brand-600/10 to-transparent blur-2xl"
      />
      <div className="relative rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur">
        <div className="flex items-center gap-2 pb-4 border-b border-white/8">
          <ShieldCheck className="size-4.5 text-emerald-400" aria-hidden />
          <span className="text-sm font-semibold">Chain intact</span>
          <span className="ml-auto text-[11px] font-mono text-navy-400">
            head #3 · fea3fc1f…
          </span>
        </div>

        <ol className="mt-4 space-y-3">
          {entries.map((entry, index) => (
            <li key={entry.seq} className="relative">
              {index < entries.length - 1 ? (
                <span
                  aria-hidden
                  className="absolute left-[15px] top-9 h-[calc(100%+0.25rem)] w-px bg-gradient-to-b from-emerald-500/50 to-transparent"
                />
              ) : null}
              <div className="flex gap-3">
                <span className="grid place-items-center size-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-[11px] font-bold text-emerald-300 shrink-0">
                  {entry.seq}
                </span>
                <div className="min-w-0 flex-1 rounded-xl border border-white/8 bg-[#07101f]/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium truncate">{entry.who}</span>
                    <span className="text-[11px] text-ember-300 font-semibold shrink-0">
                      {entry.pts} pts
                    </span>
                  </div>
                  <p className="text-xs text-navy-400 mt-0.5 truncate">{entry.what}</p>
                  <div className="flex items-center gap-1.5 mt-2">
                    <BadgeCheck className="size-3 text-emerald-400" aria-hidden />
                    <span className="text-[10px] text-navy-400">
                      lead + mentor confirmed
                    </span>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
