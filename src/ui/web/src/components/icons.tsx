/* Inline Lucide-style icons — line, 1.75px stroke, original paths matching Lucide's open license semantics.
   Kept in one file so the artifact has no external icon package dependency. */
import React from 'react';
import type { SVGProps } from 'react';

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'width' | 'height' | 'strokeWidth'> & {
  size?: number;
  strokeWidth?: number;
};

const Icon = ({ children, size = 18, className = "", strokeWidth = 1.75, ...rest }: IconProps) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...rest}
  >
    {children}
  </svg>
);

const IconMic       = (p: IconProps) => <Icon {...p}><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></Icon>;
const IconPlay      = (p: IconProps) => <Icon {...p}><path d="M6 4l14 8-14 8V4z"/></Icon>;
const IconPause     = (p: IconProps) => <Icon {...p}><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></Icon>;
const IconShield    = (p: IconProps) => <Icon {...p}><path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"/></Icon>;
const IconLock      = (p: IconProps) => <Icon {...p}><rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></Icon>;
const IconCloudOff  = (p: IconProps) => <Icon {...p}><path d="M3 3l18 18"/><path d="M7 18h10a4 4 0 0 0 .7-7.95A6 6 0 0 0 6.3 8.3"/></Icon>;
const IconCheck     = (p: IconProps) => <Icon {...p}><path d="M5 12l4 4L19 6"/></Icon>;
const IconAlert     = (p: IconProps) => <Icon {...p}><path d="M12 3 2 20h20L12 3z"/><path d="M12 10v5"/><circle cx="12" cy="18" r=".5" fill="currentColor"/></Icon>;
const IconInfo      = (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="8" r=".5" fill="currentColor"/></Icon>;
const IconArrowRight= (p: IconProps) => <Icon {...p}><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></Icon>;
const IconChevron   = (p: IconProps) => <Icon {...p}><path d="M6 9l6 6 6-6"/></Icon>;
const IconLanguages = (p: IconProps) => <Icon {...p}><path d="M3 5h10"/><path d="M8 3v2"/><path d="M5 9c.5 3 2.5 5 5 6"/><path d="M11 9c-.5 3-2.5 5-5 6"/><path d="M13 21l5-10 5 10"/><path d="M15 17h6"/></Icon>;
const IconUser      = (p: IconProps) => <Icon {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6"/></Icon>;
const IconMapPin    = (p: IconProps) => <Icon {...p}><path d="M12 21s-7-7.5-7-12a7 7 0 1 1 14 0c0 4.5-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/></Icon>;
const IconCamera    = (p: IconProps) => <Icon {...p}><path d="M4 7h3l2-2h6l2 2h3v12H4z"/><circle cx="12" cy="13" r="3.5"/></Icon>;
const IconDev       = (p: IconProps) => <Icon {...p}><path d="M8 6l-5 6 5 6"/><path d="M16 6l5 6-5 6"/></Icon>;
const IconX         = (p: IconProps) => <Icon {...p}><path d="M6 6l12 12"/><path d="M6 18L18 6"/></Icon>;
const IconLink      = (p: IconProps) => <Icon {...p}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></Icon>;
const IconSparkle   = (p: IconProps) => <Icon {...p}><path d="M12 3v4"/><path d="M12 17v4"/><path d="M3 12h4"/><path d="M17 12h4"/><path d="M6 6l2 2"/><path d="M16 16l2 2"/><path d="M6 18l2-2"/><path d="M16 8l2-2"/></Icon>;
const IconRotate    = (p: IconProps) => <Icon {...p}><path d="M4 12a8 8 0 0 1 14-5.3L20 8"/><path d="M20 4v4h-4"/><path d="M20 12a8 8 0 0 1-14 5.3L4 16"/><path d="M4 20v-4h4"/></Icon>;
const IconTerminal  = (p: IconProps) => <Icon {...p}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3"/><path d="M12 15h5"/></Icon>;
const IconClock     = (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>;
const IconList      = (p: IconProps) => <Icon {...p}><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><circle cx="4" cy="6" r="1" fill="currentColor" stroke="none"/><circle cx="4" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="4" cy="18" r="1" fill="currentColor" stroke="none"/></Icon>;

export {
  Icon, IconMic, IconPlay, IconPause, IconShield, IconLock, IconCloudOff, IconCheck,
  IconAlert, IconInfo, IconArrowRight, IconChevron, IconLanguages, IconUser,
  IconMapPin, IconCamera, IconDev, IconX, IconLink, IconSparkle, IconRotate,
  IconTerminal, IconClock, IconList,
};
