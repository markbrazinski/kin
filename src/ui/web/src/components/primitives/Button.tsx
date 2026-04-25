/* Button — variant + size + optional icon. Disabled state is structural (border + text), never opacity. */
import { forwardRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'confirm';
  size?: 'sm' | 'md' | 'lg';
  icon?: ReactNode;
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", icon, className = "", children, disabled, ...rest }, ref) => {
    const base = "inline-flex items-center justify-center gap-2 font-medium rounded-kin transition-colors duration-150 select-none";
    const sizes = {
      sm: "text-[14px] px-3 h-9",
      md: "text-[15px] px-4 h-10",
      lg: "text-[16px] px-5 h-12",
    };
    const variants = {
      primary: disabled
        ? "bg-white border border-line text-muted cursor-not-allowed"
        : "bg-primary text-white border border-primary hover:bg-primary-2",
      secondary: disabled
        ? "bg-white border border-line text-muted cursor-not-allowed"
        : "bg-white border border-line text-ink hover:bg-subtle",
      ghost: disabled
        ? "text-muted cursor-not-allowed"
        : "text-ink hover:bg-subtle",
      danger: disabled
        ? "bg-white border border-line text-muted cursor-not-allowed"
        : "bg-white border border-red text-red hover:bg-red-soft",
      confirm: disabled
        ? "bg-white border border-line text-muted cursor-not-allowed"
        : "bg-green text-white border border-green hover:brightness-95",
    };
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
        {...rest}
      >
        {icon}
        {children}
      </button>
    );
  }
);

export { Button };
