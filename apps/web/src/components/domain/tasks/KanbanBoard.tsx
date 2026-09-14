'use client';

import React, { useState } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { KanbanColumn } from './KanbanColumn';
import { TaskCard } from './TaskCard';
import { Task, TaskStatus } from '@/types/domain';
import { useUIStore } from '@/stores/ui-store';

export interface KanbanBoardProps {
  tasks: Task[];
  onMoveTask: (taskId: string, targetStatus: TaskStatus, newIndex?: number) => void;
  onCompleteTask: (id: string) => void;
  onEditTask: (id: string) => void;
  onDeleteTask?: (id: string) => void;
}

export const KANBAN_COLUMNS: { id: TaskStatus; title: string; dotColor: string }[] = [
  { id: TaskStatus.INBOX, title: 'Входящие (Inbox)', dotColor: '#6366f1' },
  { id: TaskStatus.TODO, title: 'К выполнению', dotColor: '#0ea5e9' },
  { id: TaskStatus.SCHEDULED, title: 'Запланировано', dotColor: '#8b5cf6' },
  { id: TaskStatus.IN_PROGRESS, title: 'В работе', dotColor: '#f59e0b' },
  { id: TaskStatus.WAITING, title: 'Ожидание', dotColor: '#ec4899' },
];

export function KanbanBoard({
  tasks,
  onMoveTask,
  onCompleteTask,
  onEditTask,
  onDeleteTask,
}: KanbanBoardProps) {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const { openQuickAdd } = useUIStore();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveTaskId(String(event.active.id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTaskId(null);

    if (!over) return;

    const sourceTaskId = String(active.id);
    const overId = String(over.id);

    // 1. Check if dropped directly onto a column container
    const targetColumn = KANBAN_COLUMNS.find((col) => col.id === overId || String(col.id) === overId);
    if (targetColumn) {
      onMoveTask(sourceTaskId, targetColumn.id);
      return;
    }

    // 2. Check if dropped over another task
    const overTask = tasks.find((t) => t.id === overId);
    if (overTask) {
      onMoveTask(sourceTaskId, overTask.status as TaskStatus);
    }
  };


  const activeTask = activeTaskId ? tasks.find((t) => t.id === activeTaskId) : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div
        className="flex h-[calc(100vh-140px)] gap-4 overflow-x-auto pb-4 pt-1 px-1 select-none"
        role="region"
        aria-label="Канбан доска задач"
      >
        {KANBAN_COLUMNS.map((col) => (
          <KanbanColumn
            key={col.id}
            id={col.id}
            title={col.title}
            dotColor={col.dotColor}
            tasks={tasks.filter((t) => t.status === col.id)}
            onAddTask={() => openQuickAdd('task')}
            onCompleteTask={onCompleteTask}
            onEditTask={onEditTask}
            onDeleteTask={onDeleteTask}
            onStatusChange={onMoveTask}
          />
        ))}
      </div>

      {/* Floating Drag Overlay */}
      <DragOverlay>
        {activeTask ? (
          <div className="w-[286px] rotate-2 shadow-2xl opacity-90">
            <TaskCard
              task={activeTask}
              onComplete={onCompleteTask}
              onEdit={onEditTask}
              onDelete={onDeleteTask}
              isDragging
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

export default KanbanBoard;
