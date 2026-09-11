import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { ArrowUp, Download, Paperclip, Gamepad2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useLocation } from 'react-router-dom';
import { apiClient, ProgressUpdate } from '@/lib/api';
import Header from '@/components/Header';
import GenerationLoader from '@/components/GenerationLoader';
import ChatMessage from '@/components/ChatMessage';
import { AUTH_ENABLED } from '@/lib/authConfig';

interface Message {
  text: string;
  sender: 'user' | 'bot';
  timestamp?: Date;
  /** Placeholder turn that shows a spinner until the real reply lands. */
  thinking?: boolean;
}

export default function GamoraAIDashboard() {
  const location = useLocation();
  const locationState = location.state as { 
    initialMessage?: string;
    projectId?: string;
    websocketUrl?: string;
  } || {};
  
  const initialMessage = locationState.initialMessage || '';
  const projectId = locationState.projectId;
  const websocketUrl = locationState.websocketUrl;
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<string>('');
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(projectId || null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const completionMessageAddedRef = useRef<boolean>(false);

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const addBotMessage = useCallback((text: string) => {
    setMessages((prev) => [...prev, {
      text,
      sender: 'bot',
      timestamp: new Date()
    }]);
  }, []);

  /** Append a spinner turn, or retarget the existing one with new status text. */
  const setThinking = useCallback((text: string) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.thinking);
      if (idx === -1) {
        return [...prev, { text, sender: 'bot', timestamp: new Date(), thinking: true }];
      }
      const next = [...prev];
      next[idx] = { ...next[idx], text };
      return next;
    });
  }, []);

  /** Turn the spinner turn into the final reply, so the answer lands in place. */
  const resolveThinking = useCallback((text: string) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.thinking);
      if (idx === -1) {
        return [...prev, { text, sender: 'bot', timestamp: new Date() }];
      }
      const next = [...prev];
      next[idx] = { text, sender: 'bot', timestamp: new Date(), thinking: false };
      return next;
    });
  }, []);

  const handleWebSocketUpdate = useCallback((update: ProgressUpdate) => {
    console.log('WebSocket update:', update);
    
    switch (update.type) {
      case 'connected':
        setCurrentStatus('Game Generation In Progress...');
        setThinking('Reading your idea...');
        break;
        
      case 'progress':
        const { status, message, step, progress } = update.data;
        // Update status for right panel only
        const displayText = message || status || 'Processing...';
        if (displayText) {
          setCurrentStatus(displayText);
          setThinking(displayText);
        }
        if (step) {
          setIsLoading(true);
        }
        break;
        
      case 'complete':
        setIsLoading(false);
        setCurrentStatus('Completed');
        const { project_id } = update.data;
        const previewUrlFromUpdate = (update.data as any).preview_url || update.data.web_preview_url;
        if (project_id) {
          setCurrentProjectId(project_id);
          // Fetch preview URL if not in update
          if (previewUrlFromUpdate) {
            // Same URL after an edit, so force the iframe to refetch.
            setPreviewUrl(`${previewUrlFromUpdate}${previewUrlFromUpdate.includes('?') ? '&' : '?'}v=${Date.now()}`);
          } else {
            // Fetch preview URL from API
            fetchPreviewUrl(project_id);
          }
        }
        // Update chat with completion message (only once)
        if (!completionMessageAddedRef.current) {
          resolveThinking(
            'Your game is ready — it is running on the right.\n\nTell me what to change and I will build it again.'
          );
          completionMessageAddedRef.current = true;
        }
        break;
        
      case 'error':
        setIsLoading(false);
        setCurrentStatus('Failed');
        resolveThinking(`**Generation failed.** ${update.data.error || 'Something went wrong.'}`);
        break;
    }
  }, [addBotMessage, setThinking, resolveThinking]);

  // Initialize with user message and connect to WebSocket
  useEffect(() => {
    if (initialMessage && messages.length === 0) {
      setMessages([
        { text: initialMessage, sender: 'user', timestamp: new Date() },
        { text: 'Cooking your game...', sender: 'bot', timestamp: new Date(), thinking: true }
      ]);
    }

    // Connect to WebSocket if projectId is available
    if (projectId) {
      setIsLoading(true);
      setCurrentStatus('Connecting...');
      completionMessageAddedRef.current = false; // Reset completion message flag
      
      apiClient.createWebSocketConnection(projectId, handleWebSocketUpdate).then((ws) => {
        wsRef.current = ws;
      }).catch((error) => {
        console.error('Failed to connect WebSocket:', error);
        addBotMessage('❌ Failed to connect to real-time updates');
        setIsLoading(false);
      });

      return () => {
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
      };
    }
  }, [projectId, initialMessage, addBotMessage, handleWebSocketUpdate]);

  const handleSend = async () => {
    if (input.trim() === '' || isLoading) return;
    
    const newMsg: Message = { text: input, sender: 'user', timestamp: new Date() };
    setMessages((prev) => [...prev, newMsg]);
    const userPrompt = input.trim();
    setInput('');
    setIsLoading(true);

    try {
      // Reset completion message flag for new generation
      completionMessageAddedRef.current = false;
      
      // A follow-up EDITS the game already on screen. Only the very first
      // message — when there is no project yet — creates a new game.
      const isFollowUp = Boolean(currentProjectId);

      setMessages((prev) => [
        ...prev,
        {
          text: isFollowUp ? 'Applying your change...' : 'Cooking your game...',
          sender: 'bot',
          timestamp: new Date(),
          thinking: true,
        },
      ]);

      const response = isFollowUp
        ? await apiClient.iterateGame(currentProjectId as string, userPrompt)
        : await apiClient.generateGame({ prompt: userPrompt });

      if (wsRef.current) {
        wsRef.current.close();
      }

      setCurrentProjectId(response.project_id);
      // Keep the current preview up while an edit builds; only a brand new
      // game should blank the panel.
      if (!isFollowUp) setPreviewUrl(null);

      apiClient.createWebSocketConnection(response.project_id, (update: ProgressUpdate) => {
        handleWebSocketUpdate(update);
      }).then((ws) => {
        wsRef.current = ws;
        setCurrentStatus('Starting generation...');
      }).catch((error) => {
        console.error('Failed to connect WebSocket:', error);
        resolveThinking('**Lost the live connection.** Your game may still be building — reload to check.');
        setIsLoading(false);
      });
    } catch (error: any) {
      console.error('Failed to generate game:', error);
      resolveThinking(`**Could not start generation.** ${error.message || 'Please try again.'}`);
      setIsLoading(false);
    }
  };

  const handleDownloadGame = async () => {
    if (!currentProjectId) {
      console.error('No project ID available');
      addBotMessage('❌ No game available to download. Please generate a game first.');
      return;
    }

    try {
      addBotMessage('Preparing game files for download...');

      // Get auth token for download endpoint
      const { createClient } = await import('@supabase/supabase-js');
      const supabase = createClient(
        import.meta.env.VITE_SUPABASE_URL || '',
        import.meta.env.VITE_SUPABASE_ANON_KEY || ''
      );
      
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token && AUTH_ENABLED) {
        addBotMessage('Please sign in to download games.');
        return;
      }

      // Call backend download endpoint for HTML5 games (ZIP)
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const downloadUrl = `${API_BASE_URL}/api/v1/generate/download-web/${currentProjectId}`;
      
      // Download with proper error handling and progress
      addBotMessage('Downloading game files...');
      
      const response = await fetch(downloadUrl, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });

      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = `Download failed: ${response.statusText}`;
        
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.detail || errorMessage;
        } catch {
          // Use default error message
        }
        
        throw new Error(errorMessage);
      }

      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `game_${currentProjectId}.zip`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Download as blob and create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      addBotMessage('Game downloaded successfully! Extract the ZIP file and open index.html in your browser.');
    } catch (error) {
      console.error('Download error:', error);
      addBotMessage(`❌ Download failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleDownload = async () => {
    if (!currentProjectId) {
      console.error('No project ID available');
      addBotMessage('❌ No game available to download. Please generate a game first.');
      return;
    }

    try {
      // PROTOTYPE MODE: Always use Windows build
      const platform = 'windows';
      addBotMessage('📥 Starting download... (Windows EXE)');

      // Get auth token for download endpoint
      const { createClient } = await import('@supabase/supabase-js');
      const supabase = createClient(
        import.meta.env.VITE_SUPABASE_URL || '',
        import.meta.env.VITE_SUPABASE_ANON_KEY || ''
      );
      
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token && AUTH_ENABLED) {
        addBotMessage('Please sign in to download games.');
        return;
      }

      // Call backend download endpoint
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const downloadUrl = `${API_BASE_URL}/api/v1/generate/download/${currentProjectId}?platform=${platform}`;
      
      // Download with proper error handling and progress
      addBotMessage('⏳ Downloading game file...');
      
      const response = await fetch(downloadUrl, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });

      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = `Download failed: ${response.statusText}`;
        
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.detail || errorMessage;
        } catch {
          // Use default error message
        }
        
        throw new Error(errorMessage);
      }

      // Check if response has content
      const contentLength = response.headers.get('content-length');
      if (contentLength && parseInt(contentLength) === 0) {
        throw new Error('Downloaded file is empty. The build may not be ready yet.');
      }

      // Get blob with progress tracking
      const blob = await response.blob();
      
      if (!blob || blob.size === 0) {
        throw new Error('Downloaded file is empty. Please try again.');
      }

      // Create download link
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `${currentProjectId}_windows.exe`;
      link.style.display = 'none';
      
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      setTimeout(() => {
        document.body.removeChild(link);
        window.URL.revokeObjectURL(blobUrl);
      }, 100);

      const fileSizeMB = (blob.size / 1024 / 1024).toFixed(2);
      addBotMessage(`✅ Download complete! File size: ${fileSizeMB} MB`);
    } catch (error: any) {
      console.error('Download failed:', error);
      const errorMessage = error.message || 'Unknown error occurred';
      addBotMessage(`❌ Download failed: ${errorMessage}. Please try again or contact support.`);
    }
  };

  const fetchPreviewUrl = async (projectId: string) => {
    try {
      const project = await apiClient.getProject(projectId);
      if (project.web_preview_url) {
        setPreviewUrl(project.web_preview_url);
      } else {
        // Fallback: construct preview URL from project ID
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const previewUrl = `${API_BASE_URL}/api/v1/generate/preview/${projectId}`;
        setPreviewUrl(previewUrl);
      }
    } catch (error) {
      console.error('Failed to fetch preview URL:', error);
      // Fallback: construct preview URL from project ID
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const previewUrl = `${API_BASE_URL}/api/v1/generate/preview/${projectId}`;
        setPreviewUrl(previewUrl);
    }
  };

  const copyProjectId = async () => {
    if (currentProjectId) {
      try {
        await navigator.clipboard.writeText(currentProjectId);
        // You could show a toast here
        console.log('Project ID copied to clipboard');
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col h-screen bg-black text-white font-sans">
      {/* Header */}
      <Header />
      
      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden bg-black">
      {/* Left Chat Panel */}
      <div className="w-[35%] flex flex-col border-r border-border/50 p-6 bg-black">
        <div
          className={`flex-1 mb-4 custom-scrollbar ${
            messages.length > 0 ? 'overflow-y-auto space-y-4' : 'overflow-hidden'
          }`}
        >
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-col justify-center items-center h-full text-white text-center">
              <p className="text-lg mb-2 font-light">Start building your next game</p>
              <p className="text-sm font-light">Describe your idea and Mamba will generate code for you.</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage
              key={i}
              message={msg.text}
              isUser={msg.sender === 'user'}
              isThinking={msg.thinking}
            />
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Composer — scales gently on focus, actions pinned bottom-right */}
        <div className="mt-4">
          <div
            className={`relative origin-bottom transition-all duration-300 ease-out md:focus-within:scale-[1.02]
              bg-zinc-900/50 backdrop-blur-sm rounded-lg border border-white/30
              shadow-[0_-15px_40px_rgba(0,0,0,0.8)] p-2 sm:p-4
              ${isLoading ? 'opacity-50' : ''}`}
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (!isLoading) handleSend();
                }
              }}
              disabled={isLoading}
              placeholder={isLoading ? 'Building your game...' : 'Describe your idea...'}
              className="min-h-[80px] sm:min-h-[100px] py-2 sm:py-3 px-2 sm:px-4 text-sm sm:text-base
                resize-none border-0 bg-transparent pr-16 sm:pr-24
                focus-visible:ring-0 focus-visible:ring-offset-0
                text-white font-medium placeholder:text-gray-400 placeholder:font-normal
                disabled:cursor-not-allowed"
            />

            <input type="file" ref={fileInputRef} className="hidden" />

            <div className="absolute bottom-2 sm:bottom-3 right-2 sm:right-3 flex items-center gap-1 sm:gap-2">
              <motion.div
                className="inline-flex"
                whileHover={{ scale: 1.12 }}
                whileTap={{ scale: 0.85 }}
                transition={{ type: 'spring', stiffness: 500, damping: 12 }}
              >
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 sm:h-8 sm:w-8 rounded-sm border border-white/20 hover:bg-zinc-800"
                  onClick={handleAttachClick}
                  disabled={isLoading}
                  aria-label="Attach a file"
                >
                  <Paperclip className="h-4 w-4 sm:h-3.5 sm:w-3.5 text-white" />
                </Button>
              </motion.div>

              <motion.div
                className="inline-flex"
                whileHover={{ scale: 1.12 }}
                whileTap={{ scale: 0.85 }}
                transition={{ type: 'spring', stiffness: 500, damping: 12 }}
              >
                <Button
                  onClick={handleSend}
                  size="icon"
                  disabled={isLoading || !input.trim()}
                  className="h-9 w-9 sm:h-8 sm:w-8 bg-[#25D366] hover:bg-[#4ae389] text-black
                    rounded-sm border-none shadow-none
                    disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="Send"
                >
                  <ArrowUp className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
                </Button>
              </motion.div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Preview Panel */}
      <div className="w-[65%] flex flex-col items-center justify-center bg-black relative">
        {isLoading ? (
          <GenerationLoader status={currentStatus} />
        ) : (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
            className="flex flex-col items-center w-full h-full py-6"
          >
            {currentProjectId && previewUrl ? (
              <>
                <div className="flex items-center justify-end w-full px-6 pt-6 pb-6">
                  <button
                    onClick={handleDownloadGame}
                    className="
                      bg-black text-green-500 border border-green-500 
                      px-6 py-3 rounded-sm font-light
                      transition-colors duration-300
                      hover:bg-green-500 hover:text-black
                      flex items-center gap-2
                    "
                  >
                    <Download size={18} />
                    Download Game
                  </button>
                </div>
                <div className="flex-1 w-full px-6 pt-6 pb-6 relative flex items-center justify-center">
                  <iframe
                    key={previewUrl}
                    src={previewUrl}
                    className="w-full h-full max-w-full max-h-full border-0 rounded-lg bg-black"
                    title="Game Preview"
                    allow="gamepad; fullscreen; autoplay; cross-origin-isolated"
                    // No allow-same-origin: the game is model-written code and
                    // must not reach this app's origin or its localStorage.
                    sandbox="allow-scripts allow-pointer-lock allow-downloads"
                    style={{
                      border: 'none',
                      display: 'block',
                      width: '100%',
                      height: '100%',
                      minHeight: '500px'
                    }}
                    onLoad={() => console.log('Game loaded:', previewUrl)}
                  />
                </div>
              </>
            ) : currentProjectId ? (
              <div className="flex flex-col items-center justify-center h-full">
                <Gamepad2 size={64} className="text-gray-600 mb-4" />
                <h2 className="text-xl mb-2 text-gray-400 font-light">
                  Game is Generating...
                </h2>
                <p className="text-gray-500 text-sm font-light">
                  Preview will appear here when ready
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full">
                <Gamepad2 size={64} className="text-gray-600 mb-4" />
                <h2 className="text-xl mb-2 text-gray-400 font-light">
                  No Game Generated Yet
                </h2>
                <p className="text-gray-500 text-sm font-light">
                  Generate a game to preview it here
                </p>
              </div>
            )}
          </motion.div>
        )}
      </div>
      </div>

      <style>{`
        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: rgba(107, 107, 107, 0.2) transparent;
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 3px;
          height: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgba(107, 107, 107, 0.2);
          border-radius: 3px;
          transition: background-color 0.2s ease;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background-color: rgba(107, 107, 107, 0.35);
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
      `}</style>
    </div>
  );
}

