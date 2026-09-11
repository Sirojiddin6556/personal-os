'use client';

import { useState, useEffect } from 'react';
import { ParsedQuickAdd } from '@/types/ai';
import { TaskPriority } from '@/types/domain';

export function useParseInput(rawInput: string): {
  parsed: ParsedQuickAdd | null;
  isParsing: boolean;
} {
  const [parsed, setParsed] = useState<ParsedQuickAdd | null>(null);
  const [isParsing, setIsParsing] = useState(false);

  useEffect(() => {
    if (!rawInput.trim()) {
      setParsed(null);
      setIsParsing(false);
      return;
    }

    setIsParsing(true);
    const timer = setTimeout(() => {
      const text = rawInput.trim();

      // 1. Detect Intent
      let intent: 'task' | 'event' | 'expense' | 'note' = 'task';
      const expenseMatch = text.match(/(\d+[\s\d]*)\s*(?:₽|руб|rub|\$|€)/i) || text.match(/(купил|потратил|оплатил|расход)/i);
      const eventMatch = text.match(/(митинг|встреча|созвон|вебинар|конференция|в\s+\d{1,2}:\d{2})/i);
      const noteMatch = text.match(/^(заметка|идея|мысль|заметка:)/i);

      if (expenseMatch) {
        intent = 'expense';
      } else if (eventMatch) {
        intent = 'event';
      } else if (noteMatch) {
        intent = 'note';
      }

      // 2. Detect Priority
      let priority: TaskPriority = 'medium';
      if (/!(критично|critical|p0|срочно)/i.test(text)) {
        priority = 'critical';
      } else if (/!(high|важно|p1|высокий)/i.test(text)) {
        priority = 'high';
      } else if (/!(med|medium|средний|p2)/i.test(text)) {
        priority = 'medium';
      } else if (/!(low|низкий|p3)/i.test(text)) {
        priority = 'low';
      }

      // 3. Detect Project / Tag
      const projectMatch = text.match(/#([\w\u0400-\u04FF_-]+)/);
      const project = projectMatch ? projectMatch[1] : undefined;

      // 4. Detect Date / Due
      let dueDate: string | undefined;
      if (/сегодня/i.test(text)) {
        dueDate = 'Сегодня, 18:00';
      } else if (/завтра/i.test(text)) {
        dueDate = 'Завтра, 12:00';
      } else if (/пятниц/i.test(text)) {
        dueDate = 'Пятница, 18:00';
      } else if (/понедельник/i.test(text)) {
        dueDate = 'Понедельник, 10:00';
      }

      // 5. Detect Time
      const timeMatch = text.match(/(\d{1,2}:\d{2})/);
      const time = timeMatch ? timeMatch[1] : undefined;
      if (time && dueDate) {
        dueDate = `${dueDate.split(',')[0]}, ${time}`;
      }

      // 6. Detect Expense details
      let amount: number | undefined;
      let currency = 'RUB';
      const numberExtract = text.match(/(\d+(?:\s\d+)*)/);
      if (intent === 'expense' && numberExtract) {
        amount = parseInt(numberExtract[1].replace(/\s+/g, ''), 10);
      }

      // Clean title from special syntax
      let cleanTitle = text
        .replace(/#([\w\u0400-\u04FF_-]+)/g, '')
        .replace(/!(критично|critical|p0|срочно|high|важно|p1|высокий|med|medium|средний|p2|low|низкий|p3)/gi, '')
        .replace(/\s+/g, ' ')
        .trim();

      setParsed({
        intent,
        title: cleanTitle || text,
        due_date: dueDate,
        priority,
        project,
        amount,
        currency,
        account: intent === 'expense' ? 'Основная карта' : undefined,
        category: intent === 'expense' ? 'Повседневные расходы' : undefined,
        time,
        confidence: 0.95,
      });

      setIsParsing(false);
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [rawInput]);

  return { parsed, isParsing };
}

export function useCreateTask() {
  const [isPending, setIsPending] = useState(false);
  return {
    isPending,
    mutateAsync: async (taskData: {
      title: string;
      priority?: TaskPriority;
      due_at?: string;
      project?: string;
    }) => {
      setIsPending(true);
      await new Promise((resolve) => setTimeout(resolve, 200));
      setIsPending(false);
      return { id: `task-${Date.now()}`, ...taskData };
    },
  };
}

export function useCreateEvent() {
  const [isPending, setIsPending] = useState(false);
  return {
    isPending,
    mutateAsync: async (eventData: { title: string; start: string; end?: string }) => {
      setIsPending(true);
      await new Promise((resolve) => setTimeout(resolve, 200));
      setIsPending(false);
      return { id: `event-${Date.now()}`, ...eventData };
    },
  };
}

export function useCreateTransaction() {
  const [isPending, setIsPending] = useState(false);
  return {
    isPending,
    mutateAsync: async (txData: {
      amount: number;
      category: string;
      account_name: string;
      currency?: string;
    }) => {
      setIsPending(true);
      await new Promise((resolve) => setTimeout(resolve, 200));
      setIsPending(false);
      return { id: `tx-${Date.now()}`, ...txData };
    },
  };
}
