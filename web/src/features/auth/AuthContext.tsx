import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, tokens } from "@/api/client";
import type { Me } from "@/api/types";

type AuthState = {
  member: Me | null;
  status: "loading" | "authenticated" | "anonymous";
  signIn: (email: string, password: string) => Promise<Me>;
  signOut: () => void;
  refreshMember: () => Promise<void>;
  /** Standing roles the member holds, e.g. "mentor", "faculty_advisor". */
  roles: string[];
  can: (capability: Capability) => boolean;
};

/**
 * Client-side capabilities.
 *
 * These decide what to *show*. They are a courtesy, not a control: the server
 * re-checks every one of them, and a member who forges a role in devtools gets
 * a 403 rather than access. Hiding a button the member cannot use is worth
 * doing anyway — an interface full of actions that fail is worse than one that
 * only offers what will work.
 */
export type Capability = "review_proposals" | "moderate" | "mentor" | "grant_roles";

const CAPABILITY_ROLES: Record<Capability, string[]> = {
  review_proposals: ["mentor", "community_lead", "faculty_advisor"],
  moderate: ["moderator", "community_lead", "faculty_advisor"],
  mentor: ["mentor", "faculty_advisor"],
  grant_roles: ["faculty_advisor", "platform_maintainer"],
};

export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [member, setMember] = useState<Me | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const queryClient = useQueryClient();

  const loadMember = useCallback(async () => {
    if (!tokens.access) {
      setStatus("anonymous");
      return;
    }
    try {
      const { data } = await api.get<Me>("/accounts/me/");
      setMember(data);
      setStatus("authenticated");
    } catch {
      tokens.clear();
      setMember(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    void loadMember();
  }, [loadMember]);

  const signOut = useCallback(() => {
    tokens.clear();
    setMember(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  // The client dispatches this when a refresh fails, from deep inside an
  // interceptor that has no access to React state.
  useEffect(() => {
    const handler = () => signOut();
    window.addEventListener("forge:signed-out", handler);
    return () => window.removeEventListener("forge:signed-out", handler);
  }, [signOut]);

  const signIn = useCallback(async (email: string, password: string) => {
    const { data } = await api.post<{ access: string; refresh: string; member: Me }>(
      "/accounts/token/",
      { email, password },
    );
    tokens.set(data.access, data.refresh);
    setMember(data.member);
    setStatus("authenticated");
    return data.member;
  }, []);

  const roles = useMemo(() => member?.roles ?? [], [member]);

  const can = useCallback(
    (capability: Capability) =>
      CAPABILITY_ROLES[capability].some((role) => roles.includes(role)),
    [roles],
  );

  const value = useMemo(
    () => ({ member, status, signIn, signOut, refreshMember: loadMember, roles, can }),
    [member, status, signIn, signOut, loadMember, roles, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
