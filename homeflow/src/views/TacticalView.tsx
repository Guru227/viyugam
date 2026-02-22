import { useState } from 'react';
import { 
  LayoutList, 
  DollarSign, 
  Clock, 
  ChevronRight, 
  ChevronDown, 
  Plus,
  CheckSquare,
  Square
} from 'lucide-react';
import type { Project, Milestone, Task } from '../types';

// Mock Data
const MOCK_PROJECTS: Project[] = [
  { id: '1', title: 'Marathon Training', domainId: '1', description: 'Run a sub-4 hour marathon', status: 'active', impact: 9, effort: 8, budget: 500 },
  { id: '2', title: 'Launch Side Hustle', domainId: '2', description: 'MVP for SaaS idea', status: 'active', impact: 10, effort: 9, budget: 1000 },
];

const MOCK_MILESTONES: Record<string, Milestone[]> = {
  '1': [
    { id: 'm1', projectId: '1', title: 'Base Building', status: 'completed', costEstimate: 100, timeEstimateHours: 20 },
    { id: 'm2', projectId: '1', title: 'Speed Work Phase', status: 'in-progress', costEstimate: 50, timeEstimateHours: 15 },
    { id: 'm3', projectId: '1', title: 'Taper & Race Day', status: 'pending', costEstimate: 350, timeEstimateHours: 10 },
  ],
  '2': [
    { id: 'm4', projectId: '2', title: 'Market Research', status: 'completed', costEstimate: 0, timeEstimateHours: 10 },
    { id: 'm5', projectId: '2', title: 'Prototype Development', status: 'in-progress', costEstimate: 500, timeEstimateHours: 40 },
    { id: 'm6', projectId: '2', title: 'Launch Marketing', status: 'pending', costEstimate: 500, timeEstimateHours: 20 },
  ]
};

const MOCK_TASKS: Record<string, Task[]> = {
  'm1': [
    { id: 't1', milestoneId: 'm1', title: 'Buy running shoes', status: 'done' },
    { id: 't2', milestoneId: 'm1', title: 'Run 5k 3x/week', status: 'done' },
  ],
  'm2': [
    { id: 't3', milestoneId: 'm2', title: 'Interval training Tue/Thu', status: 'doing' },
    { id: 't4', milestoneId: 'm2', title: 'Long run Sunday', status: 'todo' },
  ],
  'm5': [
    { id: 't5', milestoneId: 'm5', title: 'Setup React project', status: 'done' },
    { id: 't6', milestoneId: 'm5', title: 'Build landing page', status: 'doing' },
    { id: 't7', milestoneId: 'm5', title: 'Integrate payments', status: 'todo' },
  ]
};

type ViewMode = 'scope' | 'budget' | 'time';

