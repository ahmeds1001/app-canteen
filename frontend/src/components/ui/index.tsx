import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";
import "./ui.css";

type Variant = "primary" | "accent" | "ghost" | "danger";

export function Button({
  variant = "primary",
  block,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; block?: boolean }) {
  return <button className={`btn btn--${variant} ${block ? "btn--block" : ""} ${className}`} {...props} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Field({
  label,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} aria-invalid={Boolean(error)} {...props} />
      {error && <span className="field__error">{error}</span>}
    </div>
  );
}

export function SelectField({
  label,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} {...props}>
        {children}
      </select>
    </div>
  );
}

export function TextAreaField({ label, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <textarea id={id} rows={3} {...props} />
    </div>
  );
}

/** Modal built on the native <dialog> (focus trap, Esc to close). Rendered only while open. */
export function Dialog({ title, onClose, children, wide }: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) {
      dialog.showModal();
      // showModal() focuses the close button; start on the first field instead.
      dialog.querySelector<HTMLElement>("input:not([type=file]), select, textarea")?.focus();
    }
  }, []);
  return (
    <dialog ref={ref} className={`dialog ${wide ? "dialog--wide" : ""}`} onClose={onClose} aria-label={title}>
      <div className="dialog__head">
        <h2>{title}</h2>
        <button type="button" className="dialog__close" onClick={onClose} aria-label={t("common.close")}>
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}

export function Alert({ kind = "error", children }: { kind?: "error" | "success" | "info"; children: ReactNode }) {
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`alert alert--${kind}`}>
      {children}
    </div>
  );
}

export function Badge({ tone, children }: { tone?: "green" | "orange" | "red"; children: ReactNode }) {
  return <span className={`badge ${tone ? `badge--${tone}` : ""}`}>{children}</span>;
}

export function Logo({ size = 120 }: { size?: number }) {
  return <img className="logo" src="/logo.png" alt="OVAGRI Groupe" width={size} height={size} />;
}
