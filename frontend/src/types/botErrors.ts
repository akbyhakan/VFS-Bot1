export interface BotError {
  id: string;
  timestamp: string;
  error_type: string;
  error_message: string;
  context?: Record<string, unknown>;
  captures?: {
    full_screenshot?: string;
    element_screenshot?: string;
    html_snapshot?: string;
  };
  url?: string;
  failed_selector?: string;
  skipped?: boolean;
}

export interface SelectorHealth {
  status: string;
  message?: string;
  checks?: Record<string, {
    selector: string;
    found: boolean;
    response_time_ms?: number;
  }>;
}
