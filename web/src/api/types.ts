/**
 * Hand-written aliases over the generated schema.
 *
 * `schema.d.ts` is regenerated from the backend with `npm run api:types` and
 * must never be edited. This file is the stable surface the app imports, so a
 * rename on the server shows up as one compile error here rather than fifty
 * across the components.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type Member = S["Member"];
export type Me = S["Me"];
export type PublicUser = S["PublicUser"];
export type School = S["School"];
export type Programme = S["Programme"];
export type DisciplineArea = S["DisciplineArea"];
export type Skill = S["Skill"];
export type UserSkill = S["UserSkill"];
export type Invitation = S["Invitation"];
export type RoleGrant = S["RoleGrant"];
export type EmailLog = S["EmailLog"];

export type Project = S["ProjectDetail"];
export type ProjectSummary = S["ProjectList"];
export type ProjectRole = S["ProjectRole"];
export type Application = S["Application"];
export type Membership = S["Membership"];
export type ProjectReview = S["ProjectReview"];
export type StageTransition = S["StageTransition"];
export type RoleSuggestion = S["RoleSuggestion"];

export type Contribution = S["Contribution"];
export type Attestation = S["Attestation"];
export type LedgerEntry = S["LedgerEntry"];

export type Standing = S["Standing"];
export type Level = S["Level"];
export type Badge = S["Badge"];
export type Certificate = S["Certificate"];
export type Leaderboard = S["Leaderboard"];

export type Thread = S["ThreadList"];
export type ThreadDetail = S["ThreadDetail"];
export type Post = S["Post"];
export type Space = S["Space"];

export type Milestone = S["Milestone"];
export type Task = S["Task"];
export type ProgressUpdate = S["ProgressUpdate"];

export type MentorProfile = S["MentorProfile"];
export type MentorshipRequest = S["MentorshipRequest"];
export type OfficeHour = S["OfficeHour"];

export type ShowcaseEntry = S["ShowcaseEntry"];
export type Notification = S["Notification"];
export type NotificationPreference = S["NotificationPreference"];
export type Report = S["Report"];

/** The paginated envelope every list endpoint returns. */
export type Page<T> = {
  count: number;
  page: number;
  pages: number;
  page_size: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

/** The seven lifecycle stages, in the order the concept proposal sets out. */
export const PROJECT_STAGES = [
  { number: 1, label: "Proposal" },
  { number: 2, label: "Review" },
  { number: 3, label: "Team" },
  { number: 4, label: "Build" },
  { number: 5, label: "Test" },
  { number: 6, label: "Document" },
  { number: 7, label: "Recognition" },
] as const;

export type ProjectStatus = NonNullable<ProjectSummary["status"]>;

/** Everything the reference endpoint returns, in one call. */
export type ReferenceData = {
  identity: {
    oidc_enabled: boolean;
    university_email_domains: string[];
    credentials_by_email: boolean;
  };
  schools: School[];
  programmes: Programme[];
  discipline_areas: DisciplineArea[];
  skills: Skill[];
};

/** A public portfolio document, as served and as exported. */
export type Portfolio = {
  format: string;
  generated_at: string;
  platform: { name: string; institution: string; url: string; note: string };
  member: {
    display_name: string;
    public_slug: string;
    portfolio_url: string;
    school: string | null;
    programme: string | null;
    status: string;
    headline: string;
    bio: string;
    links: Record<string, string>;
    member_since: string;
  };
  standing: {
    level?: string | null;
    total_points?: number;
    confirmed_contributions?: number;
    completed_projects?: number;
    projects_led?: number;
    points_by_dimension?: Record<string, number>;
  };
  projects: Array<{
    title: string;
    slug: string;
    summary: string;
    status: string;
    discipline_areas: string[];
    role: string | null;
    was_lead: boolean;
    joined_at: string;
    left_at: string | null;
    days_served: number;
    is_open_source: boolean;
    repository_url: string;
    confirmed_contributions: number;
    points: number;
  }>;
  contributions: Array<{
    sequence: number;
    project: string;
    dimension: string;
    description: string;
    occurred_on: string;
    evidence_url: string;
    ai_assistance: string;
    skills: string[];
    confirmed_by: Array<{ name: string; capacity: string }>;
    points: number;
    entry_hash: string;
  }>;
  skills: Array<{ skill: string; self_rating: string; evidence_count: number }>;
  badges: Array<{ name: string; criteria: string; awarded_at: string }>;
  certificates: Array<{
    kind: string;
    code: string;
    issued_at: string;
    verify_at: string;
  }>;
  ledger: { entry_count: number; head_hash: string | null; chain_note: string };
};


/** What a steward sees on the administration console's summary row. */
export type AdminOverview = {
  members: {
    total: number;
    active: number;
    pending: number;
    suspended: number;
    alumni: number;
    joined_this_week: number;
    never_signed_in: number;
  };
  invitations: Record<string, number>;
  roles: Record<string, number>;
  projects: Record<string, number>;
  evidence: { ledger_entries: number; awaiting_confirmation: number };
  email: { sent_this_week: number; failed_this_week: number };
};

/** The preview shown on the accept-invitation screen. */
export type InvitationPreview = {
  email: string;
  full_name: string;
  kind: string;
  role_label: string;
  message: string;
  invited_by_name: string;
  expires_at: string;
};

export const ROLE_LABELS: Record<string, string> = {
  mentor: "Mentor",
  community_lead: "Community lead",
  faculty_advisor: "Faculty advisor",
  moderator: "Moderator",
  platform_maintainer: "Platform maintainer",
};

/**
 * What each role actually lets somebody do, in plain words.
 *
 * Shown wherever a role is granted. A steward choosing from a dropdown of
 * bare labels is a steward guessing, and over-granting is how access control
 * quietly stops meaning anything.
 */
export const ROLE_DESCRIPTIONS: Record<string, string> = {
  mentor:
    "Reviews proposals, and countersigns contributions on projects they mentor.",
  community_lead:
    "Moderates a discipline area, and can countersign a project lead's own contributions.",
  faculty_advisor:
    "Handles escalated conduct matters, grants roles, and administers accounts.",
  moderator: "Reviews reports and removes content that breaches the code of conduct.",
  platform_maintainer:
    "Administers the platform itself: invitations, accounts and roles.",
};
