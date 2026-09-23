import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, BadgeCheck } from "lucide-react";
import { useShowcase } from "@/api/queries";
import { cn } from "@/lib/cn";

/**
 * The frame every signed-out page sits in.
 *
 * A single floating card over a dark backdrop, split in two: a showcase panel
 * on the left and whatever form the page needs on the right. Below `lg` the
 * showcase panel is dropped entirely rather than stacked — on a phone it would
 * push the form below the fold, and somebody who came here to sign in did not
 * come to read.
 */

type Slide = {
  image: string;
  eyebrow: string;
  title: string;
  body: string;
  attribution?: { name: string; role: string };
};

/**
 * The fallback rotation.
 *
 * These illustrate the *kinds* of work FORGE is for. They carry no student's
 * name, because inventing one to decorate a sign-in page would be a strange
 * thing for a platform whose whole argument is that its records are real.
 * Once the showcase has published entries, real projects replace these.
 */
const FALLBACK: Slide[] = [
  {
    image: "/img/slide-classroom.webp",
    eyebrow: "Education and Learning",
    title: "Materials a screen reader can actually read",
    body: "First-year mathematics rebuilt as accessible HTML, tested with the students who need it.",
  },
  {
    image: "/img/slide-health.webp",
    eyebrow: "Health",
    title: "Know the queue before you travel",
    body: "A clinic queue tracker, built by a nursing student and two developers who had never met.",
  },
  {
    image: "/img/slide-farm.webp",
    eyebrow: "Agriculture and Environment",
    title: "A season of data, not a season of guessing",
    body: "Low-cost soil moisture logging on two partner farms, with a report each farmer can use.",
  },
];

