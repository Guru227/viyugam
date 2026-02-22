import { useState } from 'react';
import { 
  DollarSign, 
  Clock, 
  Filter, 
  Layers, 
  CheckCircle2, 
  Circle,
  LayoutList,
  AlertCircle
} from 'lucide-react';
import { 
  Radar, 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  PolarRadiusAxis, 
  ResponsiveContainer,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import type { Project } from '../types';
import { INITIAL_DOMAINS, INITIAL_PROJECTS, TOTAL_CAPACITIES } from '../data';

const TogglePill = ({ label, active, onClick, icon: Icon }: any) => (
    <button 
        onClick={onClick}
        className={`flex items-center space-x-1 px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${active ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'}`}
    >
        {Icon && <Icon size={14} />}
        <span>{label}</span>
    </button>
);

type Lens = 'budget' | 'scope' | 'time';

export function StrategyFocusView() {
  const [projects, setProjects] = useState<Project[]>(INITIAL_PROJECTS);
  const [domains] = useState(INITIAL_DOMAINS);
  const [activeTab, setActiveTab] = useState<'matrix' | 'capacity'>('matrix');
  const [showBudget, setShowBudget] = useState(false);
  const [showTime, setShowTime] = useState(false);
  const [activeLens, setActiveLens] = useState<Lens>('scope');

  const toggleStatus = (id: string) => {
    setProjects(projects.map(p => 
      p.id === id ? { ...p, status: p.status === 'active' ? 'backlog' : 'active' } : p
    ));
  };

  const activeProjectsCount = projects.filter(p => p.status === 'active').length;
  const backlogProjectsCount = projects.filter(p => p.status === 'backlog').length;

  // --- Chart Helpers ---
  const getChartData = () => {
    return domains.map(d => ({
      name: d.name,
      value: activeLens === 'budget' ? d.budgetScore : activeLens === 'time' ? d.timeScore : d.scopeScore,
      target: d.targetScore,
      fullMark: 10
    }));
  };

  const getDistributionData = () => {
    const totalCapacity = activeLens === 'budget' ? TOTAL_CAPACITIES.budget : activeLens === 'time' ? TOTAL_CAPACITIES.time : TOTAL_CAPACITIES.scope;
    
    const usedData = domains.map(d => {
      const domainProjects = projects.filter(p => p.domainId === d.id);
      const domainValue = domainProjects.reduce((sum, p) => {
        const val = activeLens === 'budget' ? p.budget : activeLens === 'time' ? p.effort : p.impact;
        return sum + (val || 0);
      }, 0);
      
      return {
        name: d.name,
        value: domainValue,
        color: d.color
      };
    }).filter(d => d.value > 0);

    const totalUsed = usedData.reduce((sum, d) => sum + d.value, 0);
    const unused = Math.max(0, totalCapacity - totalUsed);

    const data = usedData.map(d => ({
      ...d,
      value: Math.round((d.value / totalCapacity) * 100)
    }));

    if (unused > 0) {
      data.push({
        name: 'Available' as any,
        value: Math.round((unused / totalCapacity) * 100),
        color: '#f1f5f9' // Slate-100
      });
    }

    return data;
  };

  return (
    <div id="strategy-focus" className="w-full h-full p-8 snap-start overflow-y-auto bg-slate-50">
      <div className="w-full h-full flex flex-col">
        <div className="mb-6 flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-bold text-slate-800 mb-2 font-sans">Strategy Focus</h1>
            <p className="text-xl text-slate-500">The Arbitrator — Prioritize & Execute</p>
          </div>
          
          <div className="flex bg-white rounded-lg p-1 border border-slate-200 shadow-sm">
             <button 
                onClick={() => setActiveTab('matrix')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'matrix' ? 'bg-indigo-100 text-indigo-700 shadow-sm' : 'text-slate-500 hover:bg-slate-50'}`}
             >
                <Filter size={16} />
                Priority Matrix
             </button>
             <button 
                onClick={() => setActiveTab('capacity')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'capacity' ? 'bg-indigo-100 text-indigo-700 shadow-sm' : 'text-slate-500 hover:bg-slate-50'}`}
             >
                <Layers size={16} />
                Capacity Check
             </button>
          </div>
        </div>

        {activeTab === 'matrix' ? (
            <div className="flex-1 min-h-0 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                {/* Toolbar */}
                <div className="px-6 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="text-sm font-medium text-slate-500">
                        Drag projects to adjust priority (Visual only)
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-400 uppercase mr-2">Overlays:</span>
                        <TogglePill label="Budget" icon={DollarSign} active={showBudget} onClick={() => setShowBudget(!showBudget)} />
                        <TogglePill label="Time (Effort)" icon={Clock} active={showTime} onClick={() => setShowTime(!showTime)} />
                    </div>
                </div>

                {/* Matrix Grid */}
                <div className="flex-1 relative bg-slate-50/30 p-6">
                     <div className="absolute inset-6 bg-white rounded-xl border border-slate-200 shadow-inner grid grid-cols-2 grid-rows-2">
                         {/* Quadrants */}
                         <div className="border-b border-r border-slate-100 p-4 relative">
                             <span className="absolute top-4 left-4 text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded">Quick Wins (High Impact, Low Effort)</span>
                         </div>
                         <div className="border-b border-slate-100 p-4 relative bg-indigo-50/30">
                             <span className="absolute top-4 right-4 text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-1 rounded">Major Projects (High Impact, High Effort)</span>
                         </div>
                         <div className="border-r border-slate-100 p-4 relative">
                             <span className="absolute bottom-4 left-4 text-xs font-bold text-slate-400 bg-slate-100 px-2 py-1 rounded">Fill-ins (Low Impact, Low Effort)</span>
                         </div>
                         <div className="p-4 relative">
                             <span className="absolute bottom-4 right-4 text-xs font-bold text-red-400 bg-red-50 px-2 py-1 rounded">Thankless Tasks (Low Impact, High Effort)</span>
                         </div>

                         {/* Axes Labels */}
                         <div className="absolute bottom-[-24px] left-0 w-full text-center text-xs font-bold text-slate-400 uppercase tracking-widest">Effort →</div>
                         <div className="absolute left-[-24px] top-0 h-full flex items-center justify-center -rotate-90 text-xs font-bold text-slate-400 uppercase tracking-widest">Impact →</div>
                     </div>

                     {/* Project Cards */}
                     <div className="absolute inset-6 pointer-events-none">
                         {projects.map(p => (
                             <div 
                                key={p.id} 
                                className={`absolute transform -translate-x-1/2 -translate-y-1/2 p-3 bg-white rounded-xl shadow-md border transition-all cursor-pointer pointer-events-auto hover:scale-105 hover:shadow-lg hover:z-10 w-48 ${p.status === 'active' ? 'border-indigo-200 ring-2 ring-indigo-50' : 'border-slate-200 opacity-80 grayscale'}`}
                                style={{ 
                                    top: `${100 - (p.impact * 10)}%`, 
                                    left: `${(p.effort * 10)}%` 
                                }}
                                onClick={() => toggleStatus(p.id)}
                             >
                                 <div className="flex justify-between items-start mb-1">
                                     <span className="font-bold text-xs text-slate-700 line-clamp-1">{p.title}</span>
                                     {p.status === 'active' ? <CheckCircle2 size={14} className="text-indigo-500" /> : <Circle size={14} className="text-slate-300" />}
                                 </div>
                                 <p className="text-[10px] text-slate-400 line-clamp-1 mb-2">{p.description}</p>
                                 
                                 {(showBudget || showTime) && (
                                     <div className="flex gap-1 flex-wrap">
                                         {showBudget && <span className="text-[10px] font-medium bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded flex items-center gap-0.5"><DollarSign size={8} />{p.budget}</span>}
                                         {showTime && <span className="text-[10px] font-medium bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded flex items-center gap-0.5"><Clock size={8} />{p.effort}/10</span>}
                                     </div>
                                 )}
                             </div>
                         ))}
                     </div>
                </div>
            </div>
        ) : (
            <div className="flex-1 min-h-0 flex flex-col gap-2">
                {/* Top Bar: Metrics & Lenses */}
                <div className="relative flex items-center justify-center h-16 mb-2">
                    {/* Central Metrics */}
                    <div className="flex justify-center gap-2">
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 px-6 py-3 flex items-center gap-4 min-w-[150px]">
                            <div className="p-2 bg-green-100 text-green-600 rounded-xl"><CheckCircle2 size={20} /></div>
                            <div>
                                <div className="text-2xl font-bold text-slate-800 leading-none">{activeProjectsCount}</div>
                                <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">Active Projects</div>
                            </div>
                        </div>
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 px-6 py-3 flex items-center gap-4 min-w-[150px]">
                            <div className="p-2 bg-slate-100 text-slate-500 rounded-xl"><Circle size={20} /></div>
                            <div>
                                <div className="text-2xl font-bold text-slate-800 leading-none">{backlogProjectsCount}</div>
                                <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">Backlog</div>
                            </div>
                        </div>
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 px-6 py-3 flex items-center gap-4 min-w-[150px]">
                            <div className="p-2 bg-red-100 text-red-500 rounded-xl"><AlertCircle size={20} /></div>
                            <div>
                                <div className="text-2xl font-bold text-slate-800 leading-none">2</div>
                                <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">Alerts</div>
                            </div>
                        </div>
                    </div>

                    {/* Right: Capsule Lens Switcher */}
                    <div className="absolute right-0 bg-white rounded-full shadow-sm border border-slate-200 p-1 flex">
                        {(['budget', 'scope', 'time'] as const).map(lens => (
                            <button
                                key={lens}
                                onClick={() => setActiveLens(lens)}
                                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                                    activeLens === lens 
                                    ? lens === 'budget' ? 'bg-emerald-500 text-white shadow-md' : lens === 'time' ? 'bg-amber-500 text-white shadow-md' : 'bg-indigo-500 text-white shadow-md'
                                    : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600'
                                }`}
                                title={lens.charAt(0).toUpperCase() + lens.slice(1)}
                            >
                                {lens === 'budget' && <DollarSign size={18} />}
                                {lens === 'scope' && <LayoutList size={18} />}
                                {lens === 'time' && <Clock size={18} />}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Charts Grid */}
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-2 min-h-0">
                    {/* Radar Chart */}
                    <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-6 flex flex-col relative overflow-hidden h-[360px]">
                        <h3 className="text-lg font-bold text-slate-700 mb-2">Balance Analysis</h3>
                        <div className="flex-1 min-h-0 flex items-center justify-center">
                            <div className="w-full h-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={getChartData()}>
                                        <PolarGrid stroke="#e2e8f0" />
                                        <PolarAngleAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 12, fontWeight: 600 }} />
                                        <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
                                        <Radar
                                            name="Current"
                                            dataKey="value"
                                            stroke={activeLens === 'budget' ? '#10b981' : activeLens === 'time' ? '#f59e0b' : '#6366f1'}
                                            strokeWidth={3}
                                            fill={activeLens === 'budget' ? '#10b981' : activeLens === 'time' ? '#f59e0b' : '#6366f1'}
                                            fillOpacity={0.3}
                                        />
                                        <Radar
                                            name="Target"
                                            dataKey="target"
                                            stroke="#ec4899"
                                            strokeWidth={3}
                                            fill="#ec4899"
                                            fillOpacity={0.1}
                                            strokeDasharray="5 5"
                                        />
                                        <Tooltip 
                                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                            itemStyle={{ color: '#475569', fontWeight: 500 }}
                                        />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>

                    {/* Distribution Chart (Pie) */}
                    <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-6 flex flex-col h-[360px]">
                        <h3 className="text-lg font-bold text-slate-700 mb-2">Project Distribution (%)</h3>
                        <p className="text-xs text-slate-400 mb-4">Percentage of Total {activeLens.charAt(0).toUpperCase() + activeLens.slice(1)} used by each Domain</p>
                        <div className="flex-1 min-h-0">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={getDistributionData()}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={60}
                                        outerRadius={80}
                                        paddingAngle={5}
                                        dataKey="value"
                                    >
                                        {getDistributionData().map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip 
                                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                        itemStyle={{ color: '#475569', fontWeight: 500 }}
                                        formatter={(value: number) => [`${value}%`, 'Contribution']}
                                    />
                                    <Legend 
                                        verticalAlign="middle" 
                                        align="right"
                                        layout="vertical"
                                        iconType="circle"
                                        wrapperStyle={{ fontSize: '12px', fontWeight: 500, color: '#64748b' }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
                <div className="flex-1"></div>
            </div>
        )}
      </div>
    </div>
  );
}
