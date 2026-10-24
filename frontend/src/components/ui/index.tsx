import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";
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
