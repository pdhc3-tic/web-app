import { TextareaHTMLAttributes, forwardRef, useId } from "react";
import { Label } from "../Label/Label";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  helperText?: string;
  error?: string;
  success?: boolean;
};

const textareaBase =
  "w-full min-h-[88px] py-2 px-3 text-sm leading-normal text-text bg-surface border border-border rounded-md outline-none resize-y placeholder:text-text-muted transition duration-[120ms] enabled:hover:border-text-muted focus:border-2 focus:border-primary focus:py-[calc(var(--space-2)-1px)] focus:px-[calc(var(--space-3)-1px)] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] disabled:bg-surface-muted disabled:text-text-muted disabled:cursor-not-allowed disabled:opacity-70";

const textareaError =
  "border-error-text focus:border-error-text focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-error-text)_15%,transparent)]";

const textareaSuccess = "border-success-text focus:border-success-text";

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

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
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

    const stateClass = error
      ? textareaError
      : success
        ? textareaSuccess
        : "";

    return (
      <div className={`flex flex-col gap-1 ${className ?? ""}`}>
        <Label htmlFor={id} required={required}>
          {label}
        </Label>

        <div className="relative flex">
          <textarea
            ref={ref}
            id={id}
            className={`${textareaBase} ${stateClass}`}
            required={required}
            disabled={disabled}
            aria-invalid={!!error || undefined}
            aria-describedby={helperId}
            aria-errormessage={errorId}
            {...rest}
          />
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
  },
);
