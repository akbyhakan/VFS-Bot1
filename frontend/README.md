# VFS-Bot Modern Frontend Dashboard

Modern, responsive React + TypeScript + Tailwind CSS dashboard for VFS-Bot automation system.

## 🎨 Features

- ✅ **Modern UI** - Glassmorphism design with dark theme
- ✅ **Real-time Updates** - WebSocket integration for live logs and status
- ✅ **Responsive Design** - Mobile-first approach, works on all devices
- ✅ **Type-Safe** - Full TypeScript support
- ✅ **Authentication** - JWT-based login with "Remember Me"
- ✅ **User Management** - Full CRUD operations for VFS users
- ✅ **Dashboard** - Live bot status, statistics, and controls
- ✅ **Settings** - Bot and notification configuration
- ✅ **Logs** - Real-time log viewing and filtering
- ✅ **PWA Ready** - Progressive Web App support

## 🛠️ Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.3.x | UI Framework |
| TypeScript | 5.7.x | Type Safety |
| Vite | 6.1.x | Build Tool |
| Tailwind CSS | 3.4.x | Styling |
| Zustand | 5.0.x | State Management |
| React Router | 7.1.x | Routing |
| React Query | 5.66.x | Data Fetching |
| React Hook Form | 7.54.x | Form Handling |
| Zod | 3.24.x | Validation |
| Axios | 1.13.x | HTTP Client |
| Lucide React | Latest | Icons |
| Sonner | 1.3.x | Toast Notifications |

## 📁 Project Structure

```
frontend/
├── public/              # Static files
│   ├── manifest.json    # PWA manifest
│   └── robots.txt
├── src/
│   ├── components/      # React components
│   │   ├── ui/         # Base UI components (Button, Card, Input, Modal, Table)
│   │   ├── layout/     # Layout components (Sidebar, Header, Layout)
│   │   ├── dashboard/  # Dashboard-specific components
│   │   ├── users/      # User management components
│   │   └── common/     # Common components (Loading, ErrorBoundary, ProtectedRoute)
│   ├── pages/          # Page components
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Users.tsx
│   │   ├── Settings.tsx
│   │   ├── Logs.tsx
│   │   └── NotFound.tsx
│   ├── hooks/          # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   └── useApi.ts
│   ├── services/       # API and service layer
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── websocket.ts
│   ├── store/          # Zustand state stores
│   │   ├── authStore.ts
│   │   ├── botStore.ts
│   │   └── userStore.ts
│   ├── types/          # TypeScript type definitions
│   │   ├── api.ts
│   │   ├── user.ts
│   │   └── bot.ts
│   ├── utils/          # Utility functions
│   │   ├── constants.ts
│   │   ├── helpers.ts
│   │   └── validators.ts
│   ├── styles/         # Global styles
│   │   └── globals.css
│   ├── App.tsx         # Main app component
│   └── main.tsx        # Entry point
├── index.html          # HTML template
├── package.json        # Dependencies
├── tsconfig.json       # TypeScript config
├── tailwind.config.js  # Tailwind config
├── vite.config.ts      # Vite config
└── README.md          # This file
```

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- Backend API running on `http://localhost:8000`

### Installation

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   # or
   pnpm install
   ```

3. **Configure environment (optional)**
   
   Create `.env` file if you need to override defaults:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_WS_BASE_URL=ws://localhost:8000
   ```

4. **Start development server**
   ```bash
   npm run dev
   ```
   
   Frontend will be available at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

This will create optimized production build in `../web/static/dist` directory, which can be served by the FastAPI backend.

### Type Checking

```bash
npm run type-check
```

## 🔐 Authentication

The frontend uses JWT-based authentication with HttpOnly cookies:

1. Login with admin credentials (set in backend `.env`)
2. JWT token is managed via **HttpOnly cookie** (set by the server automatically)
3. Cookie-based authentication is used for all API requests (no manual token handling)
4. Token expires after configured time (default 24h)
5. "Remember Me" preference is stored locally to persist login intent across sessions
6. Logout clears the HttpOnly cookie via the `/api/auth/logout` endpoint

## 🌐 API Integration

### Endpoints Used

- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/logout` - User logout (clears HttpOnly cookie)
- `GET /api/status` - Bot status (non-versioned health endpoint)
- `POST /api/v1/bot/start` - Start bot
- `POST /api/v1/bot/stop` - Stop bot
- `POST /api/v1/bot/restart` - Restart bot
- `POST /api/v1/bot/check-now` - Manual check trigger
- `GET /api/v1/bot/logs` - Fetch logs
- `GET /api/metrics` - Bot metrics (non-versioned health endpoint)
- `GET /health` - Health check (non-versioned)
- `GET /api/v1/users` - User management
- `WS /ws` - WebSocket for real-time updates

### WebSocket Messages

The frontend listens for these WebSocket message types:
- `status` - Bot status updates
- `log` - New log entries
- `stats` - Statistics updates
- `ping` - Keep-alive ping

## 🎨 Customization

### Theme Colors

Edit `tailwind.config.js` to customize colors:

```javascript
colors: {
  primary: {
    500: '#22c55e', // Main green color
    // ...
  },
  dark: {
    900: '#0f172a', // Background
    // ...
  },
}
```

### Component Styling

All components use Tailwind CSS utility classes. Custom styles are defined in `src/styles/globals.css`.

## 📱 PWA Support

The application includes PWA manifest for installation on mobile devices and desktop. To enable full PWA features, add a service worker in future updates.

## 🔧 Development

### Adding New Pages

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation link in `src/components/layout/Sidebar.tsx`

### Creating New Components

1. Place in appropriate directory (`ui/`, `layout/`, `common/`)
2. Use TypeScript interfaces for props
3. Export component as named export
4. Document props with JSDoc comments

### State Management

- **Authentication**: `authStore` (Zustand)
- **Bot State**: `botStore` (Zustand)
- **User Data**: React Query + `userStore`

### Form Validation

Forms use `react-hook-form` + `zod`:

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { mySchema } from '@/utils/validators';

const { register, handleSubmit } = useForm({
  resolver: zodResolver(mySchema),
});
```

## 🐛 Troubleshooting

### Build Errors

- Clear `node_modules` and reinstall: `rm -rf node_modules package-lock.json && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`

### API Connection Issues

- Verify backend is running on `http://localhost:8000`
- Check CORS settings in backend
- Ensure JWT tokens are valid

### WebSocket Not Connecting

- Check backend WebSocket endpoint is accessible
- Verify authentication token is valid
- Check browser console for connection errors

## 📄 License

MIT License - see LICENSE file in repository root

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## 📞 Support

For issues and questions, please open an issue on GitHub.
