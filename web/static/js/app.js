// VFS-Bot Dashboard JavaScript

class Dashboard {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadInitialStatus();
    }

    setupEventListeners() {
        // Start button
        document.getElementById('start-btn').addEventListener('click', () => {
            this.startBot();
        });

        // Stop button
        document.getElementById('stop-btn').addEventListener('click', () => {
            this.stopBot();
        });

        // Clear logs button
        document.getElementById('clear-logs-btn').addEventListener('click', () => {
            this.clearLogs();
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.addLog('Connected to server', 'SUCCESS');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.addLog('Disconnected from server', 'WARNING');
            this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
                console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
                this.connectWebSocket();
            }, 2000 * this.reconnectAttempts);
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'status':
                this.updateStatus(data.data);
                break;
            case 'stats':
                this.updateStats(data.data);
                break;
            case 'log':
                this.addLog(data.data.message, data.data.level);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    async loadInitialStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            this.updateStatus({
                running: data.running,
                status: data.status
            });
            
            if (data.stats) {
                this.updateStats({
                    slots_found: data.stats.slots_found,
                    appointments_booked: data.stats.appointments_booked,
                    active_users: data.stats.active_users,
                    last_check: data.last_check
                });
            }
        } catch (error) {
            console.error('Failed to load initial status:', error);
        }
    }

    async startBot() {
        try {
            const response = await fetch('/api/bot/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    config: {}
                })
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                this.addLog('Bot started successfully', 'SUCCESS');
            } else {
                this.addLog(`Failed to start bot: ${data.message}`, 'ERROR');
            }
        } catch (error) {
            console.error('Error starting bot:', error);
            this.addLog(`Error starting bot: ${error.message}`, 'ERROR');
        }
    }

    async stopBot() {
        try {
            const response = await fetch('/api/bot/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                this.addLog('Bot stopped successfully', 'WARNING');
            } else {
                this.addLog(`Failed to stop bot: ${data.message}`, 'ERROR');
            }
        } catch (error) {
            console.error('Error stopping bot:', error);
            this.addLog(`Error stopping bot: ${error.message}`, 'ERROR');
        }
    }

    updateStatus(data) {
        const statusText = document.getElementById('status-text');
        const statusDot = document.getElementById('status-dot');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');

        if (data.running) {
            statusText.textContent = 'Running';
            statusDot.className = 'dot running';
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusText.textContent = 'Stopped';
            statusDot.className = 'dot stopped';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }

    updateStats(data) {
        if (data.slots_found !== undefined) {
            document.getElementById('slots-found').textContent = data.slots_found;
        }
        
        if (data.appointments_booked !== undefined) {
            document.getElementById('appointments-booked').textContent = data.appointments_booked;
        }
        
        if (data.active_users !== undefined) {
            document.getElementById('active-users').textContent = data.active_users;
        }
        
        if (data.last_check) {
            const date = new Date(data.last_check);
            document.getElementById('last-check').textContent = date.toLocaleTimeString();
        }
    }

    addLog(message, level = 'INFO') {
        const logsContainer = document.getElementById('logs-container');
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${level}`;
        logEntry.textContent = message;
        
        logsContainer.appendChild(logEntry);
        
        // Auto-scroll to bottom
        logsContainer.scrollTop = logsContainer.scrollHeight;
        
        // Keep only last 200 logs
        while (logsContainer.children.length > 200) {
            logsContainer.removeChild(logsContainer.firstChild);
        }
    }

    clearLogs() {
        const logsContainer = document.getElementById('logs-container');
        logsContainer.innerHTML = '';
        this.addLog('Logs cleared', 'INFO');
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
