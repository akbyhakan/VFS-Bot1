/**
 * Application version imported from package.json
 * This ensures the version displayed in the UI stays in sync with package.json
 * 
 * Note: Requires resolveJsonModule: true in tsconfig.json (already configured)
 * Vite handles JSON imports natively, so this works seamlessly in development and production builds.
 */
import packageJson from '../package.json';

export const APP_VERSION = packageJson.version;
