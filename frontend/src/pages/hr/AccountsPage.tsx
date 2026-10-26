import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { userAdminApi } from "@/api/endpoints";
import type { AccountStatus, ManagedUser, Role } from "@/api/types";
import { Alert, Badge, Button, Card, Dialog, Field } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useConfirm } from "@/hooks/useConfirm";
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

const ROLES: Role[] = ["employee", "hr", "chef", "management", "scanner", "admin"];

/** FR-04 to FR-06, FR-40: HR approves registrations (entering the matricule) and manages accounts. */
export default function AccountsPage() {
  const { t, i18n } = useTranslation();
  const { user: me } = useAuth();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(TABS[0]);
  const [q, setQ] = useState("");
  const [rejecting, setRejecting] = useState<ManagedUser | null>(null);
  const [numbering, setNumbering] = useState<ManagedUser | null>(null);
  const [tempPassword, setTempPassword] = useState<{ user: ManagedUser; password: string; hours: number } | null>(null);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  const users = useQuery({
    queryKey: ["users", tab.key, q],
    queryFn: () => userAdminApi.list({ status: tab.status, q }),
    placeholderData: keepPreviousData,
  });
  const list = users.data ?? [];

  const done = (text?: string) => {
    setMessage(text ? { kind: "success", text } : null);
    queryClient.invalidateQueries({ queryKey: ["users"] });
  };
  const fail = (e: unknown) => setMessage({ kind: "error", text: toMessage(e) });

  const changeStatus = useMutation({
    mutationFn: ({ id, transition }: { id: number; transition: Transition }) => userAdminApi.changeStatus(id, transition),
    onSuccess: (u) => done(t("accounts.statusChanged", { name: u.full_name, status: t(`accounts.status.${u.status}`) })),
    onError: fail,
  });
  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) => userAdminApi.setRole(id, role),
    onSuccess: (u) => done(t("accounts.roleChanged", { name: u.full_name, role: t(`accounts.roles.${u.role}`) })),
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

  const confirm = useConfirm();
  const confirmThen = confirm.ask;

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("accounts.title")}</h1>
      </div>
      <p className="muted">{t("accounts.help")}</p>

      <div className="tabs" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={tab.key === item.key}
            className={`tab ${tab.key === item.key ? "tab--active" : ""}`}
            onClick={() => { setTab(item); setMessage(null); }}
          >
            {t(`accounts.tabs.${item.key}`)}
          </button>
        ))}
      </div>

      <div className="toolbar">
        <Field label={t("accounts.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}

      {users.data && list.length === 0 && <p className="muted">{t(`accounts.empty.${tab.key}`)}</p>}
      <div className="accounts">
        {list.map((user) => (
          <Card key={user.id} className="account">
            <div className="account__main">
              <div className="account__who">
                <strong>{user.full_name}</strong>
                <span className="muted">{user.work_email}</span>
                <span className="account__meta">
                  {user.employee_number ? t("accounts.number", { number: user.employee_number }) : t("accounts.noNumber")}
                  {user.department && ` · ${user.department}`}
                  {` · ${t(`accounts.roles.${user.role}`)}`}
                  {` · ${t("accounts.since", { date: formatShortDate(user.created_at.slice(0, 10), i18n.language) })}`}
                </span>
              </div>
              <div className="account__badges">
                <Badge tone={STATUS_TONE[user.status]}>{t(`accounts.status.${user.status}`)}</Badge>
              </div>
            </div>
            {user.id !== me?.id && <div className="actions">
              {me?.role === "admin" && (
                <label className="account__role">
                  <span>{t("accounts.roleLabel")}</span>
                  <select
                    value={user.role}
                    disabled={setRole.isPending}
                    onChange={(e) => {
                      const role = e.target.value as Role;
                      const ask = role === "admin" ? "accounts.confirm.makeAdmin" : "accounts.confirm.role";
                      confirmThen(t(ask, { name: user.full_name, role: t(`accounts.roles.${role}`) }),
                        () => setRole.mutate({ id: user.id, role }));
                    }}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{t(`accounts.roles.${r}`)}</option>
                    ))}
                  </select>
                </label>
              )}
              {user.status === "pending_hr" && (
                <>
                  <Button className="btn--sm" onClick={() => setNumbering(user)}>
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
                  <Button className="btn--sm" variant="ghost" onClick={() => setNumbering(user)}>
                    {t(user.employee_number ? "accounts.editNumber" : "accounts.addNumber")}
                  </Button>
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

      {confirm.dialog}
      {rejecting && (
        <RejectDialog user={rejecting} onClose={() => setRejecting(null)} onDone={() => done(t("accounts.rejected", { name: rejecting.full_name }))} />
      )}
      {numbering && (
        <EmployeeNumberDialog user={numbering} onClose={() => setNumbering(null)} onDone={(text) => done(text)} />
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

/** FR-04: HR types the employee's matricule to approve a pending account, or corrects it on an approved one. */
function EmployeeNumberDialog({ user, onClose, onDone }: {
  user: ManagedUser;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const approving = user.status === "pending_hr";
  const [number, setNumber] = useState(user.employee_number ?? "");
  const [error, setError] = useState("");
  const save = useMutation({
    mutationFn: () => (approving ? userAdminApi.approve : userAdminApi.setEmployeeNumber)(user.id, number.trim()),
    onSuccess: (u) => {
      onDone(approving
        ? t("accounts.approved", { name: u.full_name })
        : t("accounts.numberChanged", { name: u.full_name, number: u.employee_number }));
      onClose();
    },
    onError: (e) => setError(toMessage(e)),
  });

  return (
    <Dialog title={t(approving ? "accounts.approveTitle" : "accounts.numberTitle", { name: user.full_name })} onClose={onClose}>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        {approving && <p className="muted">{t("accounts.approveHelp", { email: user.work_email })}</p>}
        {error && <Alert>{error}</Alert>}
        <Field label={t("accounts.numberLabel")} value={number} maxLength={40} onChange={(e) => setNumber(e.target.value)}
          required autoFocus />
        <div className="actions">
          <Button type="submit" disabled={save.isPending || !number.trim()}>
            {t(approving ? "accounts.approve" : "common.save")}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
        </div>
      </form>
    </Dialog>
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
