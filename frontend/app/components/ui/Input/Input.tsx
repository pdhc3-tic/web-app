import { InputHTMLAttributes, forwardRef, useId } from "react";
import { Label } from "../Label/Label";
import styles from "./Input.module.css";

export type InputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "size"
> & {
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

function EndIconError() {
  return (
    <span className={`${styles.endIcon} ${styles.endIconError}`}>
      <ErrorIcon />
    </span>
  );
}

function EndIconSuccess() {
  return (
    <span className={`${styles.endIcon} ${styles.endIconSuccess}`}>
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

  const stateClass = error ? styles.error : success ? styles.success : "";
  const hasEndIcon = !!error || success;

  return (
    <div className={`${styles.field} ${className ?? ""}`}>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>

      <div className={styles.inputWrap}>
        <input
          ref={ref}
          id={id}
          className={`${styles.input} ${stateClass} ${
            hasEndIcon ? styles.inputWithEndIcon : ""
          }`}
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
});
