import { useEffect, useRef } from 'react';

import { lastIndexOfRole } from '../lib/conversation';
import type { Conversation } from '../state/types';
import { MessageItem } from './MessageItem';

export function MessageList({ conversation, busy }: { conversation: Conversation; busy: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const lastUser = lastIndexOfRole(conversation.messages, 'user');
  const lastMessage = conversation.messages[conversation.messages.length - 1];

  useEffect(() => {
    stickToBottom.current = true;
  }, [conversation.id]);

  useEffect(() => {
    const el = container.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [conversation.messages.length, lastMessage?.content, lastMessage?.tools?.length]);

  return (
    <div
      className="message-list"
      ref={container}
      onScroll={(e) => {
        const el = e.currentTarget;
        stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
      role="log"
      aria-live="polite"
      aria-label="Conversation"
    >
      <div className="message-list__inner">
        {conversation.messages.map((message, index) => (
          <MessageItem
            key={message.id}
            message={message}
            isLatest={index === conversation.messages.length - 1}
            isLatestUser={index === lastUser}
            busy={busy}
          />
        ))}
      </div>
    </div>
  );
}
