import { LabelHTMLAttributes, ReactNode } from "react";

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
      className={`inline-flex items-baseline gap-1 text-label font-medium text-text leading-[1.2] ${className ?? ""}`}
      {...rest}
    >
      {children}
      {required && (
        <>
          <span className="ml-0.5 font-semibold text-error-text" aria-hidden="true">
            *
          </span>
          <span className="ml-0.5 text-2xs text-text-muted">(obrigatório)</span>
        </>
      )}
    </label>
  );
}
