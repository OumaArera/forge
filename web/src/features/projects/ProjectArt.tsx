import {
  BarChart3, Briefcase, Code2, GraduationCap, HeartPulse, Landmark, Megaphone,
  Palette, ShieldCheck, Sprout, Users,
} from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * The image band at the top of a project card.
 *
 * The mockup shows a photograph per project. FORGE has no photographs and
 * should not start requiring them — an upload is one more thing standing
 * between a student and proposing something, and a stock photo of a laptop
 * tells a reader nothing about a clinic queue tracker.
 *
 * Each project gets a generated mark instead: a mesh gradient and a glyph
 * taken from its discipline, deterministic from the slug so the same project
 * always looks the same. It fills the same role in the layout, costs no
 * bandwidth, carries actual information about what the project is, and never
 * looks like a placeholder somebody forgot to replace.
 */

type Scheme = { from: string; via: string; to: string };

const SCHEMES: Scheme[] = [
  { from: "#0b2a5b", via: "#1f6fe5", to: "#38bdf8" }, // deep blue
  { from: "#064e3b", via: "#0d9488", to: "#5eead4" }, // teal
  { from: "#3b0764", via: "#7c3aed", to: "#c4b5fd" }, // violet
  { from: "#7c2d12", via: "#ea580c", to: "#fbbf24" }, // ember
  { from: "#134e4a", via: "#059669", to: "#a7f3d0" }, // green
  { from: "#1e1b4b", via: "#4f46e5", to: "#a5b4fc" }, // indigo
  { from: "#831843", via: "#db2777", to: "#f9a8d4" }, // rose
  { from: "#0c4a6e", via: "#0284c7", to: "#7dd3fc" }, // sky
];

/** Discipline → (icon, scheme). Keeps a subject visually consistent everywhere. */
const DISCIPLINES: Record<string, { icon: typeof Code2; scheme: number }> = {
  "software-and-systems": { icon: Code2, scheme: 0 },
  "cyber-security": { icon: ShieldCheck, scheme: 5 },
  "data-and-analytics": { icon: BarChart3, scheme: 2 },
  health: { icon: HeartPulse, scheme: 6 },
  "education-and-learning": { icon: GraduationCap, scheme: 3 },
  "business-and-enterprise": { icon: Briefcase, scheme: 7 },
  "agriculture-and-environment": { icon: Sprout, scheme: 4 },
  "communication-and-media": { icon: Megaphone, scheme: 3 },
  "governance-and-public-service": { icon: Landmark, scheme: 1 },
  "community-and-platform": { icon: Users, scheme: 5 },
};

function hash(input: string): number {
  let value = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    value ^= input.charCodeAt(index);
    value = Math.imul(value, 16777619) >>> 0;
  }
  return value;
}

export function ProjectArt({
  slug,
  title,
  areaSlug,
  className,
  compact,
}: {
  slug: string;
  title: string;
  areaSlug?: string;
  className?: string;
  compact?: boolean;
}) {
  const seed = hash(slug || title);
  const discipline = DISCIPLINES[areaSlug ?? ""];
  const scheme = SCHEMES[discipline?.scheme ?? seed % SCHEMES.length];
  const Icon = discipline?.icon ?? Palette;

  // Blob placement varies with the seed, so a grid of cards never reads as a
  // repeating tile, but stays stable for any one project.
  const a = { x: 18 + (seed % 34), y: 22 + ((seed >> 3) % 30) };
  const b = { x: 62 + ((seed >> 5) % 30), y: 58 + ((seed >> 7) % 30) };
  const rotation = (seed >> 11) % 40 - 20;

  return (
    <div
      className={cn("relative overflow-hidden isolate", className)}
      style={{ backgroundColor: scheme.from }}
      aria-hidden
    >
      <svg
        className="absolute inset-0 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <defs>
          <radialGradient id={`a-${seed}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={scheme.via} stopOpacity="0.95" />
            <stop offset="100%" stopColor={scheme.via} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`b-${seed}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={scheme.to} stopOpacity="0.75" />
            <stop offset="100%" stopColor={scheme.to} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx={a.x} cy={a.y} r="46" fill={`url(#a-${seed})`} />
        <circle cx={b.x} cy={b.y} r="38" fill={`url(#b-${seed})`} />
      </svg>

      {/* A faint grid gives the panel some texture at large sizes without
          reading as noise at thumbnail size. */}
      <svg className="absolute inset-0 size-full opacity-[0.13]" aria-hidden>
        <defs>
          <pattern
            id={`grid-${seed}`}
            width="14"
            height="14"
            patternUnits="userSpaceOnUse"
          >
            <path d="M 14 0 L 0 0 0 14" fill="none" stroke="white" strokeWidth="0.6" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#grid-${seed})`} />
      </svg>

      {/* The glyph, oversized and clipped — decorative rather than an icon to
          read, which is why the small centred one carries the meaning. */}
      <Icon
        className={cn(
          "absolute text-white/12",
          compact ? "-right-4 -bottom-5 size-24" : "-right-6 -bottom-8 size-40",
        )}
        style={{ transform: `rotate(${rotation}deg)` }}
        strokeWidth={1.25}
        aria-hidden
      />

      <span className="absolute inset-0 grid place-items-center">
        <Icon
          className={cn("text-white/90 drop-shadow", compact ? "size-7" : "size-10")}
          strokeWidth={1.6}
          aria-hidden
        />
      </span>

      <span className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/25 to-transparent" />
    </div>
  );
}
