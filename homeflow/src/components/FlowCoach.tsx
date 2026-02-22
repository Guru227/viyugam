import { useState, useEffect, useRef } from 'react';
import { Bot, Sparkles, Send, User } from 'lucide-react';

interface FlowCoachProps {
  currentView: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const PERSONAS: Record<string, { title: string; role: string; description: string; initialMessage: string }> = {
  strategy: {
    title: "The Visionary",
    role: "CEO",
    description: "Helping you define core values and long-term vision.",
    initialMessage: "Welcome, CEO. Let's look at the big picture. Are your current Life Aspects aligned with your true values?"
  },
  'strategy-focus': {
    title: "The Arbitrator",
    role: "VP Strategy",
    description: "Helping you make hard trade-offs and prioritize.",
    initialMessage: "We can't do everything. What are the 'Quick Wins' we should focus on this season?"
  },
  tactical: {
    title: "The Architect",
    role: "Product Manager",
    description: "Breaking down goals into concrete requirements.",
    initialMessage: "Let's get specific. Break down your active projects into milestones. What's the definition of done?"
  },
  execution: {
    title: "The Scheduler",
    role: "Scrum Master",
    description: "Optimizing your weekly plan for flow.",
    initialMessage: "Look at your week. Do you have enough deep work blocks? Don't overcommit."
  },
  daily: {
    title: "The Coach",
    role: "IC Coach",
    description: "Keeping you motivated and unblocked.",
    initialMessage: "Focus on the 'Now'. What is the one thing you need to complete in this session?"
  }
};

export function FlowCoach({ currentView }: FlowCoachProps) {
  const persona = PERSONAS[currentView] || PERSONAS['strategy'];
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Reset chat when view changes
  useEffect(() => {
    setMessages([
      { id: 'init', role: 'assistant', content: persona.initialMessage }
    ]);
  }, [currentView, persona.initialMessage]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Mock AI Response
    setTimeout(() => {
      const responses = [
        "That's a great insight. How does that align with your core values?",
        "Have you considered the budget impact of that decision?",
        "Let's break that down further. What's the very next step?",
        "Remember to pace yourself. Consistency beats intensity.",
        "I've noted that. Let's keep moving forward."
      ];
      const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      
      const aiMsg: Message = { 
        id: (Date.now() + 1).toString(), 
        role: 'assistant', 
        content: `[${persona.role}]: ${randomResponse}` 
      };
      
      setMessages(prev => [...prev, aiMsg]);
      setIsTyping(false);
    }, 1500);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="w-full h-full bg-surface border-r border-slate-200 flex flex-col shadow-sm z-10 flex-shrink-0">
      {/* Header */}
      <div className="p-6 border-b border-slate-100 bg-gradient-to-b from-primary-50 to-transparent">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-primary-100 rounded-lg text-primary-600">
            <Bot size={24} />
          </div>
          <div>
            <h2 className="font-bold text-slate-800">Flow Coach</h2>
            <div className="flex items-center gap-1 text-xs text-primary-600 font-medium">
              <Sparkles size={12} />
              <span>AI Active</span>
            </div>
          </div>
        </div>
      </div>

      {/* Persona Card */}
      <div className="p-4">
        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 transition-all duration-300">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Current Persona</div>
          <h3 className="font-bold text-slate-800 text-lg">{persona.title}</h3>
          <div className="text-sm text-primary-600 font-medium mb-2">{persona.role}</div>
          <p className="text-sm text-slate-600 leading-relaxed">
            {persona.description}
          </p>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 p-4 overflow-y-auto custom-scrollbar flex flex-col gap-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'assistant' ? 'bg-primary-100 text-primary-600' : 'bg-slate-200 text-slate-600'}`}>
              {msg.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
            </div>
            <div className={`rounded-2xl p-3 text-sm max-w-[80%] ${
              msg.role === 'assistant' 
                ? 'bg-slate-100 text-slate-700 rounded-tl-none' 
                : 'bg-primary-500 text-white rounded-tr-none'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 flex-shrink-0">
              <Bot size={16} />
            </div>
            <div className="bg-slate-100 rounded-2xl rounded-tl-none p-3 text-sm text-slate-500 flex gap-1 items-center">
              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-slate-100">
        <div className="relative">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask ${persona.role}...`} 
            className="w-full pl-4 pr-10 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-primary-400 transition-all text-sm"
          />
          <button 
            onClick={handleSend}
            disabled={!input.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-primary-600 transition-colors disabled:opacity-50"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
