import type { CapacitorConfig } from '@capacitor/cli';

const webUrl = process.env.IHALEX_WEB_URL;

if (webUrl && !webUrl.startsWith('https://')) {
  throw new Error('IHALEX_WEB_URL production için HTTPS olmalıdır.');
}

const config: CapacitorConfig = {
  appId: 'tr.com.ihalex.app',
  appName: 'İhalex',
  webDir: 'www',
  server: webUrl ? {
    url: `${webUrl.replace(/\/$/, '')}/?embedded=1`,
    cleartext: false,
    allowNavigation: [new URL(webUrl).hostname],
  } : undefined,
};

export default config;
