import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import CommonAiDrawer, {
  type AiPanelContext,
} from "../components/CommonAiDrawer";

type AiDrawerState =
  | { status: "CLOSED" }
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
    setState({
      status: "CLOSED",
    });
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
        open={state.status === "IDLE_CONTEXT"}
        context={
          state.status === "IDLE_CONTEXT"
            ? state.context
            : null
        }
        onClose={closeAiDrawer}
      />
    </AiDrawerActionsContext.Provider>
  );
}