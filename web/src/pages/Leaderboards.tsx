import { Link } from "react-router-dom";
import { Trophy } from "lucide-react";
import { useLeaderboards } from "@/api/queries";
import { Card, CardHeader, EmptyState, Loading, PageHeader, Pill } from "@/components/ui";
import { cn } from "@/lib/cn";

/**
 * Boards are scoped and frozen per trimester.
 *
 * There is no global all-members ranking, deliberately: one would be won
 * permanently by whoever writes the most code, and a Nursing or Education
 * student would never appear on it.
 */
export function Leaderboards() {
  const { data, isLoading } = useLeaderboards();
  const boards = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Leaderboards"
        description="One board per discipline area, recomputed each trimester. There is no single overall ranking, on purpose."
      />

      {isLoading ? (
        <Loading />
      ) : boards.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Trophy className="size-10" aria-hidden />}
            title="No boards yet"
            description="Boards are computed on a schedule once contributions start settling into the ledger."
          />
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {boards.map((board) => (
            <Card key={board.id}>
              <CardHeader
                title={board.discipline_area_name ?? board.scope}
                subtitle={`${board.period_start} to ${board.period_end}`}
              />
              {(board.rows as Array<Record<string, unknown>>).length === 0 ? (
                <p className="p-5 pt-3 text-sm text-muted">Nothing recorded this period.</p>
              ) : (
                <ol className="p-5 pt-3 space-y-1">
                  {(board.rows as Array<{
                    rank: number;
                    display_name: string;
                    public_slug: string | null;
                    points: number;
                    contributions: number;
                  }>).map((row) => (
                    <li
                      key={row.rank}
                      className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-sunken"
                    >
                      <span
                        className={cn(
                          "grid place-items-center size-7 rounded-lg text-xs font-bold shrink-0 tabular-nums",
                          row.rank === 1
                            ? "bg-ember-500 text-navy-950"
                            : row.rank <= 3
                              ? "bg-ember-100 text-ember-700 dark:bg-ember-700/30 dark:text-ember-200"
                              : "bg-sunken text-muted",
                        )}
                      >
                        {row.rank}
                      </span>
                      <span className="flex-1 min-w-0 text-sm">
                        {/* A member who made their portfolio private is ranked
                            but not linked: appearing on a board is not consent
                            to be looked up. */}
                        {row.public_slug ? (
                          <Link
                            to={`/p/${row.public_slug}`}
                            className="text-strong font-medium hover:text-brand-600 truncate"
                          >
                            {row.display_name}
                          </Link>
                        ) : (
                          <span className="text-strong font-medium truncate">
                            {row.display_name}
                          </span>
                        )}
                      </span>
                      <Pill tone="ember">{row.points} pts</Pill>
                      <span className="text-xs text-muted tabular-nums shrink-0 w-16 text-right">
                        {row.contributions} logged
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
