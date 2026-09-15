'use client';

import { useState, useEffect, useMemo } from 'react';
import { ParsedQuickAdd } from '@/types/ai';
import { TaskPriority, Priority, TaskStatus, TransactionType } from '@/types/domain';
import { useCreateTask } from '@/hooks/useTasks';
import { useCreateEvent } from '@/hooks/useCalendar';
import { useCreateTransaction, useAccounts, useCategories } from '@/hooks/useFinance';
import { useCreateNote } from '@/hooks/useNotes';

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
      const isExpense = /(\d+[\s\d]*)\s*(?:₽|руб|сум|uzs|rub|\$|€)/i.test(text) ||
        /\b(купил|потратил|оплатил|расход|чек|обед|такси|кофе|покупка|ужин|билет)\b/i.test(text);
      const isEvent = /\b(митинг|встреча|созвон|вебинар|конференция|зум|zoom|звонок|стоматолог|тренировка|встретиться|собрание)\b/i.test(text) ||
        /\bв\s+\d{1,2}:\d{2}\b/i.test(text);
      const isNote = /^(заметка|идея|мысль|записать|memo|note):?/i.test(text);

      if (isNote) {
        intent = 'note';
      } else if (isExpense) {
        intent = 'expense';
      } else if (isEvent) {
        intent = 'event';
      }

      // 2. Detect Priority
      let priority: TaskPriority = 'medium';
      if (/!(критично|critical|p0|срочно|urgent)/i.test(text)) {
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
      const now = new Date();
      let targetDate = new Date();
      let hasDate = false;

      if (/сегодня/i.test(text)) {
        hasDate = true;
      } else if (/завтра/i.test(text)) {
        targetDate.setDate(targetDate.getDate() + 1);
        hasDate = true;
      } else if (/послезавтра/i.test(text)) {
        targetDate.setDate(targetDate.getDate() + 2);
        hasDate = true;
      } else if (/в\s+понедельник/i.test(text)) {
        const day = 1;
        const diff = (day + 7 - targetDate.getDay()) % 7 || 7;
        targetDate.setDate(targetDate.getDate() + diff);
        hasDate = true;
      } else if (/в\s+пятниц/i.test(text)) {
        const day = 5;
        const diff = (day + 7 - targetDate.getDay()) % 7 || 7;
        targetDate.setDate(targetDate.getDate() + diff);
        hasDate = true;
      }

      // 5. Detect Time
      const timeMatch = text.match(/(\d{1,2}):(\d{2})/);
      let timeStr: string | undefined;
      if (timeMatch) {
        const hours = parseInt(timeMatch[1], 10);
        const mins = parseInt(timeMatch[2], 10);
        targetDate.setHours(hours, mins, 0, 0);
        timeStr = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
        hasDate = true;
      } else if (hasDate) {
        targetDate.setHours(18, 0, 0, 0);
        timeStr = '18:00';
      }

      const isoDate = hasDate ? targetDate.toISOString() : undefined;
      const displayDueDate = hasDate
        ? `${targetDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}, ${timeStr || '18:00'}`
        : undefined;

      // 6. Detect Expense details
      let amount: number | undefined;
      let currency = 'UZS';
      if (/₽|руб|rub/i.test(text)) {
        currency = 'RUB';
      } else if (/\$|usd/i.test(text)) {
        currency = 'USD';
      } else if (/€|eur/i.test(text)) {
        currency = 'EUR';
      }

      const numberExtract = text.match(/(\d[\d\s]*\d|\d+)/);
      if (intent === 'expense' && numberExtract) {
        const rawNum = numberExtract[1].replace(/\s+/g, '');
        amount = parseInt(rawNum, 10);
      }

      // Detect Account / Category
      let category = 'Повседневные';
      if (/такси|яндекс|uber|поездка/i.test(text)) category = 'Транспорт';
      else if (/кофе|обед|ужин|кафе|ресторан|продукты|еда/i.test(text)) category = 'Питание';
      else if (/сервер|подписка|софт|хостинг|api/i.test(text)) category = 'Сервисы и IT';
      else if (/книга|курс|обучение/i.test(text)) category = 'Образование';

      // Clean Title
      const cleanTitle = text
        .replace(/^(заметка|идея|мысль|записать|memo|note):?\s*/i, '')
        .replace(/#([\w\u0400-\u04FF_-]+)/g, '')
        .replace(/!(критично|critical|p0|срочно|urgent|high|важно|p1|высокий|med|medium|средний|p2|low|низкий|p3)/gi, '')
        .replace(/\b(сегодня|завтра|послезавтра)\b/gi, '')
        .replace(/\bв\s+\d{1,2}:\d{2}\b/gi, '')
        .replace(/\b\d{1,2}:\d{2}\b/gi, '')
        .replace(/(\d+[\s\d]*)\s*(?:₽|руб|сум|uzs|rub|\$|€)/gi, '')
        .replace(/\s+/g, ' ')
        .trim();

      setParsed({
        intent,
        title: cleanTitle || text,
        due_date: displayDueDate,
        iso_date: isoDate,
        priority,
        project,
        amount,
        currency,
        account: 'Основной счет',
        category,
        time: timeStr,
        confidence: 0.95,
      });

      setIsParsing(false);
    }, 250);

    return () => clearTimeout(timer);
  }, [rawInput]);

  return { parsed, isParsing };
}

