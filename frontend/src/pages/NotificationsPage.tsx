import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { notificationApi } from "@/api/endpoints";
import type { AppNotification } from "@/api/types";
import { Alert, Button, Card } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { usePush } from "@/hooks/usePush";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { formatCompanyDateTime } from "@/utils/dates";
import "./notifications.css";

const EATING_ROLES = ["employee", "hr", "chef", "management"];

/** Spec §8: the user's notifications, phone push on/off, and the evening reminder switch. */
export default function NotificationsPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: notificationApi.list, refetchInterval: 60_000 });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const readOne = useMutation({ mutationFn: notificationApi.read, onSuccess: refresh });
  const readAll = useMutation({ mutationFn: notificationApi.readAll, onSuccess: refresh });
  const evening = useMutation({
    mutationFn: notificationApi.setEveningReminder,
    onSuccess: refresh,
    onError: (e) => setError(toMessage(e)),
  });

  const open = (note: AppNotification) => {
    if (!note.read_at) readOne.mutate(note.id);
    if (note.link) navigate(note.link);
  };

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("notifications.title")}</h1>
        {(data?.unread ?? 0) > 0 && (
          <Button className="btn--sm" variant="ghost" onClick={() => readAll.mutate()}>
            {t("notifications.readAll")}
          </Button>
        )}
      </div>
      {error && <Alert>{error}</Alert>}

      <Card className="stack notif-settings">
        <PushSetting onError={(e) => setError(toMessage(e))} />
        {user && EATING_ROLES.includes(user.role) && data && (
          <label className="notif-switch">
            <input
              type="checkbox"
              checked={data.evening_reminder}
              disabled={evening.isPending}
              onChange={(e) => evening.mutate(e.target.checked)}
            />
            <span>
              <strong>{t("notifications.eveningTitle")}</strong>
              <span className="muted">{t("notifications.eveningHelp")}</span>
            </span>
          </label>
        )}
      </Card>

      {data?.results.length === 0 && <p className="muted">{t("notifications.empty")}</p>}
      <ul className="notif-list">
        {data?.results.map((note) => (
          <li key={note.id}>
            <button type="button" className={`notif ${note.read_at ? "" : "notif--unread"}`} onClick={() => open(note)}>
              <span className="notif__title">{note.title}</span>
              <span className="notif__body">{note.body}</span>
              <span className="notif__time">{formatCompanyDateTime(note.created_at, i18n.language)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PushSetting({ onError }: { onError: (e: unknown) => void }) {
  const { t } = useTranslation();
  const { state, busy, enable, disable } = usePush();

  return (
    <div className="notif-push">
      <div>
        <strong>{t("notifications.pushTitle")}</strong>
        <p className="muted">{t(`notifications.push.${state}`)}</p>
      </div>
      {state === "off" && (
        <Button className="btn--sm" disabled={busy} onClick={() => enable().catch(onError)}>
          {t("notifications.enable")}
        </Button>
      )}
      {state === "on" && (
        <Button className="btn--sm" variant="ghost" disabled={busy} onClick={() => disable().catch(onError)}>
          {t("notifications.disable")}
        </Button>
      )}
    </div>
  );
}
