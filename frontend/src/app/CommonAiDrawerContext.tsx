import {
  createContext,
  useEffect,
  useContext,
  useState,
  type ReactNode,
} from "react";
import CommonAiDrawer, {
  type AiPanelContext,
} from "../components/CommonAiDrawer";
import {
  bootstrapDemoSession,
  getDemoSessionStatus,
} from "../api/demoSession";
import { BackendHttpError } from "../api/backendHttp";

export type SessionState = "ready" | "loading" | "needs-new" | "error";
let pendingBootstrap: ReturnType<typeof bootstrapDemoSession> | null = null;
function bootstrapOnce() {
  if (!pendingBootstrap) {
    pendingBootstrap = getDemoSessionStatus()
      .catch((error: unknown) => {
        if (
          error instanceof BackendHttpError &&
          (error.status === 401 || error.status === 404)
        ) {
          return bootstrapDemoSession();
        }

        throw error;
      })
      .finally(() => {
        pendingBootstrap = null;
      });
  }

  return pendingBootstrap;
}

type AiDrawerState =
  | { status: "CLOSED"; context: AiPanelContext | null }
  | {
      status: "IDLE_CONTEXT";
      context: AiPanelContext | null;
    };

    const AI_DRAWER_STORAGE_KEY = "commerce-ai-drawer-state";

function readStoredDrawerState(): AiDrawerState {
  try {
    const raw = sessionStorage.getItem(AI_DRAWER_STORAGE_KEY);
    if (!raw) {
      return { status: "CLOSED", context: null };
    }

    const value: unknown = JSON.parse(raw);

    if (
      typeof value !== "object" ||
      value === null ||
      !("status" in value) ||
      !("context" in value) ||
      (value.status !== "CLOSED" && value.status !== "IDLE_CONTEXT")
    ) {
      return { status: "CLOSED", context: null };
    }

    return {
      status: value.status,
      context: value.context as AiPanelContext | null,
    };
  } catch {
    return { status: "CLOSED", context: null };
  }
}

export type AiDrawerActions = {
  openAiDrawer: (context: AiPanelContext | null) => void;
  closeAiDrawer: () => void;
  toggleAiDrawer: () => void;
  isAiDrawerOpen: boolean;
  sessionState: SessionState;
};

const AiDrawerActionsContext =
  createContext<AiDrawerActions | null>(null);

export function useCommonAiDrawer(): AiDrawerActions {
  const actions = useContext(AiDrawerActionsContext);

  if (!actions) {
    throw new Error("Common AI Drawer host is missing");
  }

  return actions;
}

export function useOptionalCommonAiDrawer(): AiDrawerActions | null {
  return useContext(AiDrawerActionsContext);
}

export function CommonAiDrawerHost({
  children,
  sessionRequired = false,
  currentPage = "/",
}: {
  children: ReactNode;
  sessionRequired?: boolean;
  currentPage?: string;
}) {
  const [sessionState, setSessionState] = useState<SessionState>(sessionRequired ? "loading" : "ready");
  const [sessionGeneration, setSessionGeneration] = useState(0);
  useEffect(() => {
    if (!sessionRequired) return;
    let active = true;
    void bootstrapOnce().then((session) => {
      if (!active) return;
      setSessionState("ready");
      const remaining = Date.parse(session.expiresAt) - Date.now();
      const timer = window.setTimeout(() => setSessionState("needs-new"), Math.max(0, Math.min(remaining, 2_147_483_647)));
      // A new visit gets a new host; timeout cleanup is handled below.
      expiryTimer = timer;
    }).catch(() => { if (active) setSessionState("error"); });
    let expiryTimer: number | undefined;
    return () => { active = false; if (expiryTimer !== undefined) window.clearTimeout(expiryTimer); };
  }, [sessionRequired, sessionGeneration]);

  function startNewSession() {
    try {
      sessionStorage.removeItem("commerce-ai-active-conversation");
    } catch {
      // 저장소를 사용할 수 없는 환경은 무시
    }
    setState({ status: "CLOSED", context: null });
    setSessionState("loading");
    setSessionGeneration((value) => value + 1);
  }

  const [state, setState] =
    useState<AiDrawerState>(readStoredDrawerState);

    useEffect(() => {
  try {
    sessionStorage.setItem(
      AI_DRAWER_STORAGE_KEY,
      JSON.stringify(state),
    );
  } catch {
    // 브라우저 저장소를 사용할 수 없어도 패널은 계속 동작
  }
}, [state]);

  const openAiDrawer = (context: AiPanelContext | null) =>
    setState((current) => ({
      status: "IDLE_CONTEXT",
      context: context ?? current.context,
    }));

  const closeAiDrawer = () => {
    setState((current) => ({ status: "CLOSED", context: current.context }));
  };

  const toggleAiDrawer = () => {
    setState((current) => ({
      status:
        current.status === "CLOSED" ? "IDLE_CONTEXT" : "CLOSED",
      context: current.context,
    }));
  };
  return (
    <AiDrawerActionsContext.Provider
      value={{
        openAiDrawer,
        closeAiDrawer,
        toggleAiDrawer,
        isAiDrawerOpen: state.status === "IDLE_CONTEXT",
        sessionState,
      }}
    >
      {children}

      <CommonAiDrawer
        open={state.status === "IDLE_CONTEXT"}
        context={state.context}
        currentPage={currentPage}
        onClose={closeAiDrawer}
        sessionState={sessionState}
        onStartNewSession={startNewSession}
        onSessionExpired={() => setSessionState("needs-new")}
        publicMode={sessionRequired}
      />
    </AiDrawerActionsContext.Provider>
  );
}
