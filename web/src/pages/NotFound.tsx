import { Compass } from "lucide-react";
import { Card, EmptyState, LinkButton } from "@/components/ui";

export function NotFound() {
  return (
    <Card>
      <EmptyState
        icon={<Compass className="size-10" aria-hidden />}
        title="That page does not exist"
        description="The link may be out of date, or the project may be a draft that is not yours to see."
        action={<LinkButton to="/dashboard">Back to the dashboard</LinkButton>}
      />
    </Card>
  );
}
