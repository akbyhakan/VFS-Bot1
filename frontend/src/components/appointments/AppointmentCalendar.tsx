import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, CheckCircle2, Clock, Circle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { cn } from '@/utils/helpers';
import type { AppointmentRequestResponse } from '@/types/appointment';

interface AppointmentCalendarProps {
  appointments: AppointmentRequestResponse[];
  onDateClick?: (date: string) => void;
}

interface DayData {
  date: Date;
  dateString: string;
  isCurrentMonth: boolean;
  hasPreferredDate: boolean;
  hasBookedAppointment: boolean;
  hasChecked: boolean;
  appointments: AppointmentRequestResponse[];
}

export function AppointmentCalendar({ appointments, onDateClick }: AppointmentCalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  // Navigate months
  const previousMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  // Get month/year display
  const monthYear = useMemo(() => {
    return currentDate.toLocaleDateString('tr-TR', { month: 'long', year: 'numeric' });
  }, [currentDate]);

  // Build calendar days
  const calendarDays = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    // First day of month and last day
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    // Get day of week (0 = Sunday, adjust to Monday = 0)
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek === -1) startDayOfWeek = 6; // Sunday becomes 6

    const days: DayData[] = [];

    // Add previous month's trailing days
    const prevMonthLastDay = new Date(year, month, 0);
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const date = new Date(year, month - 1, prevMonthLastDay.getDate() - i);
      days.push({
        date,
        dateString: date.toISOString().split('T')[0],
        isCurrentMonth: false,
        hasPreferredDate: false,
        hasBookedAppointment: false,
        hasChecked: false,
        appointments: [],
      });
    }

    // Add current month's days
    for (let day = 1; day <= lastDay.getDate(); day++) {
      const date = new Date(year, month, day);
      const dateString = date.toISOString().split('T')[0];

      // Check appointments for this date
      const dayAppointments = appointments.filter((apt) => {
        if (apt.status === 'booked' && apt.booked_date) {
          return apt.booked_date.startsWith(dateString);
        }
        if (apt.preferred_dates) {
          return apt.preferred_dates.some((pd) => pd.startsWith(dateString));
        }
        return false;
      });

      const hasPreferredDate = dayAppointments.some(
        (apt) => apt.preferred_dates?.some((pd) => pd.startsWith(dateString))
      );
      const hasBookedAppointment = dayAppointments.some(
        (apt) => apt.status === 'booked' && apt.booked_date?.startsWith(dateString)
      );
      const hasChecked = dayAppointments.some(
        (apt) => apt.status === 'checking' || apt.status === 'pending'
      );

      days.push({
        date,
        dateString,
        isCurrentMonth: true,
        hasPreferredDate,
        hasBookedAppointment,
        hasChecked,
        appointments: dayAppointments,
      });
    }

    // Add next month's leading days to complete the grid
    const remainingDays = 42 - days.length; // 6 rows x 7 days
    for (let day = 1; day <= remainingDays; day++) {
      const date = new Date(year, month + 1, day);
      days.push({
        date,
        dateString: date.toISOString().split('T')[0],
        isCurrentMonth: false,
        hasPreferredDate: false,
        hasBookedAppointment: false,
        hasChecked: false,
        appointments: [],
      });
    }

    return days;
  }, [currentDate, appointments]);

  const handleDayClick = (dayData: DayData) => {
    if (dayData.appointments.length > 0) {
      setSelectedDate(dayData.dateString);
      setIsDetailModalOpen(true);
      if (onDateClick) {
        onDateClick(dayData.dateString);
      }
    }
  };

  const selectedDayData = useMemo(() => {
    if (!selectedDate) return null;
    return calendarDays.find((day) => day.dateString === selectedDate);
  }, [selectedDate, calendarDays]);

  const weekDays = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];

  return (
    <div className="space-y-4">
      {/* Calendar Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold text-dark-100 flex items-center gap-2">
          <CalendarIcon className="w-5 h-5 text-primary-500" />
          {monthYear}
        </h3>
        <div className="flex gap-2">
          <Button onClick={previousMonth} variant="outline" size="sm">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button onClick={nextMonth} variant="outline" size="sm">
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Calendar Grid */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-7 gap-1">
            {/* Week day headers */}
            {weekDays.map((day) => (
              <div
                key={day}
                className="text-center text-sm font-medium text-dark-400 py-2"
              >
                {day}
              </div>
            ))}

            {/* Calendar days */}
            {calendarDays.map((dayData, index) => {
              const isToday =
                dayData.dateString === new Date().toISOString().split('T')[0];
              const hasActivity =
                dayData.hasPreferredDate || dayData.hasBookedAppointment || dayData.hasChecked;

              return (
                <button
                  key={index}
                  onClick={() => handleDayClick(dayData)}
                  disabled={!hasActivity}
                  className={cn(
                    'relative aspect-square p-2 rounded-lg text-sm transition-all',
                    'flex flex-col items-center justify-center',
                    dayData.isCurrentMonth ? 'text-dark-100' : 'text-dark-600',
                    hasActivity && 'cursor-pointer hover:bg-dark-800',
                    !hasActivity && 'cursor-default',
                    isToday && 'ring-2 ring-primary-500 ring-opacity-50',
                    selectedDate === dayData.dateString && 'bg-dark-800'
                  )}
                >
                  <span className={cn('mb-1', isToday && 'font-bold text-primary-400')}>
                    {dayData.date.getDate()}
                  </span>

                  {/* Activity indicators */}
                  {hasActivity && (
                    <div className="flex gap-1 absolute bottom-1">
                      {dayData.hasBookedAppointment && (
                        <CheckCircle2 className="w-3 h-3 text-green-500" />
                      )}
                      {dayData.hasPreferredDate && !dayData.hasBookedAppointment && (
                        <Circle className="w-3 h-3 text-blue-500 fill-blue-500" />
                      )}
                      {dayData.hasChecked && !dayData.hasBookedAppointment && (
                        <Clock className="w-3 h-3 text-yellow-500" />
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-4 pt-4 border-t border-dark-700 flex flex-wrap gap-4 text-sm">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <span className="text-dark-300">Alınmış Randevu</span>
            </div>
            <div className="flex items-center gap-2">
              <Circle className="w-4 h-4 text-blue-500 fill-blue-500" />
              <span className="text-dark-300">Tercih Edilen Tarih</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-yellow-500" />
              <span className="text-dark-300">Kontrol Ediliyor</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Day Detail Modal */}
      <Modal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        title={`Randevular - ${selectedDate ? new Date(selectedDate).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' }) : ''}`}
      >
        {selectedDayData && (
          <div className="space-y-3">
            {selectedDayData.appointments.map((apt) => (
              <Card key={apt.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-dark-100">
                        {apt.country_code} - {apt.centres.join(', ')}
                      </p>
                      <p className="text-sm text-dark-400">
                        {apt.person_count} kişi - {apt.visa_category}
                      </p>
                    </div>
                    <span
                      className={cn(
                        'px-2 py-1 rounded text-xs font-medium',
                        apt.status === 'booked' && 'bg-green-500/20 text-green-400',
                        apt.status === 'pending' && 'bg-blue-500/20 text-blue-400',
                        apt.status === 'checking' && 'bg-yellow-500/20 text-yellow-400',
                        apt.status === 'failed' && 'bg-red-500/20 text-red-400'
                      )}
                    >
                      {apt.status === 'booked' && 'Alındı'}
                      {apt.status === 'pending' && 'Beklemede'}
                      {apt.status === 'checking' && 'Kontrol Ediliyor'}
                      {apt.status === 'failed' && 'Başarısız'}
                    </span>
                  </div>

                  {apt.status === 'booked' && apt.booked_date && (
                    <div className="text-sm text-dark-300">
                      <span className="font-medium">Randevu Tarihi:</span>{' '}
                      {new Date(apt.booked_date).toLocaleString('tr-TR')}
                    </div>
                  )}

                  {apt.preferred_dates && apt.preferred_dates.length > 0 && (
                    <div className="text-sm text-dark-300 mt-2">
                      <span className="font-medium">Tercih Edilen Tarihler:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {apt.preferred_dates.map((date, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-1 bg-dark-800 rounded text-xs"
                          >
                            {new Date(date).toLocaleDateString('tr-TR')}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
