import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  Award, BadgeCheck, Download, ExternalLink, Link2, ShieldCheck, Sparkles,
} from "lucide-react";
import { format } from "date-fns";
import { api } from "@/api/client";
import { usePortfolio } from "@/api/queries";
import { useAuth } from "@/features/auth/useAuth";
import {
  Avatar, Button, Card, CardHeader, ErrorState, Loading, Pill, StatTile,
} from "@/components/ui";

/**
 * A member's public record.
 *
 * Served at /p/:slug to anyone, with no account. That is the point of the
 * whole platform: a record only the University can read does nothing for the
 * employability argument it rests on.
 */
export function Portfolio() {
  const { slug: routeSlug } = useParams();
  const { member } = useAuth();
  const slug = routeSlug ?? member?.public_slug ?? "";
  const isOwn = !routeSlug || routeSlug === member?.public_slug;
  const { data, isLoading, isError, refetch } = usePortfolio(slug);
  const [exporting, setExporting] = useState(false);
  const [copied, setCopied] = useState(false);

  if (isLoading) return <Loading label="Loading portfolio" />;
  if (isError || !data)
    return (
      <ErrorState
        message="That portfolio could not be loaded. It may have been made private."
        onRetry={() => void refetch()}
      />
    );

  async function downloadExport() {
    setExporting(true);
    try {
      const { data: signed } = await api.get("/portfolio/export/");
      const blob = new Blob([JSON.stringify(signed, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `forge-portfolio-${slug}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(data!.member.portfolio_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard is blocked in some contexts; the URL is on screen anyway */
    }
  }

  const standing = data.standing ?? {};

  return (
    <div className="space-y-6 max-w-5xl">
      <Card className="overflow-hidden">
        <div className="h-28 sm:h-32 bg-navy-900 relative">
          <div
            aria-hidden
            className="absolute -top-10 right-10 size-48 rounded-full bg-brand-600/30 blur-2xl"
          />
          <div
            aria-hidden
            className="absolute -bottom-16 left-1/3 size-44 rounded-full bg-ember-500/15 blur-2xl"
          />
        </div>

        {/*
          Only the avatar overlaps the band. An earlier version pulled the whole
          row up with a negative margin and aligned it to the avatar's baseline,
          which dragged the member's name into the navy band and clipped it.
          The avatar is positioned on its own; everything else starts below.
        */}
        <div className="px-6 pb-6 relative">
          <div className="flex items-start justify-between gap-4">
            <Avatar
              name={data.member.display_name}
              size={88}
              className="-mt-11 ring-4 ring-[--surface-card] shadow-lg shrink-0"
            />
            <div className="flex flex-wrap gap-2 pt-4">
              <Button
                variant="secondary"
                size="sm"
                onClick={copyLink}
                icon={<Link2 className="size-4" aria-hidden />}
              >
                {copied ? "Copied" : "Copy link"}
              </Button>
              {isOwn ? (
                <Button
                  size="sm"
                  loading={exporting}
                  onClick={downloadExport}
                  icon={<Download className="size-4" aria-hidden />}
                >
                  Signed export
                </Button>
              ) : null}
            </div>
          </div>

          <div className="mt-3">
            <h1 className="text-2xl font-bold text-strong leading-tight">
              {data.member.display_name}
            </h1>
            <p className="text-sm text-muted mt-0.5">
              {data.member.programme ?? data.member.school ?? "Member"}
            </p>
          </div>

          {data.member.headline ? (
            <p className="text-body mt-4">{data.member.headline}</p>
          ) : null}
          {data.member.bio ? (
            <p className="text-sm text-muted mt-2 whitespace-pre-line">{data.member.bio}</p>
          ) : null}

          <p className="text-xs text-muted mt-4">
            Member since {format(new Date(data.member.member_since), "MMMM yyyy")} ·{" "}
            {data.member.status}
          </p>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Confirmed contributions"
          value={standing.confirmed_contributions ?? 0}
          icon={<Sparkles className="size-5" aria-hidden />}
        />
        <StatTile
          label="Projects delivered"
          value={standing.completed_projects ?? 0}
          icon={<BadgeCheck className="size-5" aria-hidden />}
          tone="green"
        />
        <StatTile
          label="Projects led"
          value={standing.projects_led ?? 0}
          icon={<Award className="size-5" aria-hidden />}
          tone="purple"
        />
        <StatTile
          label="Level"
          value={standing.level ?? "Apprentice"}
          icon={<Award className="size-5" aria-hidden />}
          tone="ember"
          hint={`${standing.total_points ?? 0} points`}
        />
      </div>

      {/*
        The verification notice. An employer looking at this needs to know, in
        one sentence, why they should believe any of it.
      */}
      <Card className="p-5 border-emerald-300 bg-emerald-50/50 dark:bg-emerald-950/20">
        <div className="flex items-start gap-3.5">
          <ShieldCheck className="size-5 text-emerald-600 shrink-0 mt-0.5" aria-hidden />
          <div className="min-w-0">
            <p className="font-medium text-strong text-sm">
              Every contribution here was confirmed by two other people
            </p>
            <p className="text-sm text-body mt-1 leading-relaxed">
              {data.ledger.chain_note} A signed export can be checked by anyone against
              a public key, without an account.
            </p>
            {data.ledger.head_hash ? (
              <p className="text-xs font-mono text-muted mt-2 break-all">
                Ledger head: {data.ledger.head_hash.slice(0, 32)}…
              </p>
            ) : null}
          </div>
        </div>
      </Card>

      {data.projects.length > 0 ? (
        <Card>
          <CardHeader title="Projects" subtitle={`${data.projects.length} in total`} />
          <ul className="p-5 pt-3 divide-y divide-line">
            {data.projects.map((project) => (
              <li key={project.slug} className="py-4 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-strong">{project.title}</h3>
                      {project.was_lead ? <Pill tone="ember">Led</Pill> : null}
                      {project.is_open_source ? <Pill tone="green">Open source</Pill> : null}
                    </div>
                    <p className="text-sm text-muted mt-1">{project.summary}</p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-xs text-muted">
                      <span>{project.role ?? "Contributor"}</span>
                      <span>{project.status}</span>
                      <span>{project.days_served} days</span>
                      {project.discipline_areas.map((area) => (
                        <Pill key={area} tone="brand">
                          {area}
                        </Pill>
                      ))}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-lg font-bold text-strong tabular-nums">
                      {project.confirmed_contributions}
                    </div>
                    <div className="text-xs text-muted">confirmed</div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {data.contributions.length > 0 ? (
        <Card>
          <CardHeader
            title="Confirmed contributions"
            subtitle="In the order they were settled into the ledger"
          />
          <ul className="p-5 pt-3 space-y-4">
            {data.contributions.map((contribution) => (
              <li
                key={contribution.sequence}
                className="rounded-lg border border-line p-4"
              >
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <Pill tone="brand">{contribution.dimension.split(" —")[0]}</Pill>
                  <span className="text-xs text-muted">{contribution.project}</span>
                  <span className="text-xs text-muted">
                    {format(new Date(contribution.occurred_on), "d MMM yyyy")}
                  </span>
                  {contribution.ai_assistance !== "none" ? (
                    <Pill tone="purple">AI {contribution.ai_assistance}</Pill>
                  ) : null}
                </div>
                <p className="text-body leading-relaxed">{contribution.description}</p>
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  {contribution.confirmed_by.map((confirmer) => (
                    <Pill
                      key={confirmer.capacity}
                      tone="green"
                      icon={<BadgeCheck className="size-3" aria-hidden />}
                    >
                      {confirmer.name} ({confirmer.capacity})
                    </Pill>
                  ))}
                  {contribution.evidence_url ? (
                    <a
                      href={contribution.evidence_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-xs text-brand-600 hover:underline inline-flex items-center gap-1"
                    >
                      Evidence <ExternalLink className="size-3" aria-hidden />
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <div className="grid gap-6 md:grid-cols-2">
        {data.skills.length > 0 ? (
          <Card>
            <CardHeader
              title="Skills"
              subtitle="Evidence counts come from confirmed work, not self-assessment"
            />
            <ul className="p-5 pt-3 space-y-2">
              {data.skills.map((skill) => (
                <li key={skill.skill} className="flex items-center justify-between gap-3">
                  <span className="text-sm text-strong">{skill.skill}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted">{skill.self_rating}</span>
                    {skill.evidence_count > 0 ? (
                      <Pill tone="green">{skill.evidence_count} confirmed</Pill>
                    ) : (
                      <Pill>no evidence yet</Pill>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        {data.badges.length > 0 || data.certificates.length > 0 ? (
          <Card>
            <CardHeader title="Recognition" />
            <div className="p-5 pt-3 space-y-4">
              {data.badges.map((badge) => (
                <div key={badge.name} className="flex items-start gap-3">
                  <Award className="size-5 text-ember-500 shrink-0 mt-0.5" aria-hidden />
                  <div>
                    <p className="text-sm font-medium text-strong">{badge.name}</p>
                    <p className="text-xs text-muted">{badge.criteria}</p>
                  </div>
                </div>
              ))}
              {data.certificates.map((certificate) => (
                <div key={certificate.code} className="flex items-start gap-3">
                  <BadgeCheck className="size-5 text-emerald-500 shrink-0 mt-0.5" aria-hidden />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-strong">{certificate.kind}</p>
                    <a
                      href={certificate.verify_at}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-xs font-mono text-brand-600 hover:underline break-all"
                    >
                      {certificate.code}
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ) : null}
      </div>

      <p className="text-xs text-muted leading-relaxed border-t border-line pt-5">
        {data.platform.note}
      </p>
    </div>
  );
}
