import {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ReactNode,
  forwardRef,
} from "react";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "icon-label";
type Size = "sm" | "md" | "lg";

type CommonProps = {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  children?: ReactNode;
  className?: string;
};

type ButtonAsButton = CommonProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps> & {
    as?: "button";
  };

type ButtonAsAnchor = CommonProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps> & {
    as: "a";
    href: string;
  };

export type ButtonProps = ButtonAsButton | ButtonAsAnchor;

const variantClass: Record<Variant, string> = {
  primary: styles.primary,
  secondary: styles.secondary,
  ghost: styles.ghost,
  danger: styles.danger,
  "icon-label": styles.iconLabel,
};

const sizeClass: Record<Size, string> = {
  sm: styles.sizeSm,
  md: styles.sizeMd,
  lg: styles.sizeLg,
};

function Spinner() {
  return (
    <svg
      className={styles.spinner}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="4"
      />
      <path
        d="M4 12a8 8 0 018-8"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function isAnchor(props: ButtonProps): props is ButtonAsAnchor {
  return props.as === "a";
}

function buildClasses(
  variant: Variant,
  size: Size,
  loading: boolean,
  extra: string | undefined,
) {
  return [
    styles.button,
    variantClass[variant],
    sizeClass[size],
    loading ? styles.loading : "",
    extra ?? "",
  ]
    .filter(Boolean)
    .join(" ");
}

function renderContent(
  loading: boolean,
  leftIcon: ReactNode,
  rightIcon: ReactNode,
  children: ReactNode,
) {
  return (
    <>
      {loading ? (
        <Spinner />
      ) : leftIcon ? (
        <span className={styles.icon}>{leftIcon}</span>
      ) : null}
      <span>{loading ? "Salvando..." : children}</span>
      {!loading && rightIcon ? (
        <span className={styles.icon}>{rightIcon}</span>
      ) : null}
    </>
  );
}

export const Button = forwardRef<
  HTMLButtonElement | HTMLAnchorElement,
  ButtonProps
>(function Button(props, ref) {
  if (isAnchor(props)) {
    const {
      as,
      variant = "primary",
      size = "md",
      loading = false,
      leftIcon,
      rightIcon,
      children,
      className,
      ...anchorProps
    } = props;
    void as;
    return (
      <a
        ref={ref as React.Ref<HTMLAnchorElement>}
        className={buildClasses(variant, size, loading, className)}
        aria-disabled={loading || undefined}
        {...anchorProps}
      >
        {renderContent(loading, leftIcon, rightIcon, children)}
      </a>
    );
  }

  const {
    as,
    variant = "primary",
    size = "md",
    loading = false,
    leftIcon,
    rightIcon,
    children,
    className,
    disabled,
    type,
    ...buttonProps
  } = props;
  void as;

  return (
    <button
      ref={ref as React.Ref<HTMLButtonElement>}
      className={buildClasses(variant, size, loading, className)}
      type={type ?? "button"}
      disabled={disabled || loading}
      {...buttonProps}
    >
      {renderContent(loading, leftIcon, rightIcon, children)}
    </button>
  );
});
