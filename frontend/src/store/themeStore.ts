import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { logger } from '@/utils/logger';

type Theme = 'dark' | 'light';

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

/**
 * Theme store for managing dark/light mode
 * Persists theme preference to localStorage
 */
export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: 'dark',
      
      toggleTheme: () =>
        set((state) => {
          const newTheme = state.theme === 'dark' ? 'light' : 'dark';
          updateDocumentTheme(newTheme);
          return { theme: newTheme };
        }),
      
      setTheme: (theme) =>
        set(() => {
          updateDocumentTheme(theme);
          return { theme };
        }),
    }),
    {
      name: 'vfs-bot-theme',
      onRehydrateStorage: () => (state) => {
        // Apply theme on initial load
        if (state) {
          updateDocumentTheme(state.theme);
        }
      },
    }
  )
);

/**
 * Update document class and meta tags for theme
 */
function updateDocumentTheme(theme: Theme) {
  const root = document.documentElement;
  
  if (theme === 'dark') {
    root.classList.add('dark');
    root.classList.remove('light');
  } else {
    root.classList.remove('dark');
    root.classList.add('light');
  }
  
  // Update meta theme-color for mobile browsers
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');
  if (metaThemeColor) {
    metaThemeColor.setAttribute(
      'content',
      theme === 'dark' ? '#0f172a' : '#ffffff'
    );
  }
}

/**
 * Initialize theme on app load
 * Checks for saved preference or system preference
 */
export function initializeTheme() {
  const savedTheme = localStorage.getItem('vfs-bot-theme');
  
  if (savedTheme) {
    try {
      const { state } = JSON.parse(savedTheme);
      updateDocumentTheme(state.theme);
    } catch (error) {
      logger.error('Failed to parse saved theme:', error);
    }
  } else {
    // Check system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    updateDocumentTheme(prefersDark ? 'dark' : 'light');
  }
}
