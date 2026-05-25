import { InputHTMLAttributes, forwardRef, useId } from "react";
import { Label } from "../Label/Label";

export type InputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "size"
> & {
  label: string;
  helperText?: string;
  error?: string;
  success?: boolean;
};

const inputBase =
  "w-full h-9 px-3 text-sm text-text bg-surface border border-border rounded-md outline-none placeholder:text-text-muted transition duration-[120ms] enabled:hover:border-text-muted focus:border-2 focus:border-primary focus:px-[calc(var(--space-3)-1px)] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] disabled:bg-surface-muted disabled:text-text-muted disabled:cursor-not-allowed disabled:opacity-70";

const inputError =
  "border-error-text focus:border-error-text focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-error-text)_15%,transparent)]";

const inputSuccess = "border-success-text focus:border-success-text";

const inputWithEndIcon = "pr-7 focus:pr-[calc(var(--space-7)-1px)]";

const endIconBase =
  "absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center justify-center w-4 h-4 pointer-events-none";

function ErrorIcon() {
  return (
    <svg
      className="w-3 h-3 shrink-0"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 5v3.5M8 11v.5" />
    </svg>
  );
}

function EndIconError() {
  return (
    <span className={`${endIconBase} text-error-text`}>
      <ErrorIcon />
    </span>
  );
}

function EndIconSuccess() {
  return (
    <span className={`${endIconBase} text-success-text`}>
      <svg
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        width="14"
        height="14"
      >
        <circle cx="8" cy="8" r="6.5" />
        <path d="M5 8l2 2 4-4" />
      </svg>
    </span>
  );
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  {
    id: idProp,
    label,
    helperText,
    error,
    success,
    required,
    disabled,
    className,
    ...rest
  },
  ref,
) {
  const reactId = useId();
  const id = idProp ?? reactId;
  const helperId = helperText ? `${id}-helper` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  const stateClass = error ? inputError : success ? inputSuccess : "";
  const hasEndIcon = !!error || success;

  return (
    <div className={`flex flex-col gap-1 ${className ?? ""}`}>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>

      <div className="relative flex items-center">
        <input
          ref={ref}
          id={id}
          className={`${inputBase} ${stateClass} ${hasEndIcon ? inputWithEndIcon : ""}`}
          required={required}
          disabled={disabled}
          aria-invalid={!!error || undefined}
          aria-describedby={helperId}
          aria-errormessage={errorId}
          {...rest}
        />
        {error ? (
          <EndIconError />
        ) : success ? (
          <EndIconSuccess />
        ) : null}
      </div>

      {helperText && !error && (
        <span id={helperId} className="text-xs text-text-muted leading-[1.4]">
          {helperText}
        </span>
      )}

      {error && (
        <span
          id={errorId}
          className="inline-flex items-center gap-1 text-xs text-error-text leading-[1.4]"
          role="alert"
        >
          <ErrorIcon />
          {error}
        </span>
      )}
    </div>
  );
});
