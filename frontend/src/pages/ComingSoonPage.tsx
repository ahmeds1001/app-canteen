import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui";

/** Placeholder for screens listed in docs/plans/backlog.md (built in later sprints). */
export default function ComingSoonPage({ title, refs }: { title: string; refs: string }) {
  const { t } = useTranslation();
  return (
    <div className="container">
      <Card className="stack">
        <h1>{t(title)}</h1>
        <p className="muted">{t("soon.help", { refs })}</p>
      </Card>
    </div>
  );
}
