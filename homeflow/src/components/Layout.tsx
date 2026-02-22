import React from 'react';
import { FlowCoach } from './FlowCoach';

interface LayoutProps {
  children: React.ReactNode;
  currentView: string;
  onViewChange: (view: string) => void;
}

const SECTIONS = ['strategy', 'strategy-focus', 'tactical', 'execution', 'daily'];

export function Layout({ children, currentView, onViewChange }: LayoutProps) {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Sidebar - 1/3 width */}
      <div className="w-1/3 h-full flex-shrink-0 z-20 shadow-xl border-r border-slate-100">
        <FlowCoach currentView={currentView} />
      </div>

      {/* Main Content - Single Page View */}
      <div className="flex-1 relative h-full bg-slate-50">
        <div className="w-full h-full">
          {children}
        </div>

        {/* Navigation Dots */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-3 bg-white/80 backdrop-blur-md p-3 rounded-full border border-white/20 shadow-lg z-30">
          {SECTIONS.map((section) => (
            <button
              key={section}
              onClick={() => onViewChange(section)}
              className={`w-3 h-3 rounded-full transition-all duration-300 ${
                currentView === section 
                  ? 'bg-primary-600 scale-125' 
                  : 'bg-slate-300 hover:bg-primary-300'
              }`}
              title={section.replace('-', ' ')}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
