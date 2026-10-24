import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { userAdminApi } from "@/api/endpoints";
import type { AccountStatus, ManagedUser } from "@/api/types";
import { Alert, Badge, Button, Card, Dialog, Field } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { formatShortDate } from "@/utils/dates";
import "./hr.css";

const TABS: { key: string; status?: AccountStatus }[] = [
  { key: "pending", status: "pending_hr" },
  { key: "active", status: "active" },
  { key: "suspended", status: "suspended" },
  { key: "all" },
];

const STATUS_TONE: Partial<Record<AccountStatus, "green" | "orange" | "red">> = {
  pending_hr: "orange", active: "green", rejected: "red", suspended: "red", deactivated: "red",
};

type Transition = "suspend" | "reactivate" | "deactivate";

/** FR-04 to FR-06, FR-37, FR-40: HR approves registrations and manages accounts. */
export default function AccountsPage() {
  const { t, i18n } = useTranslation();
  const { user: me } = useAuth();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(TABS[0]);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [rejecting, setRejecting] = useState<ManagedUser | null>(null);
  const [tempPassword, setTempPassword] = useState<{ user: ManagedUser; password: string; hours: number } | null>(null);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const users = useQuery({
    queryKey: ["users", tab.key, q],
    queryFn: () => userAdminApi.list({ status: tab.status, q }),
    placeholderData: keepPreviousData,
  });
  const list = users.data ?? [];
  const pendingView = tab.key === "pending";

  const done = (text?: string) => {
    setMessage(text ? { kind: "success", text } : null);
    setSelected([]);
    queryClient.invalidateQueries({ queryKey: ["users"] });
  };
  const fail = (e: unknown) => setMessage({ kind: "error", text: toMessage(e) });

  const approve = useMutation({
    mutationFn: userAdminApi.approve,
    onSuccess: (u) => done(t("accounts.approved", { name: u.full_name })),
    onError: fail,
  });
  const bulkApprove = useMutation({
    mutationFn: userAdminApi.bulkApprove,
    onSuccess: (list) => done(t("accounts.bulkApproved", { count: list.length })),
    onError: fail,
  });
  const changeStatus = useMutation({
    mutationFn: ({ id, transition }: { id: number; transition: Transition }) => userAdminApi.changeStatus(id, transition),
    onSuccess: (u) => done(t("accounts.statusChanged", { name: u.full_name, status: t(`accounts.status.${u.status}`) })),
    onError: fail,
  });
  const resetPassword = useMutation({
    mutationFn: (user: ManagedUser) => userAdminApi.resetPassword(user.id),
    onSuccess: (res, user) => {
      setMessage(null);
      setTempPassword({ user, password: res.temporary_password, hours: res.expires_in_hours });
    },
    onError: fail,
  });
  const importRoster = useMutation({
    mutationFn: userAdminApi.importRoster,
    onSuccess: (res) => done(t("accounts.imported", { count: res.imported })),
    onError: fail,
    onSettled: () => { if (fileInput.current) fileInput.current.value = ""; },
  });

  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const onRoster = list.filter((u) => u.on_roster).map((u) => u.id);
  const confirmThen = (text: string, action: () => void) => window.confirm(text) && action();

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("accounts.title")}</h1>
        <div className="actions">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => e.target.files?.[0] && importRoster.mutate(e.target.files[0])}
          />
          <Button variant="ghost" disabled={importRoster.isPending} onClick={() => fileInput.current?.click()}>
            {t("accounts.importRoster")}
          </Button>
        </div>
      </div>
      <p className="muted">{t("accounts.rosterHelp")}</p>

      <div className="tabs" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={tab.key === item.key}
            className={`tab ${tab.key === item.key ? "tab--active" : ""}`}
            onClick={() => { setTab(item); setSelected([]); setMessage(null); }}
          >
            {t(`accounts.tabs.${item.key}`)}
          </button>
        ))}
      </div>

      <div className="toolbar">
        <Field label={t("accounts.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}

      {pendingView && list.length > 0 && (
        <div className="actions">
          <Button variant="ghost" className="btn--sm" disabled={onRoster.length === 0} onClick={() => setSelected(onRoster)}>
            {t("accounts.selectOnRoster", { count: onRoster.length })}
          </Button>
          <Button
            className="btn--sm"
            disabled={selected.length === 0 || bulkApprove.isPending}
            onClick={() => bulkApprove.mutate(selected)}
          >
            {t("accounts.approveSelected", { count: selected.length })}
          </Button>
        </div>
      )}

      {users.data && list.length === 0 && <p className="muted">{t(`accounts.empty.${tab.key}`)}</p>}
      <div className="accounts">
        {list.map((user) => (
          <Card key={user.id} className="account">
            <div className="account__main">
              {pendingView && (
                <input
                  type="checkbox"
                  className="account__check"
                  aria-label={user.full_name}
                  checked={selected.includes(user.id)}
                  onChange={() => toggle(user.id)}
                />
              )}
              <div className="account__who">
                <strong>{user.full_name}</strong>
                <span className="muted">{user.work_email}</span>
                <span className="account__meta">
                  {t("accounts.number", { number: user.employee_number })}
                  {user.department && ` · ${user.department}`}
                  {` · ${t(`accounts.roles.${user.role}`)}`}
                  {` · ${t("accounts.since", { date: formatShortDate(user.created_at.slice(0, 10), i18n.language) })}`}
                </span>
              </div>
              <div className="account__badges">
                <Badge tone={STATUS_TONE[user.status]}>{t(`accounts.status.${user.status}`)}</Badge>
                {user.status === "pending_hr" && (
                  <Badge tone={user.on_roster ? "green" : "orange"}>
                    {t(user.on_roster ? "accounts.onRoster" : "accounts.notOnRoster")}
                  </Badge>
                )}
              </div>
            </div>
            {user.id !== me?.id && <div className="actions">
              {user.status === "pending_hr" && (
                <>
                  <Button className="btn--sm" disabled={approve.isPending} onClick={() => approve.mutate(user.id)}>
                    {t("accounts.approve")}
                  </Button>
                  <Button className="btn--sm" variant="danger" onClick={() => setRejecting(user)}>
                    {t("accounts.reject")}
                  </Button>
                </>
              )}
              {user.status === "active" && (
                <Button
                  className="btn--sm"
                  variant="ghost"
                  onClick={() => confirmThen(t("accounts.confirm.suspend", { name: user.full_name }),
                    () => changeStatus.mutate({ id: user.id, transition: "suspend" }))}
                >
                  {t("accounts.suspend")}
                </Button>
              )}
              {user.status === "suspended" && (
                <Button className="btn--sm" variant="ghost" onClick={() => changeStatus.mutate({ id: user.id, transition: "reactivate" })}>
                  {t("accounts.reactivate")}
                </Button>
              )}
              {(user.status === "active" || user.status === "suspended") && (
                <>
                  <Button
                    className="btn--sm"
                    variant="ghost"
                    disabled={resetPassword.isPending}
                    onClick={() => confirmThen(t("accounts.confirm.reset", { name: user.full_name }),
                      () => resetPassword.mutate(user))}
                  >
                    {t("accounts.resetPassword")}
                  </Button>
                  <Button
                    className="btn--sm"
                    variant="danger"
                    onClick={() => confirmThen(t("accounts.confirm.deactivate", { name: user.full_name }),
                      () => changeStatus.mutate({ id: user.id, transition: "deactivate" }))}
                  >
                    {t("accounts.deactivate")}
                  </Button>
                </>
              )}
            </div>}
          </Card>
        ))}
      </div>

      {rejecting && (
        <RejectDialog user={rejecting} onClose={() => setRejecting(null)} onDone={() => done(t("accounts.rejected", { name: rejecting.full_name }))} />
      )}
      {tempPassword && (
        <Dialog title={t("accounts.tempTitle")} onClose={() => setTempPassword(null)}>
          <div className="stack">
            <p>{t("accounts.tempHelp", { name: tempPassword.user.full_name, hours: tempPassword.hours })}</p>
            <p className="temp-password">{tempPassword.password}</p>
            <Alert kind="info">{t("accounts.tempOnce")}</Alert>
            <Button onClick={() => setTempPassword(null)}>{t("common.done")}</Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

/** FR-04: rejecting requires a reason (sent to the employee by email). */
function RejectDialog({ user, onClose, onDone }: { user: ManagedUser; onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const reject = useMutation({
    mutationFn: () => userAdminApi.reject(user.id, reason),
    onSuccess: () => { onDone(); onClose(); },
    onError: (e) => setError(toMessage(e)),
  });

  return (
    <Dialog title={t("accounts.rejectTitle", { name: user.full_name })} onClose={onClose}>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); reject.mutate(); }}>
        {error && <Alert>{error}</Alert>}
        <Field label={t("accounts.rejectReason")} value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus />
        <div className="actions">
          <Button type="submit" variant="danger" disabled={reject.isPending || !reason.trim()}>{t("accounts.reject")}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
        </div>
      </form>
    </Dialog>
  );
}
