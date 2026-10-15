import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type Show = (text: string, onClick?: () => void) => void;
interface Item { id: number; text: string; onClick?: () => void }

const TOAST_MS = 6000;
const ToastContext = createContext<Show>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(0);
  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);

  const show = useCallback<Show>((text, onClick) => {
    const id = next.current++;
    setItems((all) => [...all, { id, text, onClick }]);
    setTimeout(() => dismiss(id), TOAST_MS);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <button key={t.id} type="button" className="toast" onClick={() => { t.onClick?.(); dismiss(t.id); }}>
            {t.text}
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
