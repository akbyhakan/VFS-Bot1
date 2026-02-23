import { Component, ErrorInfo, ReactNode } from 'react';
import { logger } from '@/utils/logger';
import i18n from '@/i18n';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logger.error('Uncaught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="min-h-screen flex items-center justify-center p-4 bg-dark-900">
          <div className="text-center">
            <h2 className="text-xl text-red-500 mb-4">{i18n.t('errorBoundary.title')}</h2>
            <p className="text-dark-400 mb-4">{i18n.t('errorBoundary.description')}</p>
            <button 
              onClick={() => this.setState({ hasError: false })}
              className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
            >
              {i18n.t('errorBoundary.retry')}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
