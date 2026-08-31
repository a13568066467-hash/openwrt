import {
  PlansIcon,
  VouchersIcon,
  RoutersIcon,
  AuditIcon,
  UsersIcon,
  UsageIcon,
  BrandingIcon,
} from './icons/CustomMenuIcons';

function wrapCustom(Icon: typeof PlansIcon) {
  return (
    <span className="menu-icon menu-icon--custom">
      <Icon size={22} />
    </span>
  );
}

export const menuIcons = {
  routers: wrapCustom(RoutersIcon),
  users: wrapCustom(UsersIcon),
  plans: wrapCustom(PlansIcon),
  vouchers: wrapCustom(VouchersIcon),
  usage: wrapCustom(UsageIcon),
  audit: wrapCustom(AuditIcon),
  branding: wrapCustom(BrandingIcon),
} as const;

export { LogoutIcon } from './MenuIconsLogout';
