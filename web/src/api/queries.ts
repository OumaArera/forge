/**
 * Query and mutation hooks.
 *
 * One file rather than one per feature: the app has a single API and a single
 * cache, and keeping the key hierarchy in one place is what stops two
 * components inventing two different keys for the same resource and then
 * failing to invalidate each other.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "./client";
import type {
  AdminOverview,
  Application,
  Certificate,
  Contribution,
  EmailLog,
  Invitation,
  Leaderboard,
  LedgerEntry,
  Level,
  MentorProfile,
  MentorshipRequest,
  Milestone,
  Notification,
  Page,
  Portfolio,
  ProgressUpdate,
  Project,
  ProjectReview,
  ProjectRole,
  ProjectSummary,
  PublicUser,
  ReferenceData,
  RoleSuggestion,
  ShowcaseEntry,
  Space,
  Standing,
  Task,
  Thread,
  ThreadDetail,
} from "./types";

export const keys = {
  reference: ["reference"] as const,
  me: ["me"] as const,
  mySkills: ["me", "skills"] as const,
  standing: (slug?: string) => ["standing", slug ?? "me"] as const,
  members: (params?: unknown) => ["members", params] as const,
  member: (slug: string) => ["member", slug] as const,
  suggestedRoles: ["suggested-roles"] as const,

  projects: (params?: unknown) => ["projects", params] as const,
  project: (slug: string) => ["project", slug] as const,
  projectTeam: (slug: string) => ["project", slug, "team"] as const,
  projectHistory: (slug: string) => ["project", slug, "history"] as const,
  projectReviews: (slug: string) => ["project", slug, "reviews"] as const,
  myProjects: ["projects", "mine"] as const,
  reviewQueue: ["projects", "awaiting-review"] as const,
  applications: (params?: unknown) => ["applications", params] as const,

  contributions: (params?: unknown) => ["contributions", params] as const,
  attestationQueue: ["contributions", "awaiting-attestation"] as const,
  ledger: (params?: unknown) => ["ledger", params] as const,
  ledgerVerify: ["ledger", "verify"] as const,

  levels: ["levels"] as const,
  badges: ["badges"] as const,
  leaderboards: (params?: unknown) => ["leaderboards", params] as const,
  certificates: ["certificates"] as const,

  spaces: ["spaces"] as const,
  threads: (params?: unknown) => ["threads", params] as const,
  thread: (id: string) => ["thread", id] as const,

  milestones: (project?: string) => ["milestones", project] as const,
  tasks: (params?: unknown) => ["tasks", params] as const,
  myTasks: ["tasks", "mine"] as const,
  progressUpdates: (project?: string) => ["progress-updates", project] as const,

  mentors: (params?: unknown) => ["mentors", params] as const,
  availableMentors: ["mentors", "available"] as const,
  mentorshipRequests: ["mentorship-requests"] as const,

  showcase: (params?: unknown) => ["showcase", params] as const,
  notifications: (params?: unknown) => ["notifications", params] as const,
  unreadCount: ["notifications", "unread-count"] as const,
  portfolio: (slug: string) => ["portfolio", slug] as const,

  adminOverview: ["admin", "overview"] as const,
  adminMembers: (params?: unknown) => ["admin", "members", params] as const,
  invitations: (params?: unknown) => ["admin", "invitations", params] as const,
  emailLog: (params?: unknown) => ["admin", "email-log", params] as const,
};

async function get<T>(url: string, params?: unknown): Promise<T> {
  const { data } = await api.get<T>(url, { params: params as object });
  return data;
}

type Options<T> = Omit<UseQueryOptions<T, unknown, T, readonly unknown[]>, "queryKey" | "queryFn">;

// ---------------------------------------------------------------- reference

export const useReference = () =>
  useQuery({
    queryKey: keys.reference,
    queryFn: () => get<ReferenceData>("/accounts/reference/"),
    // Schools and programmes change once a year at most.
    staleTime: 60 * 60 * 1000,
  });

// ------------------------------------------------------------------ members

export const useSuggestedRoles = () =>
  useQuery({
    queryKey: keys.suggestedRoles,
    queryFn: () => get<RoleSuggestion[]>("/accounts/members/suggested-roles/"),
  });

export const useMembers = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.members(params),
    queryFn: () => get<Page<PublicUser>>("/accounts/members/", params),
  });

export const useMySkills = () =>
  useQuery({
    queryKey: keys.mySkills,
    queryFn: () => get<Page<import("./types").UserSkill>>("/accounts/my-skills/"),
  });

// ----------------------------------------------------------------- projects

export const useProjects = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.projects(params),
    queryFn: () => get<Page<ProjectSummary>>("/projects/", params),
  });

export const useMyProjects = () =>
  useQuery({
    queryKey: keys.myProjects,
    queryFn: () => get<Page<ProjectSummary>>("/projects/mine/"),
  });

export const useProject = (slug: string, options?: Options<Project>) =>
  useQuery({
    queryKey: keys.project(slug),
    queryFn: () => get<Project>(`/projects/${slug}/`),
    ...options,
  });

export const useProjectHistory = (slug: string) =>
  useQuery({
    queryKey: keys.projectHistory(slug),
    queryFn: () => get<import("./types").StageTransition[]>(`/projects/${slug}/history/`),
  });

export const useReviewQueue = (enabled = true) =>
  useQuery({
    queryKey: keys.reviewQueue,
    queryFn: () => get<Page<ProjectSummary>>("/projects/awaiting-review/"),
    enabled,
  });

export const useApplications = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.applications(params),
    queryFn: () => get<Page<Application>>("/projects/applications/", params),
  });

export function useProjectMutations(slug?: string) {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
    void queryClient.invalidateQueries({ queryKey: ["project"] });
    void queryClient.invalidateQueries({ queryKey: keys.reviewQueue });
  };

  return {
    create: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<Project>("/projects/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.patch<Project>(`/projects/${slug}/`, body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    // Takes an explicit slug so that the proposal form, which creates the
    // project and its roles in one go, can add roles to a project that did not
    // exist when this hook was called.
    addRole: useMutation({
      mutationFn: ({ slug: target, ...body }: { slug?: string } & Record<string, unknown>) =>
        api
          .post<ProjectRole>(`/projects/${target ?? slug}/roles/`, body)
          .then((r) => r.data),
      onSuccess: invalidate,
    }),
    submit: useMutation({
      mutationFn: () => api.post<Project>(`/projects/${slug}/submit/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
    review: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<ProjectReview>(`/projects/${slug}/review/`, body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    transition: useMutation({
      mutationFn: (body: { to_status: string; note?: string }) =>
        api.post<Project>(`/projects/${slug}/transition/`, body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    handOver: useMutation({
      mutationFn: (body: { to_user_id: string; note?: string }) =>
        api.post<Project>(`/projects/${slug}/hand-over-lead/`, body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    apply: useMutation({
      mutationFn: ({ roleId, statement }: { roleId: string; statement: string }) =>
        api.post<Application>(`/projects/roles/${roleId}/apply/`, { statement }).then((r) => r.data),
      onSuccess: () => {
        invalidate();
        void queryClient.invalidateQueries({ queryKey: ["applications"] });
        void queryClient.invalidateQueries({ queryKey: keys.suggestedRoles });
      },
    }),
    decideApplication: useMutation({
      mutationFn: ({ id, accept, note }: { id: string; accept: boolean; note?: string }) =>
        api.post<Application>(`/projects/applications/${id}/decide/`, { accept, note }).then((r) => r.data),
      onSuccess: () => {
        invalidate();
        void queryClient.invalidateQueries({ queryKey: ["applications"] });
      },
    }),
  };
}

// ------------------------------------------------------------ contributions

export const useContributions = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.contributions(params),
    queryFn: () => get<Page<Contribution>>("/contributions/", params),
  });

export const useAttestationQueue = () =>
  useQuery({
    queryKey: keys.attestationQueue,
    queryFn: () => get<Page<Contribution>>("/contributions/awaiting-my-attestation/"),
  });

export const useLedger = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.ledger(params),
    queryFn: () => get<Page<LedgerEntry>>("/contributions/ledger/", params),
  });

export const useLedgerVerification = () =>
  useQuery({
    queryKey: keys.ledgerVerify,
    queryFn: () =>
      get<{ checked: number; intact: boolean; head: number; problems: unknown[]; verified_at: string }>(
        "/contributions/ledger/verify/",
      ),
  });

export function useContributionMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["contributions"] });
    void queryClient.invalidateQueries({ queryKey: ["ledger"] });
    void queryClient.invalidateQueries({ queryKey: ["standing"] });
  };

  return {
    create: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<Contribution>("/contributions/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    submit: useMutation({
      mutationFn: (id: string) =>
        api.post<Contribution>(`/contributions/${id}/submit/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
    attest: useMutation({
      mutationFn: ({ id, confirm, note }: { id: string; confirm: boolean; note?: string }) =>
        api.post(`/contributions/${id}/attest/`, { confirm, note }).then((r) => r.data),
      onSuccess: invalidate,
    }),
    withdraw: useMutation({
      mutationFn: (id: string) =>
        api.post<Contribution>(`/contributions/${id}/withdraw/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
  };
}

// ------------------------------------------------------------- recognition

export const useStanding = () =>
  useQuery({
    queryKey: keys.standing(),
    queryFn: () => get<Standing>("/recognition/standings/me/"),
  });

export const useLevels = () =>
  useQuery({
    queryKey: keys.levels,
    queryFn: () => get<Page<Level>>("/recognition/levels/"),
    staleTime: 60 * 60 * 1000,
  });

export const useBadges = () =>
  useQuery({
    queryKey: keys.badges,
    queryFn: () => get<Page<import("./types").Badge>>("/recognition/badges/"),
    staleTime: 60 * 60 * 1000,
  });

export const useLeaderboards = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.leaderboards(params),
    queryFn: () => get<Page<Leaderboard>>("/recognition/leaderboards/", params),
  });

export const useCertificates = () =>
  useQuery({
    queryKey: keys.certificates,
    queryFn: () => get<Page<Certificate>>("/recognition/certificates/"),
  });

// --------------------------------------------------------------- community

export const useSpaces = () =>
  useQuery({
    queryKey: keys.spaces,
    queryFn: () => get<Page<Space>>("/community/spaces/"),
    staleTime: 30 * 60 * 1000,
  });

export const useThreads = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.threads(params),
    queryFn: () => get<Page<Thread>>("/community/threads/", params),
  });

export const useThread = (id: string) =>
  useQuery({
    queryKey: keys.thread(id),
    queryFn: () => get<ThreadDetail>(`/community/threads/${id}/`),
  });

export function useCommunityMutations(threadId?: string) {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["threads"] });
    if (threadId) void queryClient.invalidateQueries({ queryKey: keys.thread(threadId) });
  };

  return {
    createThread: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<Thread>("/community/threads/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    reply: useMutation({
      mutationFn: ({ id, body, parent }: { id: string; body: string; parent?: string }) =>
        api.post(`/community/threads/${id}/reply/`, { body, parent }).then((r) => r.data),
      onSuccess: invalidate,
    }),
    acceptAnswer: useMutation({
      mutationFn: ({ id, postId }: { id: string; postId: string }) =>
        api.post(`/community/threads/${id}/accept-answer/${postId}/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
    vote: useMutation({
      mutationFn: ({ postId, value }: { postId: string; value: 1 | -1 | 0 }) =>
        api.post(`/community/posts/${postId}/vote/`, { value }).then((r) => r.data),
      onSuccess: invalidate,
    }),
  };
}

// --------------------------------------------------------------- workspace

export const useMilestones = (project?: string) =>
  useQuery({
    queryKey: keys.milestones(project),
    queryFn: () => get<Page<Milestone>>("/workspace/milestones/", { project }),
    enabled: Boolean(project),
  });

export const useTasks = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.tasks(params),
    queryFn: () => get<Page<Task>>("/workspace/tasks/", params),
  });

export const useMyTasks = () =>
  useQuery({
    queryKey: keys.myTasks,
    queryFn: () => get<Task[]>("/workspace/tasks/mine/"),
  });

export const useProgressUpdates = (project?: string) =>
  useQuery({
    queryKey: keys.progressUpdates(project),
    queryFn: () => get<Page<ProgressUpdate>>("/workspace/progress-updates/", { project }),
    enabled: Boolean(project),
  });

export function useWorkspaceMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    void queryClient.invalidateQueries({ queryKey: ["milestones"] });
    void queryClient.invalidateQueries({ queryKey: ["progress-updates"] });
  };

  return {
    createTask: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<Task>("/workspace/tasks/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    updateTask: useMutation({
      mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
        api.patch<Task>(`/workspace/tasks/${id}/`, body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    createMilestone: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<Milestone>("/workspace/milestones/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    postUpdate: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<ProgressUpdate>("/workspace/progress-updates/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
  };
}

// -------------------------------------------------------------- mentorship

export const useAvailableMentors = () =>
  useQuery({
    queryKey: keys.availableMentors,
    queryFn: () => get<MentorProfile[]>("/mentorship/mentors/available/"),
  });

export const useMentorshipRequests = () =>
  useQuery({
    queryKey: keys.mentorshipRequests,
    queryFn: () => get<Page<MentorshipRequest>>("/mentorship/requests/"),
  });

// ----------------------------------------------------------------- showcase

export const useShowcase = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.showcase(params),
    queryFn: () => get<Page<ShowcaseEntry>>("/showcase/", params),
  });

// ------------------------------------------------------------ notifications

export const useNotifications = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.notifications(params),
    queryFn: () => get<Page<Notification>>("/notifications/", params),
  });

export const useUnreadCount = () =>
  useQuery({
    queryKey: keys.unreadCount,
    queryFn: () =>
      get<{ total: number; by_category: Record<string, number> }>(
        "/notifications/unread-count/",
      ),
    refetchInterval: 60_000,
  });

export function useNotificationMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };
  return {
    markRead: useMutation({
      mutationFn: (id: string) => api.post(`/notifications/${id}/read/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
    markAllRead: useMutation({
      mutationFn: () => api.post("/notifications/read-all/").then((r) => r.data),
      onSuccess: invalidate,
    }),
  };
}

// ---------------------------------------------------------------- portfolio

export const usePortfolio = (slug: string) =>
  useQuery({
    queryKey: keys.portfolio(slug),
    queryFn: () => get<Portfolio>(`/portfolio/${slug}/`),
  });


// ------------------------------------------------------------ administration

export const useAdminOverview = (enabled = true) =>
  useQuery({
    queryKey: keys.adminOverview,
    queryFn: () => get<AdminOverview>("/accounts/admin/overview/"),
    enabled,
  });

export const useAdminMembers = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.adminMembers(params),
    queryFn: () => get<Page<import("./types").Me>>("/accounts/admin/members/", params),
  });

export const useInvitations = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.invitations(params),
    queryFn: () => get<Page<Invitation>>("/accounts/invitations/", params),
  });

export const useEmailLog = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: keys.emailLog(params),
    queryFn: () => get<Page<EmailLog>>("/accounts/admin/email-log/", params),
  });

export const useRoleGrants = () =>
  useQuery({
    queryKey: ["admin", "role-grants"] as const,
    queryFn: () => get<Page<import("./types").RoleGrant>>("/accounts/role-grants/"),
  });

export function useAdminMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin"] });
  };

  return {
    invite: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post<Invitation>("/accounts/invitations/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    resendInvitation: useMutation({
      mutationFn: (id: string) =>
        api.post(`/accounts/invitations/${id}/resend/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
    revokeInvitation: useMutation({
      mutationFn: (id: string) => api.delete(`/accounts/invitations/${id}/`),
      onSuccess: invalidate,
    }),
    grantRole: useMutation({
      mutationFn: (body: Record<string, unknown>) =>
        api.post("/accounts/role-grants/", body).then((r) => r.data),
      onSuccess: invalidate,
    }),
    revokeRole: useMutation({
      mutationFn: (id: string) => api.delete(`/accounts/role-grants/${id}/`),
      onSuccess: invalidate,
    }),
    suspend: useMutation({
      mutationFn: ({ slug, reason }: { slug: string; reason: string }) =>
        api.post(`/accounts/admin/members/${slug}/suspend/`, { reason }).then((r) => r.data),
      onSuccess: invalidate,
    }),
    reinstate: useMutation({
      mutationFn: (slug: string) =>
        api.post(`/accounts/admin/members/${slug}/reinstate/`).then((r) => r.data),
      onSuccess: invalidate,
    }),
    resetPassword: useMutation({
      mutationFn: (slug: string) =>
        api.post<{ delivered: boolean; detail: string }>(
          `/accounts/admin/members/${slug}/reset-password/`,
        ).then((r) => r.data),
      onSuccess: invalidate,
    }),
    unlock: useMutation({
      mutationFn: (slug: string) =>
        api.post<{ was_locked: boolean; detail: string }>(
          `/accounts/admin/members/${slug}/unlock/`,
        ).then((r) => r.data),
      onSuccess: invalidate,
    }),
  };
}

// ------------------------------------------------------------- the account

export function useAccountMutations() {
  const queryClient = useQueryClient();
  const refreshMe = () => {
    void queryClient.invalidateQueries({ queryKey: keys.me });
  };

  return {
    setRecoveryEmail: useMutation({
      mutationFn: (recovery_email: string) =>
        api.post<{ member: import("./types").Me; delivered: boolean; detail: string }>(
          "/accounts/me/recovery-email/", { recovery_email },
        ).then((r) => r.data),
      onSuccess: refreshMe,
    }),
    resendRecoveryEmail: useMutation({
      mutationFn: () =>
        api.post<{ delivered: boolean; detail: string }>(
          "/accounts/me/recovery-email/resend/",
        ).then((r) => r.data),
    }),
    cancelRecoveryEmail: useMutation({
      mutationFn: () =>
        api.delete<import("./types").Me>("/accounts/me/recovery-email/").then((r) => r.data),
      onSuccess: refreshMe,
    }),
    changePassword: useMutation({
      mutationFn: (body: { current_password: string; new_password: string }) =>
        api.post<{ member: import("./types").Me }>("/accounts/me/password/", body)
          .then((r) => r.data),
      onSuccess: refreshMe,
    }),
  };
}
