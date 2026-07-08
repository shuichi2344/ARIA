'use client'

import { useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'

interface SalesRecord {
  record_id: string
  sale_date: string
  total_sales: number
  transaction_count: number | null
  source: string
  notes: string | null
}

type FilterMode = 'daily' | 'monthly' | 'yearly'

interface Props {
  records: SalesRecord[]
  filter: FilterMode
}

interface DataPoint {
  date: Date
  label: string
  total_sales: number
}

export default function SalesChart({ records, filter }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  // Aggregate data based on filter
  const chartData = useMemo((): DataPoint[] => {
    if (!records.length) return []

    const sorted = [...records].sort((a, b) => a.sale_date.localeCompare(b.sale_date))

    if (filter === 'daily') {
      return sorted.map(r => ({
        date: new Date(r.sale_date),
        label: r.sale_date,
        total_sales: r.total_sales,
      }))
    }

    if (filter === 'monthly') {
      const grouped: Record<string, number> = {}
      for (const r of sorted) {
        const key = r.sale_date.slice(0, 7) // YYYY-MM
        grouped[key] = (grouped[key] || 0) + r.total_sales
      }
      return Object.entries(grouped).map(([key, total]) => ({
        date: new Date(key + '-01'),
        label: key,
        total_sales: total,
      }))
    }

    // yearly
    const grouped: Record<string, number> = {}
    for (const r of sorted) {
      const key = r.sale_date.slice(0, 4) // YYYY
      grouped[key] = (grouped[key] || 0) + r.total_sales
    }
    return Object.entries(grouped).map(([key, total]) => ({
      date: new Date(key + '-01-01'),
      label: key,
      total_sales: total,
    }))
  }, [records, filter])

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || chartData.length === 0) return

    const container = containerRef.current
    const width = container.clientWidth
    const height = 320
    const margin = { top: 20, right: 30, bottom: 40, left: 60 }
    const innerWidth = width - margin.left - margin.right
    const innerHeight = height - margin.top - margin.bottom

    // Clear previous
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg.attr('width', width).attr('height', height)

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    // Scales
    const xScale = d3.scaleTime()
      .domain(d3.extent(chartData, d => d.date) as [Date, Date])
      .range([0, innerWidth])

    const yMax = d3.max(chartData, d => d.total_sales) || 0
    const yScale = d3.scaleLinear()
      .domain([0, yMax * 1.1])
      .range([innerHeight, 0])

    // Grid lines
    g.append('g')
      .attr('class', 'grid')
      .selectAll('line')
      .data(yScale.ticks(5))
      .enter().append('line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', d => yScale(d))
      .attr('y2', d => yScale(d))
      .attr('stroke', '#e5e7eb')
      .attr('stroke-dasharray', '3,3')

    // Area
    const area = d3.area<DataPoint>()
      .x(d => xScale(d.date))
      .y0(innerHeight)
      .y1(d => yScale(d.total_sales))
      .curve(d3.curveMonotoneX)

    g.append('path')
      .datum(chartData)
      .attr('fill', 'url(#areaGradient)')
      .attr('d', area)

    // Gradient definition
    const defs = svg.append('defs')
    const gradient = defs.append('linearGradient')
      .attr('id', 'areaGradient')
      .attr('x1', '0%').attr('y1', '0%')
      .attr('x2', '0%').attr('y2', '100%')
    gradient.append('stop').attr('offset', '0%').attr('stop-color', 'var(--accent)').attr('stop-opacity', 0.2)
    gradient.append('stop').attr('offset', '100%').attr('stop-color', 'var(--accent)').attr('stop-opacity', 0)

    // Line
    const line = d3.line<DataPoint>()
      .x(d => xScale(d.date))
      .y(d => yScale(d.total_sales))
      .curve(d3.curveMonotoneX)

    g.append('path')
      .datum(chartData)
      .attr('fill', 'none')
      .attr('stroke', 'var(--accent)')
      .attr('stroke-width', 2.5)
      .attr('d', line)

    // Dots
    g.selectAll('.dot')
      .data(chartData)
      .enter().append('circle')
      .attr('cx', d => xScale(d.date))
      .attr('cy', d => yScale(d.total_sales))
      .attr('r', chartData.length > 30 ? 2 : 4)
      .attr('fill', 'var(--accent)')
      .attr('stroke', 'white')
      .attr('stroke-width', 1.5)

    // Axes
    const xAxis = filter === 'yearly'
      ? d3.axisBottom(xScale).ticks(chartData.length).tickFormat(d => d3.timeFormat('%Y')(d as Date))
      : filter === 'monthly'
        ? d3.axisBottom(xScale).ticks(Math.min(chartData.length, 12)).tickFormat(d => d3.timeFormat('%b %Y')(d as Date))
        : d3.axisBottom(xScale).ticks(Math.min(chartData.length, 10)).tickFormat(d => d3.timeFormat('%d %b')(d as Date))

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .selectAll('text')
      .style('font-size', '0.7rem')
      .style('fill', '#6b7280')

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(5).tickFormat(d => `RM ${d3.format(',.0f')(d as number)}`))
      .selectAll('text')
      .style('font-size', '0.7rem')
      .style('fill', '#6b7280')

    // Remove domain lines
    g.selectAll('.domain').remove()

    // Tooltip
    const tooltip = d3.select(container).select('.chart-tooltip')
    const tooltipEl = tooltip.empty()
      ? d3.select(container).append('div').attr('class', 'chart-tooltip').style('position', 'absolute').style('display', 'none')
        .style('background', 'white').style('border', '1px solid #e5e7eb').style('border-radius', '8px')
        .style('padding', '0.5rem 0.75rem').style('font-size', '0.8rem').style('box-shadow', '0 4px 12px rgba(0,0,0,0.1)')
        .style('pointer-events', 'none').style('z-index', '10')
      : tooltip

    // Overlay for mouse interaction
    g.append('rect')
      .attr('width', innerWidth)
      .attr('height', innerHeight)
      .attr('fill', 'transparent')
      .on('mousemove', (event: MouseEvent) => {
        const [mx] = d3.pointer(event)
        const bisect = d3.bisector<DataPoint, Date>(d => d.date).left
        const date = xScale.invert(mx)
        const idx = bisect(chartData, date, 1)
        const d0 = chartData[idx - 1]
        const d1 = chartData[idx]
        if (!d0) return
        const d = d1 && (date.getTime() - d0.date.getTime() > d1.date.getTime() - date.getTime()) ? d1 : d0

        tooltipEl
          .style('display', 'block')
          .style('left', `${xScale(d.date) + margin.left + 10}px`)
          .style('top', `${yScale(d.total_sales) + margin.top - 10}px`)
          .html(`<strong>${d.label}</strong><br/>RM ${d.total_sales.toLocaleString('en-MY', { minimumFractionDigits: 2 })}`)
      })
      .on('mouseleave', () => {
        tooltipEl.style('display', 'none')
      })

  }, [chartData, filter])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <svg ref={svgRef} style={{ width: '100%', height: 320 }} />
    </div>
  )
}
