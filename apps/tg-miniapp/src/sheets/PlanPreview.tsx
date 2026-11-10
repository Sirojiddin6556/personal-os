import { IconSpark, Sheet, useToast } from '../components/ui';
import { dueLabel, time } from '../lib/format';
import { useApplyPlan, useTasks } from '../lib/queries';
import type { AIPlan } from '../lib/types';

const str = (v: unknown) => (typeof v === 'string' ? v : undefined);

/** Human-readable line for one proposed tool call from the AI Tool Gateway. */
export function describeChange(c: Record<string, unknown>, taskTitle: (id?: string) => string | undefined) {
  const tool = str(c.tool_name) ?? 'change';
  switch (tool) {
    case 'create_time_block': {
      const start = str(c.start_at);
      const end = str(c.end_at);
      return {
        op: 'Новый тайм-блок',
        title: taskTitle(str(c.task_id)) ?? str(c.label) ?? 'Фокус-блок',
        meta: start && end ? `${time(start)}–${time(end)}` : '',
      };
    }
    case 'move_task':
    case 'reschedule_task':
      return {
        op: 'Перенос задачи',
        title: taskTitle(str(c.task_id)) ?? 'Задача',
        meta: str(c.scheduled_at) ? dueLabel(str(c.scheduled_at)) : str(c.new_status) ?? '',
      };
    case 'create_task':
      return { op: 'Новая задача', title: str(c.title) ?? 'Задача', meta: str(c.due_at) ? dueLabel(str(c.due_at)) : '' };
    default:
      return { op: tool, title: str(c.title) ?? str(c.label) ?? '', meta: '' };
  }
}

export function PlanPreviewSheet({ plan, onClose }: { plan: AIPlan; onClose: () => void }) {
  const apply = useApplyPlan();
  const tasks = useTasks();
  const toast = useToast();
  const titleOf = (id?: string) => tasks.data?.find((t) => t.id === id)?.title;

  return (
    <Sheet label="AI-план дня" onClose={onClose}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--link)' }}>
        <IconSpark size={20} />
        <h2 className="sheet-title" style={{ color: 'var(--text)' }}>План на день</h2>
      </div>
      <div className="small muted" style={{ lineHeight: 1.4 }}>
        {plan.ai_explanation || 'AI предлагает изменения.'} Ничего не сохранится, пока вы не нажмёте «Применить».
      </div>
      {plan.changes.map((c, i) => {
        const d = describeChange(c, titleOf);
        return (
          <div key={i} className="plan-item on" style={{ padding: '10px 12px' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="xsmall" style={{ fontWeight: 600, color: 'var(--ok)' }}>{d.op}</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{d.title}</div>
              {d.meta && <div className="xsmall muted">{d.meta}</div>}
            </div>
          </div>
        );
      })}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" className="btn ghost" style={{ flex: 1 }} onClick={onClose}>Не сейчас</button>
        <button
          type="button"
          className="btn"
          style={{ flex: 2 }}
          disabled={apply.isPending}
          onClick={() =>
            apply.mutate(plan.plan_id, {
              onSuccess: () => { toast('План применён'); onClose(); },
              onError: (e) => toast(e instanceof Error ? e.message : 'Не удалось применить', 'error'),
            })
          }
        >
          {apply.isPending ? 'Применяю…' : `Применить (${plan.changes.length})`}
        </button>
      </div>
    </Sheet>
  );
}
