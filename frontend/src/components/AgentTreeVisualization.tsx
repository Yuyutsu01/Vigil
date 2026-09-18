'use client';

import React, { useState, useEffect } from 'react';

interface AgentTask {
  task_id: string;
  agent_name: string;
  status: 'completed' | 'failed' | 'timeout' | 'skipped' | 'running';
  duration_ms: number;
  tokens_consumed: number;
  error_message?: string | null;
}

interface AgentTreeData {
  coordination_id: string;
  review_run_id: string;
  tenant_id: string;
  status: string;
  total_tokens_consumed: number;
  total_wall_clock_ms: number;
  failed_agents: string[];
  tasks: AgentTask[];
}

interface AgentTreeVisualizationProps {
  token: string;
  runId: string;
}

export const AgentTreeVisualization: React.FC<AgentTreeVisualizationProps> = ({ token, runId }) => {
  const [data, setData] = useState<AgentTreeData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    async function fetchTree() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${apiBase}/v1/reviews/${runId}/agent-tree`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          if (res.status === 404) {
            setData(null);
            return;
          }
          throw new Error(`Failed to load agent tree: HTTP ${res.status}`);
        }

        const json = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message || 'Error fetching agent tree telemetry');
      } finally {
        setLoading(false);
      }
    }

    if (token && runId) {
      fetchTree();
    }
  }, [token, runId, apiBase]);

  const getStatusBadge = (status: AgentTask['status']) => {
    switch (status) {
      case 'completed':
        return <span style={{ background: '#166534', color: '#86efac', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>COMPLETED</span>;
      case 'failed':
        return <span style={{ background: '#991b1b', color: '#fca5a5', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>FAILED</span>;
      case 'timeout':
        return <span style={{ background: '#854d0e', color: '#fde047', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>TIMEOUT</span>;
      case 'skipped':
        return <span style={{ background: '#334155', color: '#cbd5e1', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>SKIPPED</span>;
      default:
        return <span style={{ background: '#1e3a8a', color: '#bfdbfe', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>RUNNING</span>;
    }
  };

  if (loading) {
    return (
      <div role="status" style={{ padding: '16px', color: '#94a3b8', fontSize: '0.875rem' }}>
        Loading agent execution telemetry...
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '6px', color: '#fca5a5', fontSize: '0.875rem' }}>
        {error}
      </div>
    );
  }

  if (!data || !data.tasks || data.tasks.length === 0) {
    return (
      <div style={{ padding: '16px', color: '#64748b', fontSize: '0.875rem', fontStyle: 'italic' }}>
        No specialist agent execution recorded for review {runId}.
      </div>
    );
  }

  return (
    <section
      aria-label="Multi-Agent Orchestration Tree"
      style={{
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '20px',
        color: '#f8fafc',
        marginTop: '16px',
      }}
    >
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #1e293b', paddingBottom: '12px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 600, color: '#e2e8f0' }}>
            Multi-Agent Orchestration DAG (FR-108)
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#64748b' }}>
            Coordination ID: <code>{data.coordination_id}</code>
          </p>
        </div>
        <div style={{ display: 'flex', gap: '16px', textAlign: 'right' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Wall Clock</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{data.total_wall_clock_ms} ms</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Total Tokens</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{data.total_tokens_consumed.toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>DAG Status</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: data.status === 'completed' ? '#4ade80' : '#f87171' }}>
              {data.status.toUpperCase()}
            </div>
          </div>
        </div>
      </header>

      <div role="tree" aria-label="Agent execution list" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {data.tasks.map((task) => {
          const isFailedOrTimeout = task.status === 'failed' || task.status === 'timeout';
          return (
            <div
              key={task.task_id}
              role="treeitem"
              tabIndex={0}
              style={{
                background: isFailedOrTimeout ? 'rgba(153, 27, 27, 0.15)' : '#1e293b',
                border: isFailedOrTimeout ? '1px solid #ef4444' : '1px solid #334155',
                borderRadius: '6px',
                padding: '12px 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isFailedOrTimeout ? '#ef4444' : '#22c55e' }} />
                <div>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: '#f1f5f9' }}>
                    {task.agent_name}
                  </span>
                  {task.error_message && (
                    <div style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '2px' }}>
                      Error: {task.error_message}
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  Duration: <strong>{task.duration_ms} ms</strong>
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  Tokens: <strong>{task.tokens_consumed.toLocaleString()}</strong>
                </span>
                {getStatusBadge(task.status)}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
