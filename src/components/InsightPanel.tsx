import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, MessageSquare, Send, RefreshCw, AlertCircle, HelpCircle, ArrowUpRight, ArrowDownRight, Minus, Bot } from 'lucide-react';
import { Dataset, AIAnalysis, ChatMessage } from '../types';

interface InsightPanelProps {
  dataset: Dataset;
  analysis: AIAnalysis | null;
  loading: boolean;
  error: string | null;
  isDemoMode: boolean;
  onRefreshAnalysis: () => void;
  onAskQuestion: (question: string) => Promise<string>;
}

export default function InsightPanel({
  dataset,
  analysis,
  loading,
  error,
  isDemoMode,
  onRefreshAnalysis,
  onAskQuestion
}: InsightPanelProps) {
  const [activeTab, setActiveTab] = useState<'report' | 'chat'>('report');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize chat with greeting when dataset changes
  useEffect(() => {
    setChatMessages([
      {
        id: 'greet',
        sender: 'assistant',
        text: `Hello! I am your AI Data Analyst. I have successfully loaded **${dataset.name}**. You can ask me any specific analytical questions, such as asking for calculations, finding correlations, explaining unexpected dips/spikes, or requesting business optimization strategies based on this data. What can I analyze for you today?`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  }, [dataset]);

  // Scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || chatLoading) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}-u`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setChatLoading(true);

    try {
      const response = await onAskQuestion(text);
      const assistantMsg: ChatMessage = {
        id: `msg-${Date.now()}-a`,
        sender: 'assistant',
        text: response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `msg-${Date.now()}-err`,
        sender: 'assistant',
        text: `Sorry, I encountered an issue querying the model. Please check your Gemini configuration. Details: ${err.message || err}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages(prev => [...prev, errorMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[650px]">
      {/* Header Tabs */}
      <div className="border-b border-slate-200 bg-slate-50 p-4 flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('report')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              activeTab === 'report'
                ? 'bg-white text-indigo-700 shadow-sm border border-slate-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Sparkles className="w-4.5 h-4.5" />
            <span>AI Narrative Findings</span>
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              activeTab === 'chat'
                ? 'bg-white text-indigo-700 shadow-sm border border-slate-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <MessageSquare className="w-4.5 h-4.5" />
            <span>Interactive Analyst Chat</span>
          </button>
        </div>

        {activeTab === 'report' && (
          <button
            onClick={onRefreshAnalysis}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{analysis ? 'Re-Analyze' : 'Run AI Analysis'}</span>
          </button>
        )}
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* Demo Mode / Missing API Key warning */}
        {isDemoMode && (
          <div className="mb-4 flex items-start gap-3 p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-800 leading-relaxed">
            <AlertCircle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Local Sandbox Mode:</span> The database insights are currently generated locally using standard statistical regressions since your Google Gemini API key has not been customized. Customize your key in <strong>Settings &gt; Secrets</strong> to enable live AI reasoning and conversation grounding.
            </div>
          </div>
        )}

        {activeTab === 'report' ? (
          <div>
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="relative mb-4">
                  <div className="w-12 h-12 rounded-full border-4 border-indigo-200 border-t-indigo-600 animate-spin" />
                  <Sparkles className="w-5 h-5 text-indigo-500 absolute top-3.5 left-3.5 animate-pulse" />
                </div>
                <h3 className="font-semibold text-slate-700">Synthesizing Dataset Trends...</h3>
                <p className="text-xs text-slate-400 max-w-sm mt-1">
                  Gemini-3.5-flash is identifying cyclical trajectories, highlighting exceptions, and detailing optimization pathways.
                </p>
              </div>
            ) : error ? (
              <div className="p-6 text-center">
                <AlertCircle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
                <h3 className="font-semibold text-slate-800">Analysis Interrupted</h3>
                <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">{error}</p>
                <button
                  onClick={onRefreshAnalysis}
                  className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg transition-all"
                >
                  Retry Analysis
                </button>
              </div>
            ) : !analysis ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-12 h-12 bg-indigo-50 rounded-2xl flex items-center justify-center mb-4">
                  <Sparkles className="w-6 h-6 text-indigo-600" />
                </div>
                <h3 className="font-semibold text-slate-700">No Automated Insights Yet</h3>
                <p className="text-sm text-slate-400 max-w-sm mt-1 mb-5">
                  Click 'Run AI Analysis' to unleash Google Gemini on your active data records.
                </p>
                <button
                  onClick={onRefreshAnalysis}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-xl shadow-sm transition-all"
                >
                  Synthesize Trends Report
                </button>
              </div>
            ) : (
              <div className="space-y-6 animate-fade-in">
                {/* Executive Overview */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                    Executive Summary
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed font-light">
                    {analysis.overview}
                  </p>
                </div>

                {/* KPI Metric Summary Cards */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                    Highlighted KPIs
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {analysis.keyMetrics.map((metric, i) => (
                      <div key={i} className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col justify-between">
                        <div>
                          <span className="text-[11px] font-medium text-slate-400 block truncate">
                            {metric.name}
                          </span>
                          <span className="text-lg font-bold font-display text-slate-800 mt-1 block">
                            {metric.value}
                          </span>
                        </div>
                        {metric.change && (
                          <div className="flex items-center gap-1 mt-2.5">
                            {metric.trend === 'up' ? (
                              <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                            ) : metric.trend === 'down' ? (
                              <ArrowDownRight className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                            ) : (
                              <Minus className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            )}
                            <span className={`text-xs font-medium ${
                              metric.trend === 'up'
                                ? 'text-emerald-700'
                                : metric.trend === 'down'
                                ? 'text-rose-700'
                                : 'text-slate-500'
                            }`}>
                              {metric.change}
                            </span>
                          </div>
                        )}
                        <p className="text-[10px] text-slate-400 mt-1.5 leading-normal">
                          {metric.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Detailed Analysis */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                    Detailed Trends & Exception Analysis
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed font-light whitespace-pre-line">
                    {analysis.trendsAnalysis}
                  </p>
                </div>

                {/* Recommendations */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                    Strategic Recommendations
                  </h3>
                  <ul className="space-y-2">
                    {analysis.recommendations.map((rec, idx) => (
                      <li key={idx} className="text-sm text-slate-600 flex items-start gap-2.5">
                        <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        <span className="font-light leading-relaxed">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Suggested Questions */}
                {analysis.suggestedQuestions && analysis.suggestedQuestions.length > 0 && (
                  <div className="pt-2 border-t border-slate-100">
                    <span className="text-xs font-medium text-slate-400 block mb-2">
                      Suggested follow-up queries:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {analysis.suggestedQuestions.map((q, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            setActiveTab('chat');
                            handleSendMessage(q);
                          }}
                          className="flex items-center gap-1 px-3 py-1.5 bg-indigo-50/50 hover:bg-indigo-50 border border-indigo-100/50 text-indigo-700 rounded-lg text-xs font-medium transition-all text-left"
                        >
                          <HelpCircle className="w-3 h-3" />
                          <span>{q}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Chat pane */
          <div className="flex flex-col h-full -mx-6 -my-6">
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {chatMessages.map((msg) => {
                const isAI = msg.sender === 'assistant';
                return (
                  <div
                    key={msg.id}
                    className={`flex gap-3 max-w-[85%] ${isAI ? 'mr-auto' : 'ml-auto flex-row-reverse'}`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                      isAI ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-700'
                    }`}>
                      {isAI ? <Bot className="w-4 h-4" /> : <span className="text-xs font-bold font-display">U</span>}
                    </div>

                    <div className={`rounded-2xl p-4 text-sm leading-relaxed ${
                      isAI
                        ? 'bg-slate-50 text-slate-800'
                        : 'bg-indigo-600 text-white shadow-sm'
                    }`}>
                      <div className="whitespace-pre-wrap font-light">{msg.text}</div>
                      <span className={`text-[10px] block mt-2 text-right ${isAI ? 'text-slate-400' : 'text-indigo-200'}`}>
                        {msg.timestamp}
                      </span>
                    </div>
                  </div>
                );
              })}

              {chatLoading && (
                <div className="flex gap-3 max-w-[80%] mr-auto animate-pulse">
                  <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="bg-slate-50 rounded-2xl p-4 text-sm">
                    <div className="flex gap-1.5 items-center justify-center py-1">
                      <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Suggested quick ask buttons (displays inside chat screen context) */}
            {analysis && (
              <div className="px-6 py-2 border-t border-slate-100 bg-slate-50/30 flex gap-2 overflow-x-auto whitespace-nowrap scrollbar-none">
                <button
                  onClick={() => handleSendMessage('Summarize the top three high points and low points in our key metric.')}
                  className="px-3 py-1 bg-white border border-slate-200 text-slate-600 rounded-full text-xs font-medium hover:bg-slate-50 shrink-0"
                >
                  Find Peaks & Troughs
                </button>
                <button
                  onClick={() => handleSendMessage('Is there any linear correlation between our X-axis column and numeric metric values?')}
                  className="px-3 py-1 bg-white border border-slate-200 text-slate-600 rounded-full text-xs font-medium hover:bg-slate-50 shrink-0"
                >
                  Analyze Correlation
                </button>
                <button
                  onClick={() => handleSendMessage('Suggest two testable business hypotheses that could explain the current trends.')}
                  className="px-3 py-1 bg-white border border-slate-200 text-slate-600 rounded-full text-xs font-medium hover:bg-slate-50 shrink-0"
                >
                  Propose Hypotheses
                </button>
              </div>
            )}

            {/* Input form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(chatInput);
              }}
              className="border-t border-slate-100 p-4 bg-white flex gap-2"
            >
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask something about your data..."
                disabled={chatLoading}
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={!chatInput.trim() || chatLoading}
                className="w-11 h-11 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl flex items-center justify-center transition-all shadow-sm shrink-0 disabled:opacity-40"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
