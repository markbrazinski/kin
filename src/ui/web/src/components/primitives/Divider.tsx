/* Divider — thin horizontal rule. */

export type DividerProps = {
  className?: string;
};

const Divider = ({ className = "" }: DividerProps) => (
  <div className={`border-t border-hair ${className}`} />
);

export { Divider };
