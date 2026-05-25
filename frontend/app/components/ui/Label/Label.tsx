import { LabelHTMLAttributes, ReactNode } from "react";
import styles from "./Label.module.css";

export type LabelProps = Omit<
  LabelHTMLAttributes<HTMLLabelElement>,
  "children"
> & {
  htmlFor: string;
  required?: boolean;
  children: ReactNode;
};

export function Label({
  htmlFor,
  required = false,
  children,
  className,
  ...rest
}: LabelProps) {
  return (
    <label
      htmlFor={htmlFor}
      className={`${styles.label} ${className ?? ""}`}
      {...rest}
    >
      {children}
      {required && (
        <>
          <span className={styles.required} aria-hidden="true">
            *
          </span>
          <span className={styles.requiredHint}>(obrigatório)</span>
        </>
      )}
    </label>
  );
}
