import React from 'react';
import { TodayDashboard } from '@/components/domain/today/TodayDashboard';

export const metadata = {
  title: 'Сегодня | Personal OS',
  description: 'Дашборд текущего дня: утренний брифинг, топ задачи, расписание и бюджет',
};

// Server Component Shell
export default function TodayPage() {
  return (
    <div className="w-full h-full">
      <TodayDashboard />
    </div>
  );
}
