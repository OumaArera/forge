import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { BadgeCheck, Lock, Search, ShieldAlert } from "lucide-react";
import { format } from "date-fns";
import { api } from "@/api/client";
import { Button, Card, Field, Input, Loading } from "@/components/ui";

type Result = {
  valid: boolean;
  recipient_name?: string;
  kind?: string;
  project?: string | null;
  statement?: string;
  issued_at?: string;
  revoked_at?: string | null;
  revoked_reason?: string | null;
  ledger_head_at_issue?: string | null;
  issuer?: string;
  note?: string;
  download_count?: number;
  last_downloaded_at?: string | null;
  downloadable_by?: string;
  detail?: string;
};

/**
 * Checking a certificate.
 *
 * Written for whoever was handed one — an employer, an internship provider —
 * so it assumes no account, no knowledge of FORGE, and no patience. Type the
 * code, get an answer, and see plainly what the answer does and does not
 * mean.
 */
export function VerifyCertificate() {
  const { code: routeCode } = useParams();
  const [code, setCode] = useState(routeCode ?? "");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);

  async function check(value: string) {
    if (!value.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const { data } = await api.get<Result>(
        `/recognition/certificates/verify/${value.trim()}/`,
      );
      setResult(data);
    } catch (caught) {
      const response = (caught as { response?: { data?: Result } }).response;
      setResult(response?.data ?? { valid: false, detail: "Could not check that code." });
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (routeCode) void check(routeCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeCode]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void check(code);
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-strong">Check a FORGE certificate</h1>
      <p className="text-sm text-muted mt-2 leading-relaxed">
        Enter the code printed on the certificate. No account needed — this is
        the same check anybody can run.
      </p>

      <Card className="p-5 mt-6">
        <form onSubmit={onSubmit} className="flex flex-wrap gap-3 items-end">
          <Field label="Verification code" className="flex-1 min-w-56">
            <Input
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              placeholder="H7KM-P3QR-9TWX"
              className="font-mono tracking-wider"
              autoFocus={!routeCode}
            />
          </Field>
          <Button
            type="submit"
            loading={busy}
            size="lg"
            icon={<Search className="size-4" aria-hidden />}
          >
            Check it
          </Button>
        </form>
      </Card>

      {busy ? <Loading label="Checking" /> : null}

      {result ? (
        <Card
          className={`p-6 mt-5 ${
            result.valid
              ? "border-emerald-300 bg-emerald-50/50 dark:bg-emerald-950/20"
              : "border-red-300 bg-red-50/50 dark:bg-red-950/20"
          }`}
        >
          <div className="flex items-start gap-4">
            {result.valid ? (
              <BadgeCheck className="size-8 text-emerald-600 shrink-0" aria-hidden />
            ) : (
              <ShieldAlert className="size-8 text-red-600 shrink-0" aria-hidden />
            )}
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-bold text-strong">
                {result.valid
                  ? "Valid — FORGE issued this"
                  : result.revoked_at
                    ? "This certificate has been withdrawn"
                    : "No certificate with that code"}
              </h2>

              {result.recipient_name ? (
                <dl className="mt-4 space-y-3">
                  <Detail label="Issued to" value={result.recipient_name} />
                  <Detail label="For" value={result.kind} />
                  {result.project ? <Detail label="Project" value={result.project} /> : null}
                  <Detail
                    label="Issued"
                    value={
                      result.issued_at
                        ? format(new Date(result.issued_at), "d MMMM yyyy")
                        : undefined
                    }
                  />
                  {result.revoked_reason ? (
                    <Detail label="Withdrawn because" value={result.revoked_reason} />
                  ) : null}
                </dl>
              ) : null}

              {result.statement ? (
                <p className="text-sm text-body mt-4 leading-relaxed border-l-3 border-line pl-4">
                  {result.statement}
                </p>
              ) : null}

              {result.detail && !result.recipient_name ? (
                <p className="text-sm text-body mt-2">{result.detail}</p>
              ) : null}

              {result.valid ? (
                <div className="mt-5 flex items-start gap-2.5 rounded-lg border border-line bg-sunken p-3.5">
                  <Lock className="size-4 text-muted shrink-0 mt-0.5" aria-hidden />
                  <p className="text-xs text-body leading-relaxed">
                    {/*
                      The code is printed on the document, so letting anyone
                      holding it pull a clean copy would let anyone ever shown
                      a certificate pass one off as their own. Verifying it is
                      what an employer needs, and that is what this page is.
                    */}
                    <strong className="text-strong">
                      Only the person it was issued to can download this.
                    </strong>{" "}
                    What you are reading is the check itself — it comes from FORGE,
                    not from the document you were handed.
                    {result.download_count
                      ? ` The holder has taken ${result.download_count} cop${result.download_count === 1 ? "y" : "ies"} of it.`
                      : " The holder has never downloaded it, which is worth asking about."}
                  </p>
                </div>
              ) : null}

              {result.ledger_head_at_issue ? (
                <p className="text-xs font-mono text-muted mt-4 break-all">
                  Ledger at issue: {result.ledger_head_at_issue.slice(0, 40)}…
                </p>
              ) : null}
            </div>
          </div>

          {result.note ? (
            <p className="text-xs text-muted mt-5 pt-4 border-t border-line leading-relaxed">
              {result.note}
            </p>
          ) : null}
        </Card>
      ) : null}

      <Card className="p-5 mt-5">
        <h3 className="text-sm font-semibold text-strong">What a valid result means</h3>
        <ul className="text-sm text-body mt-2.5 space-y-1.5 list-disc pl-5">
          <li>FORGE issued this certificate, and it has not been withdrawn.</li>
          <li>
            The work behind it was confirmed independently by two other people — the
            project lead and the project's assigned mentor.
          </li>
        </ul>
        <h3 className="text-sm font-semibold text-strong mt-4">What it does not mean</h3>
        <ul className="text-sm text-body mt-2.5 space-y-1.5 list-disc pl-5">
          <li>
            It is not an award of the University and carries no academic credit.
          </li>
          <li>It records that work was delivered and confirmed. It does not grade it.</li>
          <li>
            It is not a copy of the document. Only the holder can download that —
            this check is the part you can trust, because it comes from us.
          </li>
        </ul>
      </Card>
    </div>
  );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex flex-wrap gap-x-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted w-32 shrink-0 pt-0.5">
        {label}
      </dt>
      <dd className="text-sm text-strong font-medium min-w-0">{value}</dd>
    </div>
  );
}
