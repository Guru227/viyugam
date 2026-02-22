import { useState } from 'react';
import type { Project } from '../types';
import { 
  Heart, Wallet, Users, Zap, Briefcase, Sparkles, 
  Plus, Filter, SlidersHorizontal, ArrowUpDown, 
  ChevronDown, ChevronRight, MoreHorizontal,
  LayoutGrid, List, Search
} from 'lucide-react';
import { ProjectOverlay } from '../components/ProjectOverlay';
import { INITIAL_DOMAINS, INITIAL_PROJECTS } from '../data';

const ICONS: Record<string, React.ReactNode> = {
  Health: <Heart size={16} />,
  Wealth: <Wallet size={16} />,
  Relationships: <Users size={16} />,
  Growth: <Zap size={16} />,
  Career: <Briefcase size={16} />,
  Spirituality: <Sparkles size={16} />,
};

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: 'Now', color: 'text-emerald-700', bg: 'bg-emerald-100' },
  backlog: { label: 'Later', color: 'text-slate-600', bg: 'bg-slate-100' },
  paused: { label: 'Next', color: 'text-amber-700', bg: 'bg-amber-100' },
  completed: { label: 'Done', color: 'text-blue-700', bg: 'bg-blue-100' },
};

const RatingDots = ({ score, max = 5, colorClass = 'bg-blue-400' }: { score: number, max?: number, colorClass?: string }) => {
  // Normalize 1-10 score to 1-5 dots
  const normalizedScore = Math.ceil(score / 2);
  return (
    <div className="flex gap-1">
      {Array.from({ length: max }).map((_, i) => (
        <div 
          key={i} 
          className={`w-2 h-2 rounded-full ${i < normalizedScore ? colorClass : 'bg-slate-200'}`} 
        />
      ))}
    </div>
  );
};

const ProgressBar = ({ progress }: { progress: number }) => (
  <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden flex">
    <div className="h-full bg-emerald-500" style={{ width: `${progress}%` }}></div>
    <div className="h-full bg-blue-500" style={{ width: `${Math.max(0, progress - 20)}%` }}></div> {/* Mock secondary progress */}
  </div>
);

