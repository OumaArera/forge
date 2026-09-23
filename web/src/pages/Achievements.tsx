import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Award, BadgeCheck, ChevronDown, Download, History, Lock, Trophy,
} from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { api, toForgeError } from "@/api/client";
import { useBadges, useCertificates, useLevels, useStanding } from "@/api/queries";
import {
  Button, Card, CardHeader, EmptyState, FormError, Loading, PageHeader, Pill,
  StatTile,
} from "@/components/ui";
import { cn } from "@/lib/cn";

export function Achievements() {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const certificatesQuery = useCertificates();
  const standing = useStanding();

  /**
   * Fetch and save the PDF.
   *
   * Deliberately not a plain link: the endpoint needs the bearer token, and
   * each copy is individually stamped so it must not be cached or shared.
   */
  async function download(code: string) {
    setDownloading(code);
    setError(null);
    try {
      const { data } = await api.get<Blob>(
        `/recognition/certificates/${code}/pdf/`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `forge-certificate-${code}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
      await certificatesQuery.refetch();
    } catch (caught) {
      setError(toForgeError(caught).message);
    } finally {
      setDownloading(null);
    }
  }

  const levels = useLevels();
  const badges = useBadges();
  const certificates = certificatesQuery;

  if (standing.isLoading || levels.isLoading) return <Loading />;

  const currentRank = standing.data?.level?.rank ?? 0;
  const next = standing.data?.next_level as
    | { name?: string; points_needed?: number; contributions_needed?: number; projects_needed?: number; requires_teaching?: boolean }
    | null
    | undefined;

  return (
    <div className="space-y-6 max-w-4xl">
      <PageHeader
        title="Achievements"
        description="Earned from confirmed work. Nothing here can be awarded by hand."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile
          label="Contribution points"
          value={standing.data?.total_points ?? 0}
          icon={<Trophy className="size-5" aria-hidden />}
          tone="ember"
        />
        <StatTile
          label="Confirmed contributions"
          value={standing.data?.confirmed_contributions ?? 0}
          icon={<BadgeCheck className="size-5" aria-hidden />}
          tone="green"
        />
        <StatTile
          label="Projects delivered"
          value={standing.data?.completed_projects ?? 0}
          icon={<Award className="size-5" aria-hidden />}
        />
      </div>

      {next ? (
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-strong">
            Next up: {next.name}
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-body">
            {next.points_needed ? (
              <li>{next.points_needed} more contribution points</li>
            ) : null}
            {next.contributions_needed ? (
              <li>{next.contributions_needed} more confirmed contributions</li>
            ) : null}
            {next.projects_needed ? (
              <li>{next.projects_needed} more delivered project{next.projects_needed === 1 ? "" : "s"}</li>
            ) : null}
            {next.requires_teaching ? (
              <li className="text-ember-700 dark:text-ember-300">
                Confirmed mentorship of another member — this level cannot be reached
                on output alone
              </li>
            ) : null}
          </ul>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="The ladder"
          subtitle="Published in full — nobody should have to guess how to advance"
        />
        <ol className="p-5 pt-3 space-y-3">
          {(levels.data?.results ?? []).map((level) => {
            const reached = (level.rank ?? 0) <= currentRank;
            return (
              <li
                key={level.id}
                className={cn(
                  "rounded-lg border p-4 flex items-start gap-3.5",
                  reached
                    ? "border-ember-300 bg-ember-50/50 dark:bg-ember-700/10"
                    : "border-line",
                )}
              >
                <span
                  className={cn(
                    "grid place-items-center size-10 rounded-xl shrink-0",
                    reached ? "bg-ember-500 text-navy-950" : "bg-sunken text-muted",
                  )}
                >
                  {reached ? <Award className="size-5" aria-hidden /> : <Lock className="size-4" aria-hidden />}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-strong">{level.name}</h3>
                    {reached ? <Pill tone="ember">Reached</Pill> : null}
                    {level.requires_teaching ? <Pill tone="purple">Requires teaching</Pill> : null}
                  </div>
                  <p className="text-sm text-muted mt-1">{level.description}</p>
                  <p className="text-xs text-muted mt-1.5">
                    {level.min_points} points
                    {level.min_confirmed_contributions
                      ? ` · ${level.min_confirmed_contributions} contributions`
                      : ""}
                    {level.min_completed_projects
                      ? ` · ${level.min_completed_projects} delivered projects`
                      : ""}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </Card>

      <Card>
        <CardHeader title="Badges" subtitle="How each one is earned is published on it" />
        <div className="p-5 pt-3 grid gap-3 sm:grid-cols-2">
          {(badges.data?.results ?? []).map((badge) => (
            <div key={badge.id} className="rounded-lg border border-line p-4">
              <div className="flex items-start gap-3">
                <Award className="size-5 text-ember-500 shrink-0 mt-0.5" aria-hidden />
                <div className="min-w-0">
                  <h3 className="font-medium text-strong">{badge.name}</h3>
                  <p className="text-sm text-muted mt-0.5">{badge.description}</p>
                  <p className="text-xs text-muted mt-1.5 italic">{badge.criteria}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Certificates"
          subtitle="Only you can download these. Anyone can check one with its code."
        />
        {error ? <div className="px-5 pt-3"><FormError message={error} /></div> : null}
        {(certificates.data?.results ?? []).length === 0 ? (
          <EmptyState
            title="No certificates yet"
            description="A certificate is issued once you have confirmed contributions on a delivered project."
          />
        ) : (
          <ul className="p-5 pt-3 divide-y divide-line">
            {(certificates.data?.results ?? []).map((certificate) => (
              <li key={certificate.id} className="py-4 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-medium text-strong">{certificate.kind_display}</h3>
                    {certificate.project_title ? (
                      <p className="text-sm text-muted">{certificate.project_title}</p>
                    ) : null}
                    <p className="text-sm text-body mt-2 leading-relaxed">
                      {certificate.statement}
                    </p>
                  </div>
                  <div className="text-right shrink-0 space-y-2">
                    <code className="block text-sm font-mono text-brand-600">
                      {certificate.verification_code}
                    </code>
                    <p className="text-xs text-muted">
                      {certificate.issued_at
                        ? format(new Date(certificate.issued_at), "d MMM yyyy")
                        : ""}
                    </p>
                    <div className="flex gap-2 justify-end">
                      <Button
                        size="sm"
                        loading={downloading === certificate.verification_code}
                        onClick={() => void download(certificate.verification_code)}
                        icon={<Download className="size-3.5" aria-hidden />}
                      >
                        PDF
                      </Button>
                      <Link
                        to={`/verify-certificate/${certificate.verification_code}`}
                        className="inline-flex items-center h-8 px-3 rounded-lg border border-line text-xs font-medium text-body hover:bg-sunken"
                      >
                        Verify
                      </Link>
                    </div>
                  </div>
                </div>

                {/*
                  The holder's own audit trail. Nobody else sees it. Shown
                  because a certificate they downloaded once that reports four
                  downloads means something is wrong with the account, and
                  they are the only person positioned to notice.
                */}
                <div className="mt-4 pt-3 border-t border-line">
                  {(certificate.download_count ?? 0) === 0 ? (
                    <p className="text-xs text-muted">
                      Not downloaded yet. Only you can download this — anyone else
                      checks it with the code above.
                    </p>
                  ) : (
                    <details className="group">
                      <summary className="flex items-center gap-1.5 text-xs text-muted cursor-pointer list-none hover:text-body">
                        <History className="size-3.5" aria-hidden />
                        Downloaded {certificate.download_count} time
                        {certificate.download_count === 1 ? "" : "s"}
                        {certificate.last_downloaded_at
                          ? `, last ${formatDistanceToNow(new Date(certificate.last_downloaded_at), { addSuffix: true })}`
                          : ""}
                        <ChevronDown
                          className="size-3.5 transition-transform group-open:rotate-180"
                          aria-hidden
                        />
                      </summary>
                      <ul className="mt-2.5 space-y-1.5">
                        {(certificate.downloads ?? []).map((entry) => (
                          <li
                            key={entry.id}
                            className="flex items-center justify-between gap-3 text-xs"
                          >
                            <span className="text-body">
                              {entry.downloaded_by_name}
                              {entry.was_holder ? "" : " (on your behalf)"}
                            </span>
                            <span className="text-muted tabular-nums shrink-0">
                              {entry.downloaded_at
                                ? format(new Date(entry.downloaded_at), "d MMM yyyy, HH:mm")
                                : ""}
                            </span>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2.5 text-[11px] text-muted leading-relaxed">
                        Every copy is stamped with the moment it was taken, so a copy
                        that gets out can be traced back to one download.
                      </p>
                    </details>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
