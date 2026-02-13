import { useState, useMemo } from 'react';
import { useAuditLogs, useAuditLogDetail, useAuditStats } from '@/hooks/useAuditLogs';
import type { AuditLog } from '@/hooks/useAuditLogs';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Table } from '@/components/ui/Table';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Loading } from '@/components/common/Loading';
import { Shield, Search, Filter, Download, Eye, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { cn, formatDate } from '@/utils/helpers';
import { toast } from 'sonner';

export default function AuditLogs() {
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [successFilter, setSuccessFilter] = useState<string>('all');
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  // Build filters
  const filters = useMemo(() => {
    const f: any = { limit: 500 };
    if (actionFilter) f.action = actionFilter;
    if (successFilter !== 'all') f.success = successFilter === 'success';
    return f;
  }, [actionFilter, successFilter]);

  const { data: logs, isLoading, error } = useAuditLogs(filters);
  const { data: stats, isLoading: statsLoading } = useAuditStats();
  const { data: selectedLog } = useAuditLogDetail(selectedLogId);

  // Client-side search filter
  const filteredLogs = useMemo(() => {
    if (!logs) return [];
    if (!searchQuery) return logs;

    const query = searchQuery.toLowerCase();
    return logs.filter(
      (log) =>
        log.username?.toLowerCase().includes(query) ||
        log.action.toLowerCase().includes(query) ||
        log.ip_address?.toLowerCase().includes(query)
    );
  }, [logs, searchQuery]);

  // Get unique actions for filter dropdown
  const uniqueActions = useMemo(() => {
    if (!logs) return [];
    const actions = new Set(logs.map((log) => log.action));
    return Array.from(actions).sort();
  }, [logs]);

  const handleViewDetail = (log: AuditLog) => {
    setSelectedLogId(log.id);
    setIsDetailModalOpen(true);
  };

  const handleCloseDetail = () => {
    setIsDetailModalOpen(false);
    setSelectedLogId(null);
  };

  const handleExportCSV = () => {
    if (!filteredLogs || filteredLogs.length === 0) {
      toast.error('No logs to export');
      return;
    }

    try {
      // Create CSV header
      const headers = [
        'ID',
        'Action',
        'User ID',
        'Username',
        'IP Address',
        'Success',
        'Timestamp',
        'Resource Type',
        'Resource ID',
      ];

      // Create CSV rows
      const rows = filteredLogs.map((log) => [
        log.id,
        log.action,
        log.user_id || '',
        log.username || '',
        log.ip_address || '',
        log.success ? 'Yes' : 'No',
        log.timestamp,
        log.resource_type || '',
        log.resource_id || '',
      ]);

      // Combine headers and rows
      const csvContent = [
        headers.join(','),
        ...rows.map((row) => row.map((cell) => `"${cell}"`).join(',')),
      ].join('\n');

      // Create blob and download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `audit_logs_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success('Audit logs exported successfully');
    } catch (error) {
      toast.error('Failed to export audit logs');
      console.error('Export error:', error);
    }
  };

  const handleExportJSON = () => {
    if (!filteredLogs || filteredLogs.length === 0) {
      toast.error('No logs to export');
      return;
    }

    try {
      const jsonContent = JSON.stringify(filteredLogs, null, 2);
      const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `audit_logs_${new Date().toISOString().split('T')[0]}.json`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success('Audit logs exported successfully');
    } catch (error) {
      toast.error('Failed to export audit logs');
      console.error('Export error:', error);
    }
  };

  if (isLoading) {
    return <Loading fullScreen text="Denetim logları yükleniyor..." />;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card className="max-w-md">
          <CardContent className="p-6 text-center">
            <AlertCircle className="w-12 h-12 mx-auto text-red-500 mb-4" />
            <h3 className="text-lg font-semibold text-dark-100 mb-2">Yükleme Hatası</h3>
            <p className="text-dark-400">Denetim logları yüklenirken bir hata oluştu.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-8 h-8 text-primary-500" />
          <div>
            <h1 className="text-3xl font-bold text-gradient">Denetim Logları</h1>
            <p className="text-dark-400 mt-1">Güvenlik denetimi ve aktivite kayıtları</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleExportCSV} variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            CSV
          </Button>
          <Button onClick={handleExportJSON} variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            JSON
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && !statsLoading && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Toplam Kayıt</p>
                  <p className="text-2xl font-bold text-dark-100">{stats.total}</p>
                </div>
                <Shield className="w-8 h-8 text-primary-500 opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Başarı Oranı</p>
                  <p className="text-2xl font-bold text-green-400">
                    {(stats.success_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <CheckCircle className="w-8 h-8 text-green-500 opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Son 24s Hata</p>
                  <p className="text-2xl font-bold text-red-400">{stats.recent_failures}</p>
                </div>
                <XCircle className="w-8 h-8 text-red-500 opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Eylem Tipi</p>
                  <p className="text-2xl font-bold text-dark-100">
                    {Object.keys(stats.by_action).length}
                  </p>
                </div>
                <Filter className="w-8 h-8 text-primary-500 opacity-50" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters and Search */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
              <Input
                type="text"
                placeholder="Kullanıcı, eylem veya IP ara..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Action Filter */}
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-dark-100 
                       focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Tüm Eylemler</option>
              {uniqueActions.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>

            {/* Success Filter */}
            <select
              value={successFilter}
              onChange={(e) => setSuccessFilter(e.target.value)}
              className="px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-dark-100 
                       focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="all">Tümü</option>
              <option value="success">Başarılı</option>
              <option value="failure">Başarısız</option>
            </select>

            {/* Clear Filters */}
            <Button
              onClick={() => {
                setSearchQuery('');
                setActionFilter('');
                setSuccessFilter('all');
              }}
              variant="outline"
              size="sm"
            >
              Filtreleri Temizle
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Denetim Kayıtları
            {filteredLogs && (
              <span className="ml-2 text-sm font-normal text-dark-400">
                ({filteredLogs.length} kayıt)
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredLogs && filteredLogs.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <thead>
                  <tr>
                    <th className="text-left">Durum</th>
                    <th className="text-left">Eylem</th>
                    <th className="text-left">Kullanıcı</th>
                    <th className="text-left">IP Adresi</th>
                    <th className="text-left">Zaman</th>
                    <th className="text-left">Kaynak</th>
                    <th className="text-right">İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-dark-800/50 transition-colors">
                      <td>
                        {log.success ? (
                          <CheckCircle className="w-5 h-5 text-green-500" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-500" />
                        )}
                      </td>
                      <td>
                        <span className="font-mono text-sm">{log.action}</span>
                      </td>
                      <td>
                        <div className="flex flex-col">
                          <span className="text-dark-100">{log.username || 'N/A'}</span>
                          {log.user_id && (
                            <span className="text-xs text-dark-500">ID: {log.user_id}</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span className="font-mono text-sm text-dark-300">
                          {log.ip_address || 'N/A'}
                        </span>
                      </td>
                      <td>
                        <span className="text-sm text-dark-300">{formatDate(log.timestamp)}</span>
                      </td>
                      <td>
                        {log.resource_type ? (
                          <div className="flex flex-col">
                            <span className="text-sm text-dark-300">{log.resource_type}</span>
                            {log.resource_id && (
                              <span className="text-xs text-dark-500">{log.resource_id}</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-dark-500">-</span>
                        )}
                      </td>
                      <td className="text-right">
                        <Button
                          onClick={() => handleViewDetail(log)}
                          variant="ghost"
                          size="sm"
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12">
              <Shield className="w-12 h-12 mx-auto text-dark-600 mb-3" />
              <p className="text-dark-400">Gösterilecek denetim kaydı bulunamadı</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Modal */}
      <Modal
        isOpen={isDetailModalOpen}
        onClose={handleCloseDetail}
        title="Denetim Kaydı Detayı"
      >
        {selectedLog ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-dark-400">ID</label>
                <p className="text-dark-100 font-mono">{selectedLog.id}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">Durum</label>
                <p
                  className={cn(
                    'flex items-center gap-2',
                    selectedLog.success ? 'text-green-400' : 'text-red-400'
                  )}
                >
                  {selectedLog.success ? (
                    <>
                      <CheckCircle className="w-4 h-4" /> Başarılı
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4" /> Başarısız
                    </>
                  )}
                </p>
              </div>
              <div>
                <label className="text-sm text-dark-400">Eylem</label>
                <p className="text-dark-100 font-mono">{selectedLog.action}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">Kullanıcı Adı</label>
                <p className="text-dark-100">{selectedLog.username || 'N/A'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">Kullanıcı ID</label>
                <p className="text-dark-100">{selectedLog.user_id || 'N/A'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">IP Adresi</label>
                <p className="text-dark-100 font-mono">{selectedLog.ip_address || 'N/A'}</p>
              </div>
              <div className="col-span-2">
                <label className="text-sm text-dark-400">User Agent</label>
                <p className="text-dark-100 text-sm break-all">
                  {selectedLog.user_agent || 'N/A'}
                </p>
              </div>
              <div>
                <label className="text-sm text-dark-400">Kaynak Tipi</label>
                <p className="text-dark-100">{selectedLog.resource_type || 'N/A'}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">Kaynak ID</label>
                <p className="text-dark-100">{selectedLog.resource_id || 'N/A'}</p>
              </div>
              <div className="col-span-2">
                <label className="text-sm text-dark-400">Zaman</label>
                <p className="text-dark-100">{formatDate(selectedLog.timestamp)}</p>
              </div>
              {selectedLog.details && (
                <div className="col-span-2">
                  <label className="text-sm text-dark-400">Detaylar</label>
                  <pre className="text-dark-100 text-xs bg-dark-900 p-3 rounded mt-1 overflow-x-auto">
                    {JSON.stringify(JSON.parse(selectedLog.details || '{}'), null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        ) : (
          <Loading text="Yükleniyor..." />
        )}
      </Modal>
    </div>
  );
}