export function useQuickAddSubmit() {
  const createTaskMutation = useCreateTask();
  const createEventMutation = useCreateEvent();
  const createTxMutation = useCreateTransaction();
  const createNoteMutation = useCreateNote();
  const { accounts } = useAccounts();
  const { categories } = useCategories();

  const [isSubmitting, setIsSubmitting] = useState(false);

  const submitQuickAdd = async ({
    intent,
    title,
    priority = 'medium',
    dueDate,
    isoDate,
    project,
    amount,
    currency = 'UZS',
    categoryId,
    accountId,
    noteContent,
  }: {
    intent: 'task' | 'event' | 'expense' | 'note';
    title: string;
    priority?: TaskPriority;
    dueDate?: string;
    isoDate?: string;
    project?: string;
    amount?: number;
    currency?: string;
    categoryId?: string;
    accountId?: string;
    noteContent?: string;
  }) => {
    setIsSubmitting(true);
    try {
      if (intent === 'task') {
        const priorityEnum =
          priority === 'critical' || priority === 'urgent'
            ? Priority.P1
            : priority === 'high'
            ? Priority.P2
            : priority === 'low'
            ? Priority.P4
            : Priority.P3;

        await createTaskMutation.mutateAsync({
          title,
          priority: priorityEnum,
          due_date: isoDate || (dueDate ? new Date(dueDate).toISOString() : null),
          status: TaskStatus.TODO,
          tags: project ? [project] : [],
        });
      } else if (intent === 'event') {
        const startIso = isoDate || new Date().toISOString();
        const startObj = new Date(startIso);
        const endObj = new Date(startObj.getTime() + 60 * 60 * 1000); // 1 hour duration default

        await createEventMutation.mutateAsync({
          title,
          start_time: startObj.toISOString(),
          end_time: endObj.toISOString(),
          is_all_day: false,
        });
      } else if (intent === 'expense') {
        const targetAccount =
          accounts.find((a) => a.id === accountId) ||
          accounts[0];

        const targetCategory =
          categories.find((c) => c.id === categoryId) ||
          categories.find((c) => c.name.toLowerCase().includes('повседнев')) ||
          categories[0];

        const amountMinor = Math.round((amount || 0) * 100);

        if (targetAccount) {
          await createTxMutation.mutateAsync({
            account_id: targetAccount.id,
            category_id: targetCategory?.id || null,
            amount_minor: amountMinor > 0 ? amountMinor : 100000,
            currency: currency || targetAccount.currency || 'UZS',
            type: TransactionType.EXPENSE,
            description: title || 'Быстрый расход',
            transaction_date: isoDate || new Date().toISOString(),
          });
        }
      } else if (intent === 'note') {
        await createNoteMutation.mutateAsync({
          title: title || 'Быстрая заметка',
          content_markdown: noteContent || title,
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    submitQuickAdd,
    isSubmitting:
      isSubmitting ||
      createTaskMutation.isPending ||
      createEventMutation.isPending ||
      createTxMutation.isPending ||
      createNoteMutation.isPending,
  };
}