export function TacticalView() {
  const [viewMode, setViewMode] = useState<ViewMode>('scope');
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({ '1': true, '2': true });
  const [expandedMilestones, setExpandedMilestones] = useState<Record<string, boolean>>({ 'm2': true, 'm5': true });

  const toggleProject = (id: string) => {
    setExpandedProjects(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleMilestone = (id: string) => {
    setExpandedMilestones(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div id="tactical" className="min-w-full h-full p-8 snap-start overflow-y-auto bg-slate-50">
      <div className="max-w-7xl mx-auto h-full flex flex-col">
        <div className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-bold text-slate-800 mb-2 font-sans">Tactical Command</h1>
            <p className="text-xl text-slate-500">The Architect (Product Manager) — Break it Down</p>
          </div>
          
          {/* View Mode Switcher */}
          <div className="bg-white p-1 rounded-xl shadow-sm border border-slate-200 flex">
            <button 
              onClick={() => setViewMode('scope')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${viewMode === 'scope' ? 'bg-primary-50 text-primary-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <LayoutList size={16} />
              Scope
            </button>
            <button 
              onClick={() => setViewMode('budget')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${viewMode === 'budget' ? 'bg-emerald-50 text-emerald-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <DollarSign size={16} />
              Budget
            </button>
            <button 
              onClick={() => setViewMode('time')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${viewMode === 'time' ? 'bg-amber-50 text-amber-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <Clock size={16} />
              Time
            </button>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 flex-1 overflow-hidden flex flex-col">
          {/* Header */}
          <div className="grid grid-cols-12 gap-4 p-4 border-b border-slate-100 bg-slate-50/50 text-xs font-bold text-slate-400 uppercase tracking-wider">
            <div className="col-span-6 pl-4">Item</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-4 text-right pr-4">
              {viewMode === 'scope' && 'Requirements'}
              {viewMode === 'budget' && 'Est. Cost'}
              {viewMode === 'time' && 'Est. Hours'}
            </div>
          </div>

          {/* Content */}
          <div className="overflow-y-auto flex-1 p-4 space-y-2">
            {MOCK_PROJECTS.map(project => (
              <div key={project.id} className="space-y-2">
                {/* Project Row */}
                <div className="grid grid-cols-12 gap-4 p-3 bg-slate-50 rounded-xl border border-slate-100 items-center hover:border-primary-200 transition-colors group">
                  <div className="col-span-6 flex items-center gap-3">
                    <button onClick={() => toggleProject(project.id)} className="p-1 hover:bg-slate-200 rounded text-slate-400">
                      {expandedProjects[project.id] ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </button>
                    <div className="font-bold text-slate-800">{project.title}</div>
                    <span className="text-xs px-2 py-0.5 bg-primary-100 text-primary-700 rounded-full font-medium">Project</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-xs font-medium text-slate-500 capitalize">{project.status}</span>
                  </div>
                  <div className="col-span-4 text-right pr-4 font-mono text-slate-600">
                    {viewMode === 'scope' && <span className="text-xs text-slate-400">{project.description}</span>}
                    {viewMode === 'budget' && <span>${project.budget}</span>}
                    {viewMode === 'time' && <span>--</span>}
                  </div>
                </div>

                {/* Milestones */}
                {expandedProjects[project.id] && MOCK_MILESTONES[project.id]?.map(milestone => (
                  <div key={milestone.id} className="pl-8 space-y-2">
                    <div className="grid grid-cols-12 gap-4 p-2 border-b border-slate-50 items-center hover:bg-slate-50 rounded-lg transition-colors">
                      <div className="col-span-6 flex items-center gap-3">
                        <button onClick={() => toggleMilestone(milestone.id)} className="p-1 hover:bg-slate-200 rounded text-slate-400">
                          {expandedMilestones[milestone.id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </button>
                        <div className="font-semibold text-slate-700 text-sm">{milestone.title}</div>
                        <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded border border-slate-200 font-medium">Milestone</span>
                      </div>
                      <div className="col-span-2">
                         <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                           milestone.status === 'completed' ? 'bg-green-100 text-green-700' :
                           milestone.status === 'in-progress' ? 'bg-blue-100 text-blue-700' :
                           'bg-slate-100 text-slate-500'
                         }`}>
                           {milestone.status}
                         </span>
                      </div>
                      <div className="col-span-4 text-right pr-4 font-mono text-sm text-slate-600">
                        {viewMode === 'scope' && <span className="text-xs text-slate-400">--</span>}
                        {viewMode === 'budget' && <span>${milestone.costEstimate}</span>}
                        {viewMode === 'time' && <span>{milestone.timeEstimateHours}h</span>}
                      </div>
                    </div>

                    {/* Tasks */}
                    {expandedMilestones[milestone.id] && MOCK_TASKS[milestone.id]?.map(task => (
                      <div key={task.id} className="pl-8 grid grid-cols-12 gap-4 p-2 items-center hover:bg-slate-50 rounded-lg transition-colors group">
                        <div className="col-span-6 flex items-center gap-3">
                          <div className="w-4" /> {/* Indent for no chevron */}
                          <button className="text-slate-300 hover:text-primary-500 transition-colors">
                            {task.status === 'done' ? <CheckSquare size={16} className="text-primary-500" /> : <Square size={16} />}
                          </button>
                          <div className={`text-sm ${task.status === 'done' ? 'text-slate-400 line-through' : 'text-slate-600'}`}>
                            {task.title}
                          </div>
                        </div>
                        <div className="col-span-2">
                           {/* Task status is visual via checkbox, but could show text too */}
                        </div>
                        <div className="col-span-4 text-right pr-4">
                           {/* Tasks might not have individual budget/time in this high level view, or could sum up */}
                        </div>
                      </div>
                    ))}
                    
                    {/* Add Task Button */}
                    {expandedMilestones[milestone.id] && (
                      <div className="pl-12 py-1">
                        <button className="flex items-center gap-2 text-xs text-slate-400 hover:text-primary-600 transition-colors">
                          <Plus size={14} />
                          Add Task
                        </button>
                      </div>
                    )}
                  </div>
                ))}

                {/* Add Milestone Button */}
                {expandedProjects[project.id] && (
                  <div className="pl-8 py-2">
                     <button className="flex items-center gap-2 text-sm text-slate-400 hover:text-primary-600 transition-colors font-medium">
                        <Plus size={16} />
                        Add Milestone
                      </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
