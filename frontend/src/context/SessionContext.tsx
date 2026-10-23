import React, { createContext, useContext } from "react";
import type { SessionUser } from "../services/api";

const SessionContext = createContext<SessionUser | null>(null);
export const SessionProvider: React.FC<{ session: SessionUser; children: React.ReactNode }> = ({ session, children }) =>
  <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
export const useSession = () => useContext(SessionContext);
