import {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ReactNode,
  forwardRef,
} from "react";
import Spinner from "@/app/components/icons/Spinner";

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

const baseClass =
  "inline-flex items-center justify-center gap-2 border border-transparent rounded-md font-medium leading-none cursor-pointer no-underline whitespace-nowrap transition duration-[120ms] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:opacity-40 disabled:cursor-not-allowed";

const variantClass: Record<Variant, string> = {
  primary:
    "bg-primary text-surface border-primary enabled:hover:bg-secondary enabled:hover:border-secondary",
  secondary:
    "bg-surface text-primary border-primary enabled:hover:bg-surface-muted",
  ghost:
    "bg-transparent text-text border-transparent enabled:hover:bg-surface-muted",
  danger:
    "bg-error-text text-surface border-error-text enabled:hover:brightness-[0.92]",
  "icon-label":
    "bg-transparent text-text border-border enabled:hover:bg-surface-muted enabled:hover:border-primary enabled:hover:text-primary",
};

const sizeClass: Record<Size, string> = {
  sm: "h-7 px-3 text-xs",
  md: "h-9 px-4 text-sm",
  lg: "h-11 px-5 text-base",
};

const loadingExtra = "cursor-progress pointer-events-none";

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
    baseClass,
    variantClass[variant],
    sizeClass[size],
    loading ? loadingExtra : "",
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
        <Spinner className="animate-[spin_700ms_linear_infinite] h-3.5 w-3.5 shrink-0" />
      ) : leftIcon ? (
        <span className="inline-flex items-center justify-center shrink-0">
          {leftIcon}
        </span>
      ) : null}
      <span>{loading ? "Salvando..." : children}</span>
      {!loading && rightIcon ? (
        <span className="inline-flex items-center justify-center shrink-0">
          {rightIcon}
        </span>
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
