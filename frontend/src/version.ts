/**
 * Application version imported from package.json
 * This ensures the version displayed in the UI stays in sync with package.json
 */
import packageJson from '../package.json';

export const APP_VERSION = packageJson.version;
