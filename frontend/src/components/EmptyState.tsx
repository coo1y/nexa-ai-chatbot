import { Calculator, FileText, Globe, Image, Sparkles, Code2 } from 'lucide-react';

const SUGGESTIONS = [
  { Icon: Globe, label: "What's new in AI this week?", prompt: "What's the latest news in AI this week?" },
  {
    Icon: Code2,
    label: 'Write a Python function',
    prompt: 'Write a Python function that checks whether a string is a palindrome, with tests.',
  },
  {
    Icon: Calculator,
    label: 'Convert & calculate',
    prompt: 'Convert 26.2 miles to km, then calculate my pace for a 4h15m marathon.',
  },
  {
    Icon: FileText,
    label: 'Summarize a document',
    prompt: 'Summarize the attached document in 5 bullet points.',
  },
  { Icon: Image, label: 'Analyze an image', prompt: 'What is in this image? Describe it in detail.' },
  {
    Icon: Sparkles,
    label: 'Explain a concept',
    prompt: 'Explain how transformers work, step by step, for a beginner.',
  },
];

export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="empty-state">
      <div className="empty-state__logo" aria-hidden>
        N
      </div>
      <h1>How can I help today?</h1>
      <p>Chat, search the web, analyze documents and images, crunch numbers, or get coding help.</p>
      <div className="suggestions">
        {SUGGESTIONS.map(({ Icon, label, prompt }) => (
          <button key={label} type="button" className="suggestion" onClick={() => onPick(prompt)}>
            <Icon size={16} aria-hidden />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
