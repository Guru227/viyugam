import { useState, Component, type ReactNode } from 'react';
import { Layout } from './components/Layout';
import { StrategyView } from './views/StrategyView';
import { StrategyFocusView } from './views/StrategyFocusView';
import { TacticalView } from './views/TacticalView';
import { ExecutionView } from './views/ExecutionView';
import { DailyView } from './views/DailyView';

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean, error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-red-600 bg-red-50 h-screen w-screen flex flex-col items-center justify-center">
          <h1 className="text-2xl font-bold mb-4">Something went wrong.</h1>
          <div className="bg-white p-6 rounded-xl shadow-lg max-w-2xl w-full overflow-auto">
            <p className="font-mono text-sm font-bold text-red-700 mb-2">{this.state.error?.message}</p>
            <pre className="text-xs text-gray-500 whitespace-pre-wrap">{this.state.error?.stack}</pre>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  const [currentView, setCurrentView] = useState('strategy');

  const renderView = () => {
    switch (currentView) {
      case 'strategy':
        return <StrategyView />;
      case 'strategy-focus':
        return <StrategyFocusView />;
      case 'tactical':
        return <TacticalView />;
      case 'execution':
        return <ExecutionView />;
      case 'daily':
        return <DailyView />;
      default:
        return <StrategyView />;
    }
  };

  return (
    <ErrorBoundary>
      <Layout currentView={currentView} onViewChange={setCurrentView}>
        {renderView()}
      </Layout>
    </ErrorBoundary>
  );
}

export default App;
