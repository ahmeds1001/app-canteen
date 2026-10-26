import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Button, Dialog } from "@/components/ui";

type Pending = { text: string; action: () => void };

/** In-app confirmation. Replaces window.confirm, which some browsers silently answer "no" to
 *  (embedded browsers, "block dialogs from this page", some phones): the action then never ran. */
export function useConfirm(): { ask: (text: string, action: () => void) => void; dialog: ReactNode } {
  const { t } = useTranslation();
  const [pending, setPending] = useState<Pending | null>(null);
  const close = () => setPending(null);

  const dialog = pending && (
    <Dialog title={t("common.confirmTitle")} onClose={close}>
      <div className="stack">
        <p>{pending.text}</p>
        <div className="actions">
          <Button onClick={() => { pending.action(); close(); }}>{t("common.confirm")}</Button>
          <Button variant="ghost" onClick={close}>{t("common.cancel")}</Button>
        </div>
      </div>
    </Dialog>
  );

  return { ask: (text, action) => setPending({ text, action }), dialog };
}
