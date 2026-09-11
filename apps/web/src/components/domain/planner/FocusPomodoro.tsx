'use client';

import React, { useState, useEffect } from 'react';

export function FocusPomodoro() {
  const [minutes, setMinutes] = useState(25);
  const [seconds, setSeconds] = useState(0);
  const [isActive, setIsActive] = useState(false);
  const [focusTask, setFocusTask] = useState('');

  useEffect(() => {
    let interval: any = null;
    if (isActive) {
      interval = setInterval(() => {
        if (seconds > 0) {
          setSeconds((s) => s - 1);
        } else if (minutes > 0) {
          setMinutes((m) => m - 1);
          setSeconds(59);
        } else {
          // Timer finished
          setIsActive(false);
          try {
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification('🎉 Помодоро завершен!', {
                body: focusTask ? `Фокус над «${focusTask}» завершен!` : 'Время для 5-минутного отдыха!',
                icon: '/icon-192.png',
              });
            }
          } catch {}
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isActive, minutes, seconds, focusTask]);

  const resetTimer = (newMin = 25) => {
    setIsActive(false);
    setMinutes(newMin);
    setSeconds(0);
  };

  const formattedTime = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-xs space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center font-bold text-sm">
            ⏱️
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-primary">Фокус Помодоро</h3>
            <p className="text-xs text-text-muted">Режим глубокой концентрации</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => resetTimer(25)}
            className={`px-2 py-0.5 text-xs font-semibold rounded-md ${minutes === 25 && !isActive ? 'bg-rose-500/10 text-rose-600 font-bold' : 'text-text-muted hover:text-text-primary'}`}
          >
            25м
          </button>
          <button
            onClick={() => resetTimer(50)}
            className={`px-2 py-0.5 text-xs font-semibold rounded-md ${minutes === 50 && !isActive ? 'bg-rose-500/10 text-rose-600 font-bold' : 'text-text-muted hover:text-text-primary'}`}
          >
            50м
          </button>
          <button
            onClick={() => resetTimer(5)}
            className={`px-2 py-0.5 text-xs font-semibold rounded-md ${minutes === 5 && !isActive ? 'bg-emerald-500/10 text-emerald-600 font-bold' : 'text-text-muted hover:text-text-primary'}`}
          >
            5м (отдых)
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between p-3 bg-surface-muted rounded-xl gap-3">
        <input
          type="text"
          placeholder="Над чем фокусируемся прямо сейчас?..."
          value={focusTask}
          onChange={(e) => setFocusTask(e.target.value)}
          className="flex-1 px-3 py-1.5 text-xs bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-hidden"
        />

        <div className="font-mono text-xl font-black text-rose-600 dark:text-rose-400 tracking-wider">
          {formattedTime}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => setIsActive(!isActive)}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors text-white ${
              isActive ? 'bg-amber-600 hover:bg-amber-700' : 'bg-rose-600 hover:bg-rose-700'
            }`}
          >
            {isActive ? 'Пауза' : 'Старт'}
          </button>
          <button
            onClick={() => resetTimer(25)}
            className="p-1.5 text-xs text-text-muted hover:text-text-primary transition-colors"
            title="Сбросить"
          >
            ↺
          </button>
        </div>
      </div>
    </div>
  );
}
