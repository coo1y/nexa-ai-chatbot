import {
  AlertCircle,
  Calculator,
  Calendar,
  Check,
  Globe,
  Loader2,
  Ruler,
  ShieldAlert,
  Table,
  Wrench,
} from 'lucide-react';

import type { ToolActivity } from '../state/types';

const ICONS: Record<string, typeof Wrench> = {
  web_search: Globe,
  calculator: Calculator,
  unit_convert: Ruler,
  datetime: Calendar,
  data_process: Table,
};

function describeInput(tool: ToolActivity): string {
  const input = tool.input ?? {};
  if (typeof input.query === 'string') return `“${input.query}”`;
  if (typeof input.expression === 'string') return input.expression;
  if (tool.name === 'unit_convert') return `${input.value} ${input.from_unit} → ${input.to_unit}`;
  if (typeof input.operation === 'string') return input.operation;
  return '';
}

export function ToolActivityList({ tools }: { tools: ToolActivity[] }) {
  if (tools.length === 0) return null;
  return (
    <ul className="tool-activity" aria-label="Tool activity">
      {tools.map((tool) => {
        const Icon = ICONS[tool.name] ?? Wrench;
        return (
          <li key={tool.id} className={`tool tool--${tool.status}`} data-testid="tool-activity">
            <Icon size={14} aria-hidden />
            <span className="tool__label">{tool.label}</span>
            <span className="tool__detail">
              {tool.status === 'running' ? describeInput(tool) : (tool.summary ?? describeInput(tool))}
            </span>
            <span className="tool__status" aria-label={tool.status}>
              {tool.status === 'running' && <Loader2 size={14} className="spin" />}
              {tool.status === 'success' && <Check size={14} />}
              {tool.status === 'error' && <AlertCircle size={14} />}
              {tool.status === 'blocked' && <ShieldAlert size={14} />}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
