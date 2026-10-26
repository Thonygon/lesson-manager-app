import { Platform } from 'react-native';

/** Use the current origin on web and the deployed API from native builds. */
export function hostingApiUrl(path: `/${string}`, platform = Platform.OS, configuredHost = process.env.EXPO_PUBLIC_HOSTING_URL) {
  if (platform === 'web') return path;
  const host = (configuredHost?.trim() || 'https://classio.expo.app').replace(/\/+$/, '');
  return `${host}${path}`;
}
