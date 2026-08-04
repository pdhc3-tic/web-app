import { InputHTMLAttributes, ReactNode, forwardRef, useId } from "react";
import { Label } from "../Label/Label";
import { ErrorIcon, CheckIcon } from "@/app/components/icons";

export type InputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "size"
> & {
  label: string;
  helperText?: string;
  error?: string;
  success?: boolean;
  startIcon?: ReactNode;
};

const inputBase =
  "w-full h-9 text-sm text-text bg-surface border border-border rounded-md outline-none placeholder:text-text-muted transition duration-[120ms] enabled:hover:border-text-muted focus:border-2 focus:border-primary focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] disabled:bg-surface-muted disabled:text-text-muted disabled:cursor-not-allowed disabled:opacity-70";

const inputError =
  "border-error-text focus:border-error-text focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-error-text)_15%,transparent)]";

const inputSuccess = "border-success-text focus:border-success-text";

const startIconBase =
  "absolute left-3 top-1/2 -translate-y-1/2 inline-flex items-center justify-center w-4 h-4 pointer-events-none text-text-muted";

const endIconBase =
  "absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center justify-center w-4 h-4 pointer-events-none";

function EndIconError() {
  return (
    <span className={`${endIconBase} text-error-text`}>
      <ErrorIcon className="w-3.5 h-3.5 shrink-0" />
    </span>
  );
}

function EndIconSuccess() {
  return (
    <span className={`${endIconBase} text-success-text`}>
      <CheckIcon className="w-3.5 h-3.5 shrink-0" />
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
    startIcon,
    ...rest
  },
  ref,
) {
  const reactId = useId();
  const id = idProp ?? reactId;
  const helperId = helperText ? `${id}-helper` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  const stateClass = error ? inputError : success ? inputSuccess : "";
  const hasEndIcon = !!error || !!success;

  const pl = startIcon
    ? "pl-9 focus:pl-[calc(var(--space-9)-1px)]"
    : "pl-3 focus:pl-[calc(var(--space-3)-1px)]";
  const pr = hasEndIcon
    ? "pr-7 focus:pr-[calc(var(--space-7)-1px)]"
    : "pr-3 focus:pr-[calc(var(--space-3)-1px)]";

  return (
    <div className={`flex flex-col gap-1 ${className ?? ""}`}>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>

      <div className="relative flex items-center">
        {startIcon && (
          <span className={startIconBase}>{startIcon}</span>
        )}
        <input
          ref={ref}
          id={id}
          className={`${inputBase} ${pl} ${pr} ${stateClass}`}
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
