import { BellOff, Check } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useNotificationMutations, useNotifications } from "@/api/queries";
import { Button, Card, EmptyState, Loading, PageHeader, Pill } from "@/components/ui";
import { cn } from "@/lib/cn";

export function Notifications() {
  const { data, isLoading } = useNotifications();
  const { markRead, markAllRead } = useNotificationMutations();
  const items = data?.results ?? [];
  const unread = items.filter((item) => !item.is_read).length;

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Notifications"
        description="Everything is recorded here. Email is a digest by default — change that in settings."
        action={
          unread > 0 ? (
            <Button
              variant="secondary"
              size="sm"
              loading={markAllRead.isPending}
              onClick={() => void markAllRead.mutateAsync()}
              icon={<Check className="size-4" aria-hidden />}
            >
              Mark all read
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <Loading />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<BellOff className="size-10" aria-hidden />}
            title="Nothing to tell you"
            description="You will hear from us when somebody applies to your project, when a contribution needs confirming, or when yours is confirmed."
          />
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((notification) => (
            <Card
              key={notification.id}
              className={cn("p-4", !notification.is_read && "border-brand-300 bg-brand-50/40 dark:bg-brand-900/15")}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <Pill tone={notification.is_read ? "neutral" : "brand"}>
                      {notification.category_display}
                    </Pill>
                    <span className="text-xs text-muted">
                      {notification.created_at
                        ? formatDistanceToNow(new Date(notification.created_at), {
                            addSuffix: true,
                          })
                        : ""}
                    </span>
                  </div>
                  <p className="text-sm text-body">{notification.summary}</p>
                </div>
                {!notification.is_read ? (
                  <button
                    onClick={() => void markRead.mutateAsync(notification.id)}
                    className="shrink-0 p-1.5 rounded-lg text-muted hover:bg-sunken hover:text-brand-600"
                    aria-label="Mark as read"
                  >
                    <Check className="size-4" />
                  </button>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
