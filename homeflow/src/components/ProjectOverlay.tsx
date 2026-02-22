import { useState, useEffect } from 'react';
import { X, Save, Trash2, DollarSign, Clock, Target, LayoutList } from 'lucide-react';
import type { Project } from '../types';

interface ProjectOverlayProps {
  project: Project | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (project: Project) => void;
  onDelete?: (projectId: string) => void;
}

export function ProjectOverlay({ project, isOpen, onClose, onSave, onDelete }: ProjectOverlayProps) {
  const [formData, setFormData] = useState<Project | null>(null);

  useEffect(() => {
    if (project) {
      setFormData({ ...project });
    }
  }, [project]);

  if (!isOpen || !formData) return null;

  const handleChange = (field: keyof Project, value: any) => {
    setFormData(prev => prev ? { ...prev, [field]: value } : null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/20 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto flex flex-col animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex justify-between items-center sticky top-0 bg-white z-10">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Edit Project</h2>
            <p className="text-sm text-slate-500">Define the requirements and goals</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-600 transition-colors">
            <X size={24} />
          </button>
        </div>

        {/* Body */}
        <div className="p-8 space-y-8">
          
          {/* Main Info */}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Project Title</label>
              <input 
                type="text" 
                value={formData.title}
                onChange={(e) => handleChange('title', e.target.value)}
                className="w-full text-xl font-bold text-slate-800 border-b-2 border-slate-100 focus:border-primary-500 focus:outline-none py-2 transition-colors placeholder-slate-300"
                placeholder="e.g., Marathon Training"
              />
            </div>
            
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">The "Why" & Goal</label>
              <textarea 
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                className="w-full text-slate-600 bg-slate-50 rounded-xl p-4 border border-slate-200 focus:border-primary-400 focus:outline-none resize-none h-32"
                placeholder="Why is this important? What is the definition of done?"
              />
            </div>
          </div>

          {/* Lenses Grid */}
          <div>
            <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Target size={16} className="text-primary-500" />
              Lens Requirements
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Budget */}
              <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-100">
                <div className="flex items-center gap-2 mb-2 text-emerald-700 font-bold text-sm">
                  <DollarSign size={16} />
                  Budget
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-600 font-bold">$</span>
                  <input 
                    type="number" 
                    value={formData.budget}
                    onChange={(e) => handleChange('budget', parseInt(e.target.value) || 0)}
                    className="w-full pl-6 pr-3 py-2 bg-white rounded-lg border border-emerald-200 focus:outline-none focus:ring-2 focus:ring-emerald-200 text-emerald-900 font-mono font-bold"
                  />
                </div>
              </div>

              {/* Scope (Impact) */}
              <div className="bg-indigo-50 rounded-xl p-4 border border-indigo-100">
                <div className="flex items-center gap-2 mb-2 text-indigo-700 font-bold text-sm">
                  <LayoutList size={16} />
                  Impact (1-10)
                </div>
                <input 
                  type="number" 
                  min="1" max="10"
                  value={formData.impact}
                  onChange={(e) => handleChange('impact', parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white rounded-lg border border-indigo-200 focus:outline-none focus:ring-2 focus:ring-indigo-200 text-indigo-900 font-mono font-bold"
                />
              </div>

              {/* Time (Effort) */}
              <div className="bg-amber-50 rounded-xl p-4 border border-amber-100">
                <div className="flex items-center gap-2 mb-2 text-amber-700 font-bold text-sm">
                  <Clock size={16} />
                  Effort (1-10)
                </div>
                <input 
                  type="number" 
                  min="1" max="10"
                  value={formData.effort}
                  onChange={(e) => handleChange('effort', parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white rounded-lg border border-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-200 text-amber-900 font-mono font-bold"
                />
              </div>
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Status</label>
            <div className="flex gap-2">
              {(['active', 'backlog', 'completed', 'paused'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => handleChange('status', status)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                    formData.status === status 
                      ? 'bg-slate-800 text-white shadow-md' 
                      : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 bg-slate-50 flex justify-between items-center sticky bottom-0">
          {onDelete && (
            <button 
              onClick={() => onDelete(formData.id)}
              className="flex items-center gap-2 px-4 py-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors text-sm font-medium"
            >
              <Trash2 size={18} />
              Delete
            </button>
          )}
          <div className="flex gap-3 ml-auto">
            <button 
              onClick={onClose}
              className="px-6 py-2 text-slate-600 hover:bg-slate-200 rounded-xl transition-colors font-medium"
            >
              Cancel
            </button>
            <button 
              onClick={() => onSave(formData)}
              className="flex items-center gap-2 px-8 py-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 shadow-lg shadow-primary-500/30 transition-all font-bold"
            >
              <Save size={18} />
              Save Changes
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
