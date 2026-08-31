import { useQuery } from '@tanstack/react-query';
import { adminApi, publicApi, BrandingConfig } from '../api';

const defaultBranding: BrandingConfig = {
  site_title: 'NDS 管理',
  login_title: 'NDS 管理面板',
  admin_logo: '',
  user_logo: '',
};

export function useBranding(authenticated = true) {
  return useQuery({
    queryKey: ['branding', authenticated],
    queryFn: () =>
      (authenticated ? adminApi.getBranding() : publicApi.getBranding()).then(r => r.data),
    staleTime: 60_000,
    placeholderData: defaultBranding,
  });
}
