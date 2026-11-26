import { BarChart3, CalendarDays, FlaskConical, MessageCircle, Route } from 'lucide-react';

const icons = { chat: MessageCircle, grade: CalendarDays, metrics: BarChart3, comparison: FlaskConical, route: Route };
export type SectionId = keyof typeof icons;

export function SectionIcon({ section }: { section: SectionId }) {
  const Icon = icons[section];
  return <span className="section-icon" data-section={section} aria-hidden="true">
    <Icon size={17} strokeWidth={1.85} />
  </span>;
}
