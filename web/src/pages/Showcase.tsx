import { ExternalLink, FlaskConical, PlayCircle } from "lucide-react";
import { format } from "date-fns";
import { useShowcase } from "@/api/queries";
import {
  Avatar, Card, EmptyState, LinkButton, Loading, PageHeader, Pill,
} from "@/components/ui";

export function Showcase() {
  const { data, isLoading } = useShowcase();
  const entries = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Showcase"
        description="Delivered work, written up for someone outside the University to read."
      />

      {isLoading ? (
        <Loading />
      ) : entries.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FlaskConical className="size-10" aria-hidden />}
            title="Nothing published yet"
            description="A showcase entry is written by the project lead once a project reaches documentation. It is the artefact the whole lifecycle produces."
            action={<LinkButton to="/discover">See what is being built</LinkButton>}
          />
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {entries.map((entry) => (
            <Card key={entry.id} className="overflow-hidden flex flex-col">
              {entry.images?.[0] ? (
                <img
                  src={entry.images[0].image}
                  alt={entry.images[0].alt_text}
                  className="w-full h-44 object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="h-44 bg-navy-900 grid place-items-center">
                  <FlaskConical className="size-10 text-navy-600" aria-hidden />
                </div>
              )}

              <div className="p-5 flex-1 flex flex-col">
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {entry.is_featured ? <Pill tone="ember">Featured</Pill> : null}
                  {entry.discipline_areas?.map((area) => (
                    <Pill key={area} tone="brand">
                      {area}
                    </Pill>
                  ))}
                </div>

                <h3 className="font-semibold text-strong leading-snug">{entry.headline}</h3>
                <p className="text-sm text-muted mt-2 line-clamp-3 flex-1">
                  {entry.what_we_built}
                </p>

                <div className="flex items-center gap-2 mt-4">
                  {(entry.team ?? []).slice(0, 5).map((person) => (
                    <Avatar
                      key={person.id}
                      name={person.display_name ?? "?"}
                      src={person.avatar}
                      size={28}
                      className="ring-2 ring-[--surface-card] -mr-2 last:mr-0"
                    />
                  ))}
                  <span className="text-xs text-muted ml-3">
                    {(entry.team ?? []).length} on the team
                  </span>
                </div>

                <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t border-line text-sm">
                  {entry.demonstration_url ? (
                    <a
                      href={entry.demonstration_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1.5 text-brand-600 hover:underline"
                    >
                      <PlayCircle className="size-4" aria-hidden /> Demonstration
                    </a>
                  ) : null}
                  {entry.live_url ? (
                    <a
                      href={entry.live_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1.5 text-brand-600 hover:underline"
                    >
                      <ExternalLink className="size-4" aria-hidden /> Try it
                    </a>
                  ) : null}
                  {entry.published_at ? (
                    <span className="text-muted ml-auto">
                      {format(new Date(entry.published_at), "MMM yyyy")}
                    </span>
                  ) : null}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
