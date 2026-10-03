import { useCallback, useEffect, useState } from 'react';
import { PanelLeft } from 'lucide-react';

import { Composer } from './components/Composer';
import { EmptyState } from './components/EmptyState';
import { MessageList } from './components/MessageList';
import { SettingsDialog } from './components/SettingsDialog';
import { Sidebar } from './components/Sidebar';
import { SourcesPanel } from './components/SourcesPanel';
import { useApplySettings } from './hooks/useApplySettings';
import { useMediaQuery } from './hooks/useMediaQuery';
import { chatStore, useActiveConversation, useChat } from './state/chatStore';
import { settingsStore, useSettings } from './state/settingsStore';

export default function App() {
  const theme = useApplySettings();
  const conversation = useActiveConversation();
  const busy = useChat((s) => s.streaming !== null);
  const sourcesOpen = useChat((s) => s.sourcesFor !== null);
  const notice = useChat((s) => s.notice);
  const desktopSidebarOpen = useSettings((s) => s.sidebarOpen);
  // On small screens the sidebar is an off-canvas drawer that starts closed.
  const isMobile = useMediaQuery('(max-width: 900px)');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const sidebarOpen = isMobile ? drawerOpen : desktopSidebarOpen;
  const toggleSidebar = () =>
    isMobile
      ? setDrawerOpen((open) => !open)
      : settingsStore.getState().update({ sidebarOpen: !desktopSidebarOpen });
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [prefill, setPrefill] = useState<string | undefined>();
  const clearPrefill = useCallback(() => setPrefill(undefined), []);

  useEffect(() => {
    void chatStore.getState().loadCapabilities();
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => chatStore.getState().dismissNotice(), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  const hasMessages = (conversation?.messages.length ?? 0) > 0;

  return (
    <div
      className={`app ${sidebarOpen ? 'app--sidebar-open' : ''} ${sourcesOpen ? 'app--sources-open' : ''}`}
    >
      <Sidebar
        theme={theme}
        onOpenSettings={() => setSettingsOpen(true)}
        onNavigate={isMobile ? closeDrawer : undefined}
      />
      {isMobile && drawerOpen && <div className="backdrop" onClick={closeDrawer} aria-hidden />}
      <main className="chat">
        <header className="chat__header">
          <button
            type="button"
            className="icon-button"
            aria-label={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
            aria-expanded={sidebarOpen}
            onClick={toggleSidebar}
          >
            <PanelLeft size={18} />
          </button>
          <h1 className="chat__title">{conversation?.title ?? 'New chat'}</h1>
        </header>
        {conversation && hasMessages ? (
          <MessageList conversation={conversation} busy={busy} />
        ) : (
          <EmptyState onPick={setPrefill} />
        )}
        <div className="chat__composer">
          <Composer prefill={prefill} onPrefillUsed={clearPrefill} />
          <p className="chat__disclaimer">Nexa can make mistakes. Check important information.</p>
        </div>
        {notice && (
          <div className="toast" role="status">
            {notice}
          </div>
        )}
      </main>
      <SourcesPanel />
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
