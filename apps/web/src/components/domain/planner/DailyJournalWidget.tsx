'use client';

import React, { useState, useEffect } from 'react';
import { DailyJournal, useSaveDailyJournal } from '@/hooks/usePlanner';

interface DailyJournalWidgetProps {
  journal: DailyJournal | null;
  targetDate: string;
}

const MOODS = [
  { key: 'great', label: '🔥 Продуктивно', emoji: '🔥' },
  { key: 'happy', label: '😊 Отлично', emoji: '😊' },
  { key: 'calm', label: '😌 Спокойно', emoji: '😌' },
  { key: 'tired', label: '😴 Устал', emoji: '😴' },
  { key: 'stress', label: '🤯 Стресс', emoji: '🤯' },
];

export function DailyJournalWidget({ journal, targetDate }: DailyJournalWidgetProps) {
  const saveMutation = useSaveDailyJournal();

  const [morningIntention, setMorningIntention] = useState('');
  const [gratitude, setGratitude] = useState('');
  const [notes, setNotes] = useState('');
  const [eveningReflection, setEveningReflection] = useState('');
  const [mood, setMood] = useState<string | null>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [isSavedRecently, setIsSavedRecently] = useState(false);

  useEffect(() => {
    if (journal) {
      setMorningIntention(journal.morning_intention || '');
      setGratitude(journal.gratitude || '');
      setNotes(journal.notes || '');
      setEveningReflection(journal.evening_reflection || '');
      setMood(journal.mood || null);
      setRating(journal.productivity_rating || null);
    } else {
      setMorningIntention('');
      setGratitude('');
      setNotes('');
      setEveningReflection('');
      setMood(null);
      setRating(null);
    }
  }, [journal, targetDate]);

  const handleSave = async () => {
    await saveMutation.mutateAsync({
      entry_date: targetDate,
      morning_intention: morningIntention,
      gratitude: gratitude,
      notes: notes,
      evening_reflection: eveningReflection,
      mood: mood,
      productivity_rating: rating,
    });
    setIsSavedRecently(true);
    setTimeout(() => setIsSavedRecently(false), 2500);
  };

  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-bold text-sm">
            📖
          </div>
          <div>
            <h3 className="text-sm font-bold text-text-primary">Дневник & Рефлексия</h3>
            <p className="text-xs text-text-muted">Заметки, фокус и итоги дня</p>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary-600 disabled:opacity-50 transition-all flex items-center gap-1.5"
        >
          {isSavedRecently ? '✓ Сохранено' : saveMutation.isPending ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>

      <div className="space-y-3">
        {/* Morning Intention / Focus */}
        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-1">
            🎯 Главный фокус дня (Цель #1):
          </label>
          <input
            type="text"
            placeholder="Что самое важное нужно сделать сегодня?"
            value={morningIntention}
            onChange={(e) => setMorningIntention(e.target.value)}
            className="w-full px-3 py-2 text-xs bg-surface-muted border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-hidden focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Gratitude */}
        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-1">
            🙏 За что я благодарен:
          </label>
          <input
            type="text"
            placeholder="Люди, события или возможности дня..."
            value={gratitude}
            onChange={(e) => setGratitude(e.target.value)}
            className="w-full px-3 py-2 text-xs bg-surface-muted border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-hidden focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Daily Notes */}
        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-1">
            📝 Заметки & Мысли дня:
          </label>
          <textarea
            rows={3}
            placeholder="Идеи, выводы, важные детали..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full px-3 py-2 text-xs bg-surface-muted border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-hidden focus:ring-1 focus:ring-primary resize-none"
          />
        </div>

        {/* Evening Reflection & Rating */}
        <div className="pt-2 border-t border-border space-y-3">
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-1">
              🌙 Итоги и вечерняя рефлексия:
            </label>
            <textarea
              rows={2}
              placeholder="Что удалось выполнить? Что можно улучшить завтра?"
              value={eveningReflection}
              onChange={(e) => setEveningReflection(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-surface-muted border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:outline-hidden focus:ring-1 focus:ring-primary resize-none"
            />
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            {/* Mood selector */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-semibold text-text-muted">Настроение:</span>
              {MOODS.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => setMood(m.key)}
                  className={`px-2 py-1 text-xs rounded-lg border transition-all ${
                    mood === m.key
                      ? 'bg-purple-500/10 border-purple-500 text-purple-600 dark:text-purple-300 font-bold scale-105'
                      : 'border-border bg-surface hover:bg-surface-muted text-text-secondary'
                  }`}
                  title={m.label}
                >
                  {m.emoji}
                </button>
              ))}
            </div>

            {/* Rating 1-5 */}
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-semibold text-text-muted mr-1">Оценка:</span>
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  className={`text-sm transition-transform hover:scale-125 ${
                    rating && rating >= star ? 'text-amber-400' : 'text-text-muted opacity-40'
                  }`}
                >
                  ★
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
