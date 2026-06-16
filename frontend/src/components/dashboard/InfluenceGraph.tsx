'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'
import type { Agent, InfluenceEdge } from './types'

interface Props {
  agents: Agent[]
  influences: InfluenceEdge[]
  highlightedAgentId?: number | null
  onClearHighlight?: () => void
}

interface NodeDatum extends d3.SimulationNodeDatum {
  id: number
  agent: Agent
}

interface LinkDatum extends d3.SimulationLinkDatum<NodeDatum> {
  edge: InfluenceEdge
  count: number
}

type NodeSelection = { type: 'node'; agent: Agent }
type EdgeSelection = { type: 'edge'; edge: InfluenceEdge; count: number }
type Selection = NodeSelection | EdgeSelection

function nodeColor(agent: Agent): string {
  if (!agent.is_active)                return '#ef4444'
  if (agent.last_decision === 'visit') return '#22c55e'
  if (agent.last_decision === 'skip')  return '#f59e0b'
  return '#94a3b8'
}

function ringColor(income: string): string {
  return income === 'B40' ? '#60a5fa'
       : income === 'M40' ? '#a78bfa'
       : '#f472b6'
}

export default function InfluenceGraph({ agents, influences, highlightedAgentId, onClearHighlight }: Props) {
  const svgRef  = useRef<SVGSVGElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const simRef  = useRef<d3.Simulation<NodeDatum, LinkDatum> | null>(null)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [selected, setSelected] = useState<Selection | null>(null)

  const draw = useCallback(() => {
    if (!svgRef.current || !wrapRef.current || agents.length === 0) return

    const W = wrapRef.current.clientWidth  || 600
    const H = wrapRef.current.clientHeight || 400

    // ── Deduplicate edges ──────────────────────────────────────────────────
    const edgeMap = new Map<string, LinkDatum>()
    for (const inf of influences) {
      const key = `${Math.min(inf.from_agent_id, inf.to_agent_id)}-${Math.max(inf.from_agent_id, inf.to_agent_id)}`
      if (edgeMap.has(key)) {
        edgeMap.get(key)!.count++
      } else {
        edgeMap.set(key, { source: inf.from_agent_id, target: inf.to_agent_id, edge: inf, count: 1 })
      }
    }

    // All agents as nodes
    const nodes: NodeDatum[] = agents.map(a => {
      // Preserve existing positions if simulation already ran
      const existing = simRef.current?.nodes().find(n => n.id === a.agent_id)
      return {
        id: a.agent_id,
        agent: a,
        x: existing?.x,
        y: existing?.y,
        vx: existing?.vx,
        vy: existing?.vy,
      }
    })
    const nodeById = new Map(nodes.map(n => [n.id, n]))

    const links: LinkDatum[] = Array.from(edgeMap.values())
      .filter(l => nodeById.has(l.edge.from_agent_id) && nodeById.has(l.edge.to_agent_id))
      .map(l => ({ ...l, source: nodeById.get(l.edge.from_agent_id)!, target: nodeById.get(l.edge.to_agent_id)! }))

    // ── D3 setup ───────────────────────────────────────────────────────────
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg.attr('width', W).attr('height', H)

    // Arrow marker
    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'arrow-influence')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 26).attr('refY', 0)
      .attr('markerWidth', 5).attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#6366f1')

    const g = svg.append('g')

    // Zoom + pan
    const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', e => g.attr('transform', e.transform))
    zoomRef.current = zoomBehavior
    svg.call(zoomBehavior)

    // Click on background to deselect
    svg.on('click', (e) => {
      if (e.target === svgRef.current) {
        setSelected(null)
        onClearHighlight?.()
      }
    })

    // Edges
    const link = g.append('g').selectAll<SVGLineElement, LinkDatum>('line')
      .data(links).join('line')
      .attr('stroke', '#6366f1')
      .attr('stroke-width', d => Math.min(1 + d.count * 0.5, 4))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrow-influence)')
      .style('cursor', 'pointer')
      .on('click', (_e, d) => setSelected({ type: 'edge', edge: d.edge, count: d.count }))
      .on('mouseenter', function(_e, d) { d3.select(this).attr('stroke-opacity', 1).attr('stroke-width', Math.min(2 + d.count * 0.5, 5)) })
      .on('mouseleave', function(_e, d) { d3.select(this).attr('stroke-opacity', 0.6).attr('stroke-width', Math.min(1 + d.count * 0.5, 4)) })

    // Edge labels (shown on hover)
    const linkLabel = g.append('g').selectAll<SVGTextElement, LinkDatum>('text')
      .data(links.filter(d => d.edge.original_message || d.edge.altered_message))
      .join('text')
      .attr('font-size', '0.65rem')
      .attr('fill', 'var(--gray-700)')
      .attr('text-anchor', 'middle')
      .attr('pointer-events', 'none')
      .attr('opacity', 0)
      .style('paint-order', 'stroke')
      .style('stroke', 'white')
      .style('stroke-width', '3px')
      .style('stroke-linecap', 'round')
      .style('stroke-linejoin', 'round')
      .text(d => {
        const msg = d.edge.altered_message || d.edge.original_message || ''
        return msg.length > 40 ? msg.substring(0, 40) + '...' : msg
      })

    // Show label on edge hover
    link.on('mouseenter', function(_, d) {
      d3.select(this).attr('stroke-opacity', 1).attr('stroke-width', Math.min(2 + d.count * 0.5, 5))
      linkLabel.filter(ld => ld.edge === d.edge).attr('opacity', 1)
    }).on('mouseleave', function(_, d) {
      d3.select(this).attr('stroke-opacity', 0.6).attr('stroke-width', Math.min(1 + d.count * 0.5, 4))
      linkLabel.attr('opacity', 0)
    })

    // Node groups
    const node = g.append('g').selectAll<SVGGElement, NodeDatum>('g')
      .data(nodes).join('g')
      .attr('class', 'node-group')
      .style('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, NodeDatum>()
          .on('start', (e, d) => { if (!e.active) simRef.current?.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
          .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y })
          .on('end',   (e, d) => { if (!e.active) simRef.current?.alphaTarget(0); d.fx = null; d.fy = null })
      )
      .on('click', (_e, d) => setSelected({ type: 'node', agent: d.agent }))

    // Income ring (outer)
    node.append('circle')
      .attr('r', 22)
      .attr('fill', 'none')
      .attr('stroke', d => ringColor(d.agent.income_level))
      .attr('stroke-width', 2.5)

    // Agent fill circle
    node.append('circle')
      .attr('r', 19)
      .attr('fill', d => nodeColor(d.agent))
      .attr('stroke', 'white')
      .attr('stroke-width', 1.5)

    // Agent number label
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', '0.65rem')
      .attr('font-weight', '700')
      .attr('fill', 'white')
      .attr('pointer-events', 'none')
      .text(d => {
        // Extract number from persona_name (e.g. "Customer 12" → "12")
        const match = d.agent.persona_name.match(/\d+/)
        if (match) return match[0]
        // Fallback to initials
        return d.agent.persona_name.split(' ').map((w: string) => w[0]).join('').slice(0, 3).toUpperCase()
      })

    // Force simulation
    if (simRef.current) simRef.current.stop()
    const sim = d3.forceSimulation<NodeDatum>(nodes)
      .force('link', d3.forceLink<NodeDatum, LinkDatum>(links).id(d => d.id).distance(80).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(26))
    simRef.current = sim

    sim.on('tick', () => {
      link
        .attr('x1', d => (d.source as NodeDatum).x ?? 0)
        .attr('y1', d => (d.source as NodeDatum).y ?? 0)
        .attr('x2', d => (d.target as NodeDatum).x ?? 0)
        .attr('y2', d => (d.target as NodeDatum).y ?? 0)
      
      linkLabel
        .attr('x', d => ((d.source as NodeDatum).x! + (d.target as NodeDatum).x!) / 2)
        .attr('y', d => ((d.source as NodeDatum).y! + (d.target as NodeDatum).y!) / 2 - 5)
      
      node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => sim.stop()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents.length, influences.length])

  // Update node colors in place when agent decisions change (no full redraw)
  useEffect(() => {
    if (!svgRef.current || agents.length === 0) return
    const svg = d3.select(svgRef.current)

    svg.selectAll<SVGGElement, NodeDatum>('g.node-group')
      .each(function(d) {
        const updatedAgent = agents.find(a => a.agent_id === d.id)
        if (updatedAgent) {
          d.agent = updatedAgent
          d3.select(this).select('circle:nth-child(2)')
            .transition().duration(300)
            .attr('fill', nodeColor(updatedAgent))
        }
      })
  }, [agents])

  useEffect(() => {
    draw()
  }, [draw])

  // Redraw on resize
  useEffect(() => {
    const obs = new ResizeObserver(() => draw())
    if (wrapRef.current) obs.observe(wrapRef.current)
    return () => obs.disconnect()
  }, [draw])

  // Highlight agent when selected from activity feed
  useEffect(() => {
    if (!svgRef.current || !wrapRef.current) return
    const svg = d3.select(svgRef.current)
    
    // Reset all nodes
    svg.selectAll<SVGGElement, NodeDatum>('g.node-group')
      .select('circle:nth-child(1)') // outer ring
      .attr('stroke-width', 2.5)
      .attr('stroke-dasharray', null)
    
    svg.selectAll<SVGGElement, NodeDatum>('g.node-group')
      .style('opacity', highlightedAgentId != null ? 0.3 : 1)
      .style('filter', '')
    
    if (highlightedAgentId != null) {
      // Highlight the selected agent
      svg.selectAll<SVGGElement, NodeDatum>('g.node-group')
        .filter(d => d.id === highlightedAgentId)
        .style('opacity', 1)
        .style('filter', 'drop-shadow(0 0 8px rgba(99, 102, 241, 0.7))')
        .select('circle:nth-child(1)')
        .attr('stroke-width', 4)
        .attr('stroke-dasharray', '4,2')
      
      // Pan + zoom to center on the selected agent
      const targetNode = simRef.current?.nodes().find(n => n.id === highlightedAgentId)
      if (targetNode && targetNode.x != null && targetNode.y != null && zoomRef.current) {
        const W = wrapRef.current!.clientWidth || 600
        const H = wrapRef.current!.clientHeight || 400
        const scale = 1.5 // zoom in a bit to focus
        const tx = W / 2 - targetNode.x * scale
        const ty = H / 2 - targetNode.y * scale
        const transform = d3.zoomIdentity.translate(tx, ty).scale(scale)

        svg.transition()
          .duration(600)
          .call(zoomRef.current.transform, transform)
      }

      // Also show the detail panel for this agent
      const agent = agents.find(a => a.agent_id === highlightedAgentId)
      if (agent) {
        setSelected({ type: 'node', agent })
      }
    }
  }, [highlightedAgentId, agents])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      background: 'var(--white)', borderRadius: 8,
      border: '1px solid var(--gray-200)',
      position: 'relative', height: '100%',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '0.5rem',
        padding: '0.6rem 0.75rem',
        borderBottom: '1px solid var(--gray-100)',
        flexShrink: 0,
      }}>
        <svg style={{ width: 14, height: 14, color: 'var(--gray-600)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
        </svg>
        <span style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--gray-600)' }}>
          Customers
        </span>

        {/* Legend */}
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.72rem', fontWeight: 500 }}>
          <LegendDot color="#22c55e" label="Visiting" />
          <LegendDot color="#f59e0b" label="Skipping" />
          <LegendDot color="#ef4444" label="Churned" />
        </span>
      </div>

      {/* Graph canvas */}
      <div ref={wrapRef} style={{ flex: 1, overflow: 'hidden', position: 'relative', minHeight: 0 }}>
        {agents.length === 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--gray-400)', fontSize: '0.85rem',
            textAlign: 'center', padding: '2rem',
          }}>
            Customers will appear here when a simulation starts
          </div>
        ) : (
          <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />
        )}
      </div>

      {/* Detail panel on click */}
      {selected && (
        <div style={{
          position: 'absolute', bottom: '0.75rem', left: '0.75rem', right: '0.75rem',
          background: 'white', borderWidth: 1, borderStyle: 'solid', borderColor: 'var(--gray-200)',
          borderRadius: 8, padding: '0.75rem',
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          fontSize: '0.8rem', zIndex: 10,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
            <strong style={{ fontSize: '0.875rem' }}>
              {selected.type === 'node' ? selected.agent.persona_name : 'Influence Edge'}
            </strong>
            <button onClick={() => { setSelected(null); onClearHighlight?.() }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-400)', fontSize: '1rem', lineHeight: 1, padding: 0 }}>✕</button>
          </div>

          {selected.type === 'node' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Personality section */}
              {selected.agent.personality && (
                <div style={{ 
                  padding: '0.75rem',
                  background: 'var(--gray-50)',
                  borderRadius: 6,
                  borderLeft: '3px solid #6366f1'
                }}>
                  <div style={{ 
                    fontSize: '0.7rem', 
                    fontWeight: 600, 
                    color: 'var(--gray-500)', 
                    marginBottom: '0.4rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    Personality
                  </div>
                  <div style={{ 
                    color: 'var(--gray-700)', 
                    fontSize: '0.75rem',
                    lineHeight: 1.5
                  }}>
                    {selected.agent.personality}
                  </div>
                </div>
              )}
              
              {/* Stats grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem 1rem' }}>
                <TRow label={['Micro','Small','Medium'].includes(selected.agent.income_level) ? 'Size' : 'Income'} value={selected.agent.income_level} />
                <TRow label={['Micro','Small','Medium'].includes(selected.agent.income_level) ? 'Segment' : 'Age'} value={selected.agent.age_range} />
                <TRow label="Status"         value={selected.agent.is_active ? 'Active' : 'Churned'} />
                <TRow label="Last decision"  value={selected.agent.last_decision ?? '—'} />
              </div>
              
              {selected.agent.reasoning && (
                <div style={{ 
                  marginTop: '0.25rem', 
                  color: 'var(--gray-600)', 
                  fontStyle: 'italic', 
                  fontSize: '0.75rem',
                  padding: '0.5rem',
                  background: 'var(--gray-50)',
                  borderRadius: 4
                }}>
                  {selected.agent.reasoning}
                </div>
              )}
            </div>
          )}

          {selected.type === 'edge' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Stats grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem 1rem' }}>
                <TRow label="From"  value={`Customer ${selected.edge.from_agent_id}`} />
                <TRow label="To"    value={`Customer ${selected.edge.to_agent_id}`} />
                <TRow label="Times" value={`${selected.count}×`} />
              </div>
              
              {/* Show final message (altered if available, otherwise original) */}
              {(selected.edge.altered_message || selected.edge.original_message) && (
                <div style={{ marginTop: '0.25rem' }}>
                  <div style={{ 
                    fontSize: '0.7rem', 
                    fontWeight: 600, 
                    color: 'var(--gray-500)', 
                    marginBottom: '0.3rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    Message
                  </div>
                  <div style={{ 
                    color: 'var(--gray-700)', 
                    fontSize: '0.75rem', 
                    fontStyle: 'italic',
                    padding: '0.5rem',
                    background: 'var(--gray-50)',
                    borderRadius: 4,
                    borderLeft: '3px solid #6366f1'
                  }}>
                    "{selected.edge.altered_message || selected.edge.original_message}"
                  </div>
                </div>
              )}
              
              {!selected.edge.original_message && !selected.edge.altered_message && (
                <div style={{ marginTop: '0.25rem', color: 'var(--gray-600)', fontSize: '0.75rem' }}>
                  Customer {selected.edge.from_agent_id} influenced Customer {selected.edge.to_agent_id} through their decision.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
      {label}
    </span>
  )
}

function TRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontSize: '0.68rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</span>
      <span style={{ color: 'var(--gray-900)', textTransform: 'capitalize' }}>{value}</span>
    </div>
  )
}
