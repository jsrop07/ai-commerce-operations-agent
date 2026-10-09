import { useCommonAiDrawer } from "../app/CommonAiDrawerContext";

export default function FloatingAiLauncher() {
  const { openAiDrawer, isAiDrawerOpen } = useCommonAiDrawer();

  if (isAiDrawerOpen) return null;

  return (
    <button
      type="button"
      className="floating-ai-launcher"
      aria-label="운영 AI 열기"
      onClick={() => openAiDrawer(null)}
    >
      운영 AI
    </button>
  );
}