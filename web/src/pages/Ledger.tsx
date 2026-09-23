import { ShieldAlert, ShieldCheck } from "lucide-react";
import { format } from "date-fns";
import { useLedger, useLedgerVerification } from "@/api/queries";
import { Card, EmptyState, Loading, PageHeader, Pill } from "@/components/ui";

/**
 * The public record.
 *
 * Readable without an account on purpose. A verifiable ledger that only members
 * can read is not verifiable by the people it needs to convince.
 */
export function Ledger() {
  const { data, isLoading } = useLedger();
  const verification = useLedgerVerification();

  const intact = verification.data?.intact;

  return (
    <div>
      <PageHeader
        title="The contribution ledger"
        description="Every confirmed contribution on FORGE, in the order it was settled. Append-only and hash-chained: altering any entry invalidates every entry after it."
      />

      <Card
        className={`p-5 mb-6 ${
          intact === false
            ? "border-red-300 bg-red-50/60 dark:bg-red-950/20"
            : "border-emerald-300 bg-emerald-50/50 dark:bg-emerald-950/20"
        }`}
      >
        <div className="flex items-start gap-3.5">
          {intact === false ? (
            <ShieldAlert className="size-6 text-red-600 shrink-0" aria-hidden />
          ) : (
            <ShieldCheck className="size-6 text-emerald-600 shrink-0" aria-hidden />
          )}
          <div>
            <p className="font-semibold text-strong">
              {verification.isLoading
                ? "Checking the chain…"
                : intact
                  ? "Chain intact — every link verifies"
                  : "Chain verification FAILED"}
            </p>
            <p className="text-sm text-body mt-0.5">
              {intact === false
                ? "A settled record appears to have been altered. This has been reported and should be investigated immediately."
                : `${verification.data?.checked ?? 0} entries checked. Anyone can run this check — it needs no account.`}
            </p>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <Loading />
      ) : (data?.results ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={<ShieldCheck className="size-10" aria-hidden />}
            title="The ledger is empty"
            description="Nothing has been confirmed yet. The first entry appears when a project lead and a mentor both confirm the same contribution."
          />
        </Card>
      ) : (
        <div className="space-y-2">
          {(data?.results ?? []).map((entry) => (
            <Card key={entry.sequence} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <span className="font-mono text-xs text-muted">#{entry.sequence}</span>
                    <span className="font-medium text-strong">
                      {entry.contributor?.display_name ?? "Former member"}
                    </span>
                    <Pill tone="brand">{entry.dimension}</Pill>
                    {entry.is_intact ? (
                      <Pill tone="green" icon={<ShieldCheck className="size-3" aria-hidden />}>
                        verified
                      </Pill>
                    ) : (
                      <Pill tone="red">hash mismatch</Pill>
                    )}
                  </div>
                  <p className="text-sm text-body line-clamp-2">
                    {(entry.payload as { description?: string })?.description}
                  </p>
                  <p className="text-xs text-muted mt-1.5">
                    {entry.project_title}
                    {entry.recorded_at
                      ? ` · ${format(new Date(entry.recorded_at), "d MMM yyyy HH:mm")}`
                      : ""}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold text-strong tabular-nums">
                    {entry.points} pts
                  </div>
                  <code className="text-[10px] text-muted block mt-1">
                    {entry.entry_hash?.slice(0, 10)}…
                  </code>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