export function AuthLayout({
  children,
  wide,
}: {
  children: ReactNode;
  /** For the longer forms — registration, accepting an invitation. */
  wide?: boolean;
}) {
  return (
    <div className="min-h-dvh bg-[#070d18] relative flex items-center justify-center p-4 sm:p-6 lg:p-10">
      {/* Backdrop. Purely atmospheric: the page reads correctly without it,
          which matters on a connection where it will not arrive quickly. */}
      <div className="absolute inset-0 overflow-hidden" aria-hidden>
        <img
          src="/img/auth-backdrop.webp"
          alt=""
          className="size-full object-cover opacity-30"
          loading="eager"
          fetchPriority="high"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-[#070d18]/85 via-[#070d18]/70 to-[#0b1a33]/90" />
        <div className="absolute -top-40 -left-32 size-[34rem] rounded-full bg-brand-600/20 blur-[130px]" />
        <div className="absolute -bottom-40 -right-24 size-[30rem] rounded-full bg-ember-500/12 blur-[130px]" />
      </div>

      <div
        className={cn(
          "relative w-full grid lg:grid-cols-2 rounded-[1.75rem] overflow-hidden",
          "bg-card shadow-2xl shadow-black/60 ring-1 ring-white/10",
          wide ? "max-w-6xl" : "max-w-5xl",
        )}
      >
        <ShowcasePanel />
        <div className="flex items-center justify-center p-6 sm:p-10 lg:p-12">
          <div className={cn("w-full", wide ? "max-w-md" : "max-w-sm")}>{children}</div>
        </div>
      </div>
    </div>
  );
}

function ShowcasePanel() {
  // Published showcase entries if there are any, curated slides otherwise.
  // Unauthenticated, so this is the same list a stranger sees on /showcase.
  const { data } = useShowcase({ page_size: 4 });

  const slides = useMemo<Slide[]>(() => {
    const published = (data?.results ?? []).filter((entry) => entry.is_published);
    if (published.length === 0) return FALLBACK;

    return published.slice(0, 4).map((entry, index) => ({
      image: entry.images?.[0]?.image ?? FALLBACK[index % FALLBACK.length].image,
      eyebrow: entry.discipline_areas?.[0] ?? "FORGE",
      title: entry.headline ?? entry.project_title ?? "",
      body: (entry.what_we_built ?? "").slice(0, 150),
      attribution: entry.lead
        ? { name: entry.lead.display_name ?? "", role: "Project lead" }
        : undefined,
    }));
  }, [data]);

  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || slides.length < 2) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % slides.length), 7000);
    return () => clearInterval(timer);
  }, [paused, slides.length]);

  const slide = slides[index % slides.length];

  return (
    <aside
      className="relative hidden lg:block min-h-[34rem] bg-navy-950 overflow-hidden"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {slides.map((item, itemIndex) => (
        <img
          key={item.image + itemIndex}
          src={item.image}
          alt=""
          aria-hidden
          loading={itemIndex === 0 ? "eager" : "lazy"}
          className={cn(
            "absolute inset-0 size-full object-cover transition-opacity duration-1000",
            itemIndex === index ? "opacity-100" : "opacity-0",
          )}
        />
      ))}
      <div className="absolute inset-0 bg-gradient-to-t from-navy-950 via-navy-950/70 to-navy-950/25" />
      <div
        aria-hidden
        className="absolute -top-24 -right-16 size-80 rounded-full bg-brand-600/25 blur-[90px]"
      />

      <div className="relative h-full flex flex-col p-8 xl:p-10 text-white">
        <div className="flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5">
            <img
              src="/forge-logo.png"
              srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x"
              alt=""
              className="size-9"
            />
            <span className="text-lg font-bold tracking-tight">FORGE</span>
          </Link>
          <Link
            to="/showcase"
            className="text-xs font-medium text-navy-200 hover:text-white transition-colors"
          >
            Selected work →
          </Link>
        </div>

        <div className="max-w-sm mt-auto pt-10">
          <span className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider backdrop-blur">
            {slide.eyebrow}
          </span>
          {/*
            aria-live so that the rotation is announced rather than silently
            swapping text under a screen-reader user mid-sentence.
          */}
          <div aria-live="polite">
            <h2 className="mt-4 text-2xl xl:text-[1.75rem] font-bold leading-tight">
              {slide.title}
            </h2>
            <p className="mt-3 text-sm text-navy-200 leading-relaxed">{slide.body}</p>
          </div>
        </div>

        <div className="flex items-end justify-between gap-4 mt-7">
          <div className="min-w-0">
            {slide.attribution ? (
              <div className="flex items-center gap-3">
                <span className="grid place-items-center size-10 rounded-full bg-brand-600 text-sm font-bold ring-2 ring-white/20">
                  {slide.attribution.name
                    .split(/\s+/)
                    .slice(0, 2)
                    .map((word) => word[0])
                    .join("")}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">{slide.attribution.name}</p>
                  <p className="text-xs text-navy-300">{slide.attribution.role}</p>
                </div>
              </div>
            ) : (
              <p className="flex items-center gap-2 text-xs text-navy-300">
                <BadgeCheck className="size-4 text-ember-400 shrink-0" aria-hidden />
                Every contribution confirmed by two other people
              </p>
            )}
          </div>

          {slides.length > 1 ? (
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() =>
                  setIndex((i) => (i - 1 + slides.length) % slides.length)
                }
                aria-label="Previous"
                className="grid place-items-center size-9 rounded-full border border-white/25 text-white/80 hover:bg-white/10 hover:text-white transition-colors"
              >
                <ArrowLeft className="size-4" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => setIndex((i) => (i + 1) % slides.length)}
                aria-label="Next"
                className="grid place-items-center size-9 rounded-full border border-white/25 text-white/80 hover:bg-white/10 hover:text-white transition-colors"
              >
                <ArrowRight className="size-4" aria-hidden />
              </button>
            </div>
          ) : null}
        </div>

        <div className="flex gap-1.5 mt-5">
          {slides.map((_, itemIndex) => (
            <button
              key={itemIndex}
              type="button"
              onClick={() => setIndex(itemIndex)}
              aria-label={`Slide ${itemIndex + 1} of ${slides.length}`}
              aria-current={itemIndex === index}
              className={cn(
                "h-1 rounded-full transition-all",
                itemIndex === index ? "w-8 bg-ember-400" : "w-4 bg-white/25 hover:bg-white/40",
              )}
            />
          ))}
        </div>
      </div>
    </aside>
  );
}

/** The heading block every auth form starts with. */
export function AuthHeading({
  title,
  subtitle,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <div className="mb-7">
      <Link to="/" className="inline-flex items-center gap-2.5 mb-7 lg:hidden">
        <img
          src="/forge-logo.png"
          srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x"
          alt=""
          className="size-9"
        />
        <span className="text-lg font-bold text-strong tracking-tight">FORGE</span>
      </Link>
      <h1 className="text-3xl font-extrabold text-strong tracking-tight">{title}</h1>
      {subtitle ? <p className="text-sm text-muted mt-2">{subtitle}</p> : null}
    </div>
  );
}

/** The links under every auth form. */
export function AuthFooter({ children }: { children?: ReactNode }) {
  return (
    <div className="mt-8 pt-6 border-t border-line">
      {children}
      <nav className="flex flex-wrap gap-x-5 gap-y-1.5 mt-4 text-xs text-muted">
        <Link to="/showcase" className="hover:text-brand-600">Showcase</Link>
        <Link to="/verify-certificate" className="hover:text-brand-600">
          Verify a certificate
        </Link>
        <Link to="/ledger" className="hover:text-brand-600">The ledger</Link>
      </nav>
      <p className="mt-3 text-[11px] text-muted leading-relaxed">
        A voluntary student initiative of The Open University of Kenya. No academic
        credit.
      </p>
    </div>
  );
}
