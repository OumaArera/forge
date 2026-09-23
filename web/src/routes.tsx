import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Suspense, lazy, type ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/features/auth/useAuth";
import { Loading } from "@/components/ui";

/*
 * Routes are split per page.
 *
 * Most members will open FORGE on a phone, on a connection they are paying
 * for by the megabyte. Shipping the proposal form, the ledger and the whole
 * community module to somebody who only wanted to check their dashboard is
 * exactly the cost this platform said it would not impose.
 *
 * Sign-in and the dashboard are eager: they are what almost everybody loads
 * first, and a spinner on the very first screen reads as a broken site.
 */
import { Dashboard } from "@/pages/Dashboard";
import { SignIn } from "@/pages/SignIn";

const AcceptInvitation = lazy(() => import("@/pages/AcceptInvitation").then(m => ({ default: m.AcceptInvitation })));
const Achievements = lazy(() => import("@/pages/Achievements").then(m => ({ default: m.Achievements })));
const AdminConsole = lazy(() => import("@/pages/AdminConsole").then(m => ({ default: m.AdminConsole })));
const ChangePassword = lazy(() => import("@/pages/ChangePassword").then(m => ({ default: m.ChangePassword })));
const Community = lazy(() => import("@/pages/Community").then(m => ({ default: m.Community })));
const Contributions = lazy(() => import("@/pages/Contributions").then(m => ({ default: m.Contributions })));
const Discover = lazy(() => import("@/pages/Discover").then(m => ({ default: m.Discover })));
const Landing = lazy(() => import("@/pages/Landing").then(m => ({ default: m.Landing })));
const Leaderboards = lazy(() => import("@/pages/Leaderboards").then(m => ({ default: m.Leaderboards })));
const Ledger = lazy(() => import("@/pages/Ledger").then(m => ({ default: m.Ledger })));
const Mentors = lazy(() => import("@/pages/Mentors").then(m => ({ default: m.Mentors })));
const MyProjects = lazy(() => import("@/pages/MyProjects").then(m => ({ default: m.MyProjects })));
const NewProject = lazy(() => import("@/pages/NewProject").then(m => ({ default: m.NewProject })));
const NotFound = lazy(() => import("@/pages/NotFound").then(m => ({ default: m.NotFound })));
const Notifications = lazy(() => import("@/pages/Notifications").then(m => ({ default: m.Notifications })));
const Portfolio = lazy(() => import("@/pages/Portfolio").then(m => ({ default: m.Portfolio })));
const ProjectDetail = lazy(() => import("@/pages/ProjectDetail").then(m => ({ default: m.ProjectDetail })));
const Register = lazy(() => import("@/pages/Register").then(m => ({ default: m.Register })));
const ResendVerification = lazy(() => import("@/pages/ResendVerification").then(m => ({ default: m.ResendVerification })));
const ReviewQueue = lazy(() => import("@/pages/ReviewQueue").then(m => ({ default: m.ReviewQueue })));
const SignInHelp = lazy(() => import("@/pages/SignInHelp").then(m => ({ default: m.SignInHelp })));
const Settings = lazy(() => import("@/pages/Settings").then(m => ({ default: m.Settings })));
const Showcase = lazy(() => import("@/pages/Showcase").then(m => ({ default: m.Showcase })));
const Tasks = lazy(() => import("@/pages/Tasks").then(m => ({ default: m.Tasks })));
const ThreadDetail = lazy(() => import("@/pages/ThreadDetail").then(m => ({ default: m.ThreadDetail })));
const VerifyCertificate = lazy(() => import("@/pages/VerifyCertificate").then(m => ({ default: m.VerifyCertificate })));
const VerifyEmail = lazy(() => import("@/pages/VerifyEmail").then(m => ({ default: m.VerifyEmail })));

function RequireAuth({ children }: { children: ReactNode }) {
  const { status, member } = useAuth();
  const location = useLocation();

  if (status === "loading") return <Loading label="Signing you in" />;
  if (status === "anonymous")
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;

  // A password that arrived by email is sitting in an inbox somewhere. The
  // member replaces it before doing anything else.
  if (member?.must_change_password && location.pathname !== "/choose-password")
    return <Navigate to="/choose-password" replace />;

  return <>{children}</>;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
    <Routes>
      {/* Open to anyone, with or without an account. A portfolio and the
          ledger that backs it are no use if only members can see them. */}
      {/* The landing page is the front door and stays reachable when signed
          in — it just swaps its calls to action for a link back to the app. */}
      <Route path="/" element={<Landing />} />
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/help/signing-in" element={<SignInHelp />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify" element={<VerifyEmail />} />
      <Route path="/resend-verification" element={<ResendVerification />} />
      <Route path="/accept-invitation" element={<AcceptInvitation />} />
      <Route path="/p/:slug" element={<PublicFrame><Portfolio /></PublicFrame>} />
      <Route
        path="/verify-certificate"
        element={<PublicFrame><VerifyCertificate /></PublicFrame>}
      />
      <Route
        path="/verify-certificate/:code"
        element={<PublicFrame><VerifyCertificate /></PublicFrame>}
      />

      {/*
        A member signed in with a generated password is held here until they
        choose their own. Outside the shell on purpose: there is nothing else
        for them to do until it is done, and a sidebar full of links they
        cannot yet use is just noise.
      */}
      <Route
        path="/choose-password"
        element={
          <RequireAuth>
            <ChangePassword />
          </RequireAuth>
        }
      />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="discover" element={<Discover />} />
        <Route path="projects" element={<MyProjects />} />
        <Route path="projects/new" element={<NewProject />} />
        <Route path="projects/:slug" element={<ProjectDetail />} />
        <Route path="review-queue" element={<ReviewQueue />} />
        <Route path="contributions" element={<Contributions />} />
        <Route path="ledger" element={<Ledger />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="community" element={<Community />} />
        <Route path="community/:id" element={<ThreadDetail />} />
        <Route path="mentors" element={<Mentors />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="achievements" element={<Achievements />} />
        <Route path="leaderboards" element={<Leaderboards />} />
        <Route path="showcase" element={<Showcase />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="settings" element={<Settings />} />
        <Route path="administration" element={<AdminConsole />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </Suspense>
  );
}

/** A minimal chrome for pages an outside reader lands on directly. */
function PublicFrame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-page">
      <header className="h-16 border-b border-line bg-card">
        <div className="max-w-5xl mx-auto h-full px-4 sm:px-6 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2.5">
            <img src="/forge-logo.png" srcSet="/forge-logo.png 1x, /forge-logo@2x.png 2x" alt="" className="size-8" />
            <span className="font-bold text-strong tracking-tight">FORGE</span>
          </a>
          <span className="text-xs text-muted hidden sm:block">
            The Open University of Kenya
          </span>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">{children}</main>
    </div>
  );
}