export function StrategyView() {
  const [domains] = useState(INITIAL_DOMAINS);
  const [projects, setProjects] = useState<Project[]>(INITIAL_PROJECTS);
  const [expandedDomains, setExpandedDomains] = useState<Record<string, boolean>>(
    INITIAL_DOMAINS.reduce((acc, d) => ({ ...acc, [d.id]: true }), {})
  );
  
  // Overlay State
  const [isOverlayOpen, setIsOverlayOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const toggleDomain = (id: string) => {
    setExpandedDomains(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleProjectClick = (project: Project) => {
    setEditingProject(project);
    setIsOverlayOpen(true);
  };

  const handleSaveProject = (updatedProject: Project) => {
    setProjects(projects.map(p => p.id === updatedProject.id ? updatedProject : p));
    setIsOverlayOpen(false);
    setEditingProject(null);
  };

  return (
    <div id="strategy" className="w-full flex-shrink-0 h-full flex flex-col bg-white">
      {/* Header Toolbar */}
      <div className="px-6 py-4 border-b border-slate-200 flex flex-col gap-4">
        <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-slate-800">All ideas</h1>
                <span className="text-sm text-slate-400 font-medium">{projects.length} ideas</span>
            </div>
            <div className="flex items-center gap-2">
                 <button className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"><Search size={18} /></button>
                 <button className="p-2 hover:bg-slate-100 rounded-lg text-slate-500"><LayoutGrid size={18} /></button>
                 <button className="p-2 bg-slate-100 rounded-lg text-slate-700"><List size={18} /></button>
            </div>
        </div>
        
        <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
                <button 
                    onClick={() => { setEditingProject(null); setIsOverlayOpen(true); }}
                    className="bg-blue-600 text-white px-3 py-1.5 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors flex items-center gap-1"
                >
                    <Plus size={16} /> Create
                </button>
                <div className="h-6 w-px bg-slate-200 mx-2"></div>
                <button className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md flex items-center gap-1.5 border border-transparent hover:border-slate-200">
                    Group by <span className="text-slate-900">Theme</span> <ChevronDown size={14} />
                </button>
                <button className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md flex items-center gap-1.5 border border-transparent hover:border-slate-200">
                    <Filter size={14} /> Filter
                </button>
                <button className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md flex items-center gap-1.5 border border-transparent hover:border-slate-200">
                    <ArrowUpDown size={14} /> Sort
                </button>
                <button className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md flex items-center gap-1.5 border border-transparent hover:border-slate-200">
                    <SlidersHorizontal size={14} /> Fields <span className="bg-slate-100 text-slate-600 px-1.5 rounded text-xs">8</span>
                </button>
            </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <table className="w-full text-left border-collapse">
            <thead className="bg-slate-50 sticky top-0 z-10 shadow-sm">
                <tr>
                    <th className="py-3 px-4 border-b border-slate-200 w-10"><input type="checkbox" className="rounded border-slate-300" /></th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase w-1/3">Summary</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">Theme</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase text-center">Insights</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">Impact</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">Effort</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">Roadmap</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">Delivery Progress</th>
                    <th className="py-3 px-4 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">Assignee</th>
                </tr>
            </thead>
            <tbody>
                {domains.map(domain => {
                    const domainProjects = projects.filter(p => p.domainId === domain.id);
                    const isExpanded = expandedDomains[domain.id];
                    
                    return (
                        <>
                            {/* Group Header */}
                            <tr className="bg-slate-50/50 hover:bg-slate-50 transition-colors">
                                <td className="py-2 px-4 border-b border-slate-100" colSpan={9}>
                                    <button 
                                        onClick={() => toggleDomain(domain.id)}
                                        className="flex items-center gap-2 w-full text-left"
                                    >
                                        {isExpanded ? <ChevronDown size={16} className="text-slate-400" /> : <ChevronRight size={16} className="text-slate-400" />}
                                        <div className={`p-1 rounded bg-opacity-10 text-${domain.color}`} style={{ backgroundColor: `${domain.color}20`, color: domain.color }}>
                                            {ICONS[domain.name]}
                                        </div>
                                        <span className="font-bold text-slate-700 text-sm">{domain.name}</span>
                                        <span className="text-xs text-slate-400 font-medium">{domainProjects.length} ideas</span>
                                        <Plus size={14} className="ml-auto text-slate-400 hover:text-slate-600" />
                                    </button>
                                </td>
                            </tr>

                            {/* Project Rows */}
                            {isExpanded && domainProjects.map(project => {
                                const status = STATUS_MAP[project.status] || STATUS_MAP['backlog'];
                                const progress = Math.floor(Math.random() * 100); // Mock progress for now
                                
                                return (
                                    <tr 
                                        key={project.id} 
                                        onClick={() => handleProjectClick(project)}
                                        className="hover:bg-slate-50 transition-colors cursor-pointer group border-b border-slate-100 last:border-b-0"
                                    >
                                        <td className="py-3 px-4 w-10" onClick={e => e.stopPropagation()}>
                                            <input type="checkbox" className="rounded border-slate-300" />
                                        </td>
                                        <td className="py-3 px-4">
                                            <span className="text-sm font-medium text-slate-700 group-hover:text-blue-600 transition-colors">{project.title}</span>
                                        </td>
                                        <td className="py-3 px-4">
                                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                                                {ICONS[domain.name]} {domain.name}
                                            </span>
                                        </td>
                                        <td className="py-3 px-4 text-center">
                                            <div className="w-6 h-6 rounded bg-slate-100 mx-auto flex items-center justify-center text-slate-400">
                                                <MoreHorizontal size={12} />
                                            </div>
                                        </td>
                                        <td className="py-3 px-4">
                                            <RatingDots score={project.impact} colorClass="bg-blue-400" />
                                        </td>
                                        <td className="py-3 px-4">
                                            <RatingDots score={project.effort} colorClass="bg-red-400" />
                                        </td>
                                        <td className="py-3 px-4">
                                            <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wide ${status.bg} ${status.color}`}>
                                                {status.label}
                                            </span>
                                        </td>
                                        <td className="py-3 px-4">
                                            <ProgressBar progress={progress} />
                                        </td>
                                        <td className="py-3 px-4">
                                            <div className="flex items-center gap-2">
                                                <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-[10px] font-bold border border-indigo-200">GK</div>
                                                <span className="text-xs text-slate-500">Gurusankar K</span>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </>
                    );
                })}
                {/* Empty State Row */}
                <tr className="hover:bg-slate-50 transition-colors cursor-pointer border-b border-slate-100">
                     <td className="py-3 px-4 w-10"></td>
                     <td className="py-3 px-4" colSpan={8}>
                        <button 
                            onClick={() => { setEditingProject(null); setIsOverlayOpen(true); }}
                            className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-600 transition-colors"
                        >
                            <Plus size={16} /> Create
                        </button>
                     </td>
                </tr>
            </tbody>
        </table>
      </div>

      {/* Overlay */}
      <ProjectOverlay 
        project={editingProject} 
        isOpen={isOverlayOpen} 
        onClose={() => setIsOverlayOpen(false)} 
        onSave={handleSaveProject}
      />
    </div>
  );
}
