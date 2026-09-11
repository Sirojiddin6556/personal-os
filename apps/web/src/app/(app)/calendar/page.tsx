'use client';

import React, { useState, useRef, useMemo } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin, { DateClickArg } from '@fullcalendar/interaction';
import { useCalendarEvents, useGoogleSyncStatus } from '@/hooks/useCalendar';
import { useUIStore } from '@/stores/ui-store';
import { formatDateShort } from '@/lib/utils';
import Link from 'next/link';

export default function CalendarPage() {
  const calendarRef = useRef<FullCalendar | null>(null);
  const { openQuickAdd } = useUIStore();

  // Range state for events query (default: current month +/- 1 week)
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>(() => {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
    return {
      from: start.toISOString(),
      to: end.toISOString(),
    };
  });

  const { events, isLoading, refetch } = useCalendarEvents(dateRange.from, dateRange.to);
  const { status: syncStatus, lastSync, isSyncing, triggerSync } = useGoogleSyncStatus();

  // Transform domain CalendarEvents into FullCalendar event objects
  const fullCalendarEvents = useMemo(() => {
    return events.map((ev) => {
      const isTaskTimeblock = Boolean(ev.task_id);
      return {
        id: ev.id,
        title: ev.title,
        start: ev.start_time || ev.start,
        end: ev.end_time || ev.end,
        allDay: ev.is_all_day,
        backgroundColor: isTaskTimeblock ? '#6366f1' : '#0ea5e9',
        borderColor: isTaskTimeblock ? '#4f46e5' : '#0284c7',
        textColor: '#ffffff',
        extendedProps: {
          description: ev.description,
          location: ev.location,
          isExternal: ev.is_external,
          isTaskTimeblock,
          taskId: ev.task_id,
        },
      };
    });
  }, [events]);

  const handleDatesSet = (arg: { startStr: string; endStr: string }) => {
    setDateRange({
      from: arg.startStr,
      to: arg.endStr,
    });
  };

  const handleDateClick = (arg: DateClickArg) => {
    // Open Quick Add Modal prefilled for calendar event
    openQuickAdd('event');
  };

  const handleEventClick = (clickInfo: { event: { title: string; extendedProps: Record<string, unknown> } }) => {
    const { title, extendedProps } = clickInfo.event;
    if (extendedProps.isTaskTimeblock && extendedProps.taskId) {
      useUIStore.getState().openTaskDetail(extendedProps.taskId as string);
    } else {
      alert(`Событие: ${title}\n${(extendedProps.description as string) || 'Без описания'}`);
    }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Google Sync Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">
            Календарь и расписание
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Интеграция событий, рабочих тайм-блоков и синхронизация с Google Calendar
          </p>
        </div>

        {/* Google Calendar Sync Badge & Action */}
        <div className="flex items-center gap-3 bg-surface-muted border border-border px-3.5 py-2 rounded-xl text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                syncStatus === 'connected'
                  ? 'bg-status-success animate-pulse'
                  : syncStatus === 'syncing' || isSyncing
                  ? 'bg-status-warning animate-ping'
                  : syncStatus === 'error'
                  ? 'bg-status-error'
                  : 'bg-text-muted'
              }`}
            />
            <span className="font-medium text-text-primary">
              Google Calendar:
            </span>
            <span className="text-text-muted capitalize">
              {isSyncing || syncStatus === 'syncing'
                ? 'Синхронизация...'
                : syncStatus === 'connected'
                ? 'Подключен'
                : syncStatus === 'error'
                ? 'Ошибка'
                : 'Не подключен'}
            </span>
          </div>

          {lastSync && (
            <span className="hidden md:inline text-[11px] text-text-muted border-l border-border pl-2">
              посл: {formatDateShort(lastSync)}
            </span>
          )}

          {syncStatus === 'connected' ? (
            <button
              onClick={() => triggerSync()}
              disabled={isSyncing}
              title="Запустить синхронизацию"
              className="p-1 hover:bg-surface rounded text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
            >
              <svg className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
              </svg>
            </button>
          ) : (
            <Link
              href="/settings/integrations"
              className="text-primary hover:underline font-semibold text-[11px]"
            >
              Настроить
            </Link>
          )}
        </div>
      </div>

      {/* Legend & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-[#0ea5e9]" />
            <span className="text-text-secondary font-medium">События календаря</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-[#6366f1]" />
            <span className="text-text-secondary font-medium">Тайм-блоки задач</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => openQuickAdd('event')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary hover:bg-primary-600 text-white font-semibold shadow-xs transition-colors"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Добавить событие</span>
          </button>
        </div>
      </div>

      {/* FullCalendar Component Container */}
      <div className="bg-surface border border-border rounded-2xl p-4 sm:p-6 shadow-sm min-h-[650px] relative">
        {isLoading && (
          <div className="absolute inset-0 bg-surface/50 backdrop-blur-[1px] flex items-center justify-center z-10 rounded-2xl">
            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
        )}

        <FullCalendar
          ref={calendarRef}
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="timeGridWeek"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay',
          }}
          locale="ru"
          buttonText={{
            today: 'Сегодня',
            month: 'Месяц',
            week: 'Неделя',
            day: 'День',
          }}
          firstDay={1} // Monday
          allDaySlot={true}
          slotMinTime="07:00:00"
          slotMaxTime="23:00:00"
          slotDuration="00:30:00"
          nowIndicator={true}
          selectable={true}
          editable={true}
          events={fullCalendarEvents}
          datesSet={handleDatesSet}
          dateClick={handleDateClick}
          eventClick={handleEventClick}
          height="auto"
        />
      </div>
    </div>
  );
}
