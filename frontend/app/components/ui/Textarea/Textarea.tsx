import { TextareaHTMLAttributes, forwardRef, useId } from "react";
import { Label } from "../Label/Label";
import styles from "./Textarea.module.css";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  helperText?: string;
  error?: string;
  success?: boolean;
};

function ErrorIcon() {
  return (
    <svg
      className={styles.errorIcon}
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

    const stateClass = error ? styles.error : success ? styles.success : "";

    return (
      <div className={`${styles.field} ${className ?? ""}`}>
        <Label htmlFor={id} required={required}>
          {label}
        </Label>

        <div className={styles.textareaWrap}>
          <textarea
            ref={ref}
            id={id}
            className={`${styles.textarea} ${stateClass}`}
            required={required}
            disabled={disabled}
            aria-invalid={!!error || undefined}
            aria-describedby={helperId}
            aria-errormessage={errorId}
            {...rest}
          />
        </div>

        {helperText && !error && (
          <span id={helperId} className={styles.helper}>
            {helperText}
          </span>
        )}

        {error && (
          <span id={errorId} className={styles.errorMessage} role="alert">
            <ErrorIcon />
            {error}
          </span>
        )}
      </div>
    );
  },
);
