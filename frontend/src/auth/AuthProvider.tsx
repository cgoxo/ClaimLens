import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, createClient, type Client } from "../api/client";

type Status = "loading" | "signedOut" | "signedIn" | "forbidden";
type Mode = "dev" | "firebase";

interface AuthState {
  status: Status;
  email: string | null;
  error: string | null;
  mode: Mode;
  signInGoogle(): Promise<void>;
  signInDev(email: string): void;
  signOut(): Promise<void>;
  client: Client;
}

const DEV_KEY = "claimlens.devUser";
export const AuthContext = createContext<AuthState | null>(null);
type FirebaseApi = typeof import("./firebase")["firebase"];

export function AuthProvider({ children, mode = (import.meta.env.VITE_AUTH_MODE as Mode) || "dev" }: {
  children: ReactNode;
  mode?: Mode;
}) {
  const [status, setStatus] = useState<Status>("loading");
  const [email, setEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const emailRef = useRef<string | null>(null);
  const fb = useRef<FirebaseApi | null>(null);

  const reset = useCallback(() => {
    emailRef.current = null;
    localStorage.removeItem(DEV_KEY);
    setEmail(null);
    setStatus("signedOut");
  }, []);

  const client = useMemo(
    () =>
      createClient(
        async (): Promise<Record<string, string>> => {
          if (mode === "dev") return emailRef.current ? { "X-Dev-User": emailRef.current } : {};
          const token = await fb.current?.token();
          return token ? { Authorization: `Bearer ${token}` } : {};
        },
        () => {
          reset();
          void fb.current?.signOut();
        },
      ),
    [mode, reset],
  );

  const verify = useCallback(
    async (who: string) => {
      emailRef.current = who;
      setEmail(who);
      try {
        await client.me();
        setStatus("signedIn");
      } catch (e) {
        if (e instanceof ApiError && e.status === 403) setStatus("forbidden");
        else if (!(e instanceof ApiError && e.status === 401)) setStatus("signedOut");
      }
    },
    [client],
  );

  useEffect(() => {
    if (mode === "dev") {
      const stored = localStorage.getItem(DEV_KEY);
      if (stored) void verify(stored);
      else setStatus("signedOut");
      return;
    }
    let unsubscribe = () => {};
    import("./firebase").then(
      ({ firebase }) => {
        fb.current = firebase;
        unsubscribe = firebase.onUser((user) => (user?.email ? void verify(user.email) : reset()));
      },
      () => {
        // e.g. an old page asking for a bundle that a newer deploy replaced
        setError("Couldn't load sign-in. Reload the page.");
        setStatus("signedOut");
      },
    );
    return () => unsubscribe();
  }, [mode, verify, reset]);

  const value: AuthState = {
    status,
    email,
    error,
    mode,
    client,
    signInDev(who) {
      localStorage.setItem(DEV_KEY, who.trim().toLowerCase());
      void verify(who.trim().toLowerCase());
    },
    async signInGoogle() {
      await fb.current?.signIn();
    },
    async signOut() {
      client.releaseImages();
      reset();
      await fb.current?.signOut();
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
