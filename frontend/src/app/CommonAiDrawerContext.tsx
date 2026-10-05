import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import CommonAiDrawer, {
  type AiPanelContext,
} from "../components/CommonAiDrawer";
import { contextIdentity } from "../api/conversations";

type AiDrawerState =
  | { status: "CLOSED"; context: AiPanelContext | null }
  | {
      status: "IDLE_CONTEXT";
      context: AiPanelContext;
    };

export type AiDrawerActions = {
  openAiDrawer: (context: AiPanelContext) => void;
  closeAiDrawer: () => void;
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
}: {
  children: ReactNode;
}) {
  const [state, setState] =
    useState<AiDrawerState>({
      status: "CLOSED",
      context: null,
    });

  const openAiDrawer = (
    context: AiPanelContext,
  ) => {
    setState({
      status: "IDLE_CONTEXT",
      context,
    });
  };

  const closeAiDrawer = () => {
    setState((current) => ({ status: "CLOSED", context: current.context }));
  };

  return (
    <AiDrawerActionsContext.Provider
      value={{
        openAiDrawer,
        closeAiDrawer,
      }}
    >
      {children}

      <CommonAiDrawer
        key={state.context ? contextIdentity(state.context) : "closed"}
        open={state.status === "IDLE_CONTEXT"}
        context={state.context}
        onClose={closeAiDrawer}
      />
    </AiDrawerActionsContext.Provider>
  );
}
