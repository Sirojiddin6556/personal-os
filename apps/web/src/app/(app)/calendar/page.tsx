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

  const [selectedEvent, setSelectedEvent] = useState<{
    title: string;
    description?: string;
    start?: string;
    end?: string;
    isExternal?: boolean;
  } | null>(null);

  const handleEventClick = (clickInfo: {
    event: {
      title: string;
      startStr: string;
      endStr: string;
      extendedProps: Record<string, unknown>;
    };
  }) => {
    const { title, startStr, endStr, extendedProps } = clickInfo.event;
    if (extendedProps.isTaskTimeblock && extendedProps.taskId) {
      useUIStore.getState().openTaskDetail(extendedProps.taskId as string);
    } else {
      setSelectedEvent({
        title,
        description: (extendedProps.description as string) || undefined,
        start: startStr,
        end: endStr,
        isExternal: !!extendedProps.isExternal,
      });
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
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-surface-muted border border-border px-3.5 py-2 rounded-xl text-xs">
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
                ? 'Требуется действие'
                : 'Не подключен'}
            </span>
            {lastSync && (
              <span className="hidden md:inline text-[11px] text-text-muted border-l border-border pl-2">
                посл: {formatDateShort(lastSync)}
              </span>
            )}
          </div>

          {/* Explicit Sync Button with text */}
          <button
            onClick={() => triggerSync()}
            disabled={isSyncing}
            aria-label="Синхронизировать с Google Calendar"
            className="flex items-center gap-2 px-3.5 py-2 bg-primary hover:bg-primary-600 active:scale-95 text-white rounded-xl text-xs font-semibold shadow-sm transition-all disabled:opacity-50 cursor-pointer"
          >
            <svg className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            <span>{isSyncing ? 'Синхронизация...' : 'Синхронизировать'}</span>
          </button>

          {syncStatus !== 'connected' && syncStatus !== 'syncing' && (
            <Link
              href="/settings/integrations"
              className="text-xs text-primary hover:underline font-medium px-2 py-1"
            >
              Настройки →
            </Link>
          )}
        </div>
      </div>

      {/* Helpful banner when Google Calendar API is disabled or encountering permission error */}
      {syncStatus === 'error' && (
        <div className="bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 p-3.5 rounded-xl text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>
              В Google Cloud Console для проекта <b>811023701981</b> не активирован сервис Google Calendar API.{' '}
              <a
                href="https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=811023701981"
                target="_blank"
                rel="noreferrer"
                className="underline font-bold text-primary ml-1"
              >
                Включить в 1 клик в Google Console ↗
              </a>
            </span>
          </div>
          <button
            onClick={() => triggerSync()}
            disabled={isSyncing}
            className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-bold shrink-0 self-start sm:self-auto cursor-pointer"
          >
            {isSyncing ? 'Проверка...' : 'Повторить синхронизацию'}
          </button>
        </div>
      )}

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

      {/* Event Detail Modal Dialog */}
      {selectedEvent && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="calendar-event-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs"
        >
          <div className="w-full max-w-md bg-surface border border-border rounded-2xl p-5 shadow-xl space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="calendar-event-dialog-title" className="text-base font-bold text-text-primary">
                  {selectedEvent.title}
                </h2>
                {selectedEvent.isExternal && (
                  <span className="text-[10px] text-text-muted mt-0.5 inline-block">
                    Синхронизировано с Google Calendar
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                aria-label="Закрыть"
                className="text-text-muted hover:text-text-primary p-1 rounded-lg hover:bg-surface-muted transition-colors text-sm font-bold"
              >
                ×
              </button>
            </div>

            {selectedEvent.description && (
              <p className="text-xs text-text-secondary whitespace-pre-wrap bg-surface-muted/60 p-3 rounded-xl border border-border">
                {selectedEvent.description}
              </p>
            )}

            <div className="flex items-center justify-between text-xs text-text-muted pt-2 border-t border-border">
              <span>{selectedEvent.start?.slice(0, 16).replace('T', ' ')}</span>
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                className="px-3.5 py-1.5 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary-600 transition-colors"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
