/**
 * Chart kit. Conventions (dataviz method): one y-axis only, 2px lines, rounded 4px bar ends,
 * recessive grid, hover tooltip on every chart, legends for >= 2 series, colour follows the
 * entity (category colour), never its rank. Values in text use ink colours, not series colours.
 *
 * Series colours and chart chrome are theme-aware (see PALETTE): on a dark surface the navy "expense" series is lightened
 * so it keeps at least 3:1 contrast. `color` props accept a series name ('income', 'expense', 'upi') or any hex colour.
 */
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useTheme } from '../../context/ThemeContext'
import { compactINR, formatINR } from '../../lib/format'

export const PALETTE = {
  light: { income: '#2F7D55', expense: '#3D5A80', upi: '#1BAF7A', muted: '#B8B2A7', axis: '#6B7280', grid: '#ECECE6', cursor: '#9CA3AF', ring: '#FFFFFF', hover: 'rgba(20,33,61,0.04)' },
  dark: { income: '#4FA877', expense: '#6E94C7', upi: '#3CC48E', muted: '#8F8A80', axis: '#9AA89F', grid: '#26322A', cursor: '#76847B', ring: '#161F19', hover: 'rgba(255,255,255,0.06)' },
}
export const SERIES = PALETTE.light // light-theme series colours, for code that has no theme context

export function useChartTheme() {
  const { resolved } = useTheme()
  const t = PALETTE[resolved] || PALETTE.light
  return { ...t, axis: { fontSize: 11, fill: t.axis }, resolve: (c) => t[c] || c }
}

function TooltipBox({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-pop">
      <p className="mb-1 font-semibold text-ink">{labelFormatter ? labelFormatter(label, payload) : label}</p>
      {payload.map((p) => (
        <p key={p.dataKey || p.name} className="flex items-center gap-2 text-ink-soft">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.payload?.color }} />
          <span>{p.name}</span>
          <span className="ml-auto pl-3 font-semibold text-ink">{formatINR(p.value)}</span>
        </p>
      ))}
    </div>
  )
}

function LegendRow({ payload }) {
  return (
    <div className="flex flex-wrap justify-end gap-4 pb-2 text-xs text-ink-soft">
      {payload.map((p) => (
        <span key={p.value} className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />{p.value}
        </span>
      ))}
    </div>
  )
}

/** Single-series area (e.g. spending trend). */
export function TrendArea({ data, dataKey = 'expense', name = 'Spent', color = 'income', height = 260 }) {
  const t = useChartTheme()
  const stroke = t.resolve(color)
  const id = `grad-${dataKey}-${stroke.slice(1)}`
  const dense = data.length > 20
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.22} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="label" tick={t.axis} tickLine={false} axisLine={{ stroke: t.grid }} minTickGap={24} />
        <YAxis tick={t.axis} tickLine={false} axisLine={false} tickFormatter={compactINR} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ stroke: t.cursor, strokeDasharray: '3 3' }} />
        <Area type="monotone" dataKey={dataKey} name={name} stroke={stroke} strokeWidth={2} fill={`url(#${id})`}
          dot={dense ? false : { r: 4, fill: stroke, stroke: t.ring, strokeWidth: 2 }}
          activeDot={{ r: 5, fill: stroke, stroke: t.ring, strokeWidth: 2 }} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/** Income vs expense grouped bars on one axis. */
export function IncomeExpenseBars({ data, height = 260 }) {
  const t = useChartTheme()
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="28%">
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="label" tick={t.axis} tickLine={false} axisLine={{ stroke: t.grid }} />
        <YAxis tick={t.axis} tickLine={false} axisLine={false} tickFormatter={compactINR} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ fill: t.hover }} />
        <Legend verticalAlign="top" content={<LegendRow />} />
        <Bar dataKey="income" name="Income" fill={t.income} radius={[4, 4, 0, 0]} maxBarSize={28} />
        <Bar dataKey="expense" name="Expenses" fill={t.expense} radius={[4, 4, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Two-line comparison on a single axis (income vs expense over time). */
export function DualLine({ data, height = 260 }) {
  const t = useChartTheme()
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="label" tick={t.axis} tickLine={false} axisLine={{ stroke: t.grid }} minTickGap={24} />
        <YAxis tick={t.axis} tickLine={false} axisLine={false} tickFormatter={compactINR} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ stroke: t.cursor, strokeDasharray: '3 3' }} />
        <Legend verticalAlign="top" content={<LegendRow />} />
        <Line type="monotone" dataKey="income" name="Income" stroke={t.income} strokeWidth={2} dot={false} activeDot={{ r: 5 }} />
        <Line type="monotone" dataKey="expense" name="Expenses" stroke={t.expense} strokeWidth={2} dot={false} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Simple vertical bars for one measure. */
export function SimpleBars({ data, dataKey = 'amount', xKey = 'label', name = 'Spent', color = 'expense', height = 240, valueFormatter = compactINR }) {
  const t = useChartTheme()
  const tilt = data.length > 6 && Math.max(...data.map((d) => String(d[xKey]).length)) > 5
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barCategoryGap="24%">
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} tick={t.axis} tickLine={false} axisLine={{ stroke: t.grid }} interval={0} angle={tilt ? -20 : 0} textAnchor={tilt ? 'end' : 'middle'} height={tilt ? 48 : 30} />
        <YAxis tick={t.axis} tickLine={false} axisLine={false} tickFormatter={valueFormatter} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ fill: t.hover }} />
        <Bar dataKey={dataKey} name={name} fill={t.resolve(color)} radius={[4, 4, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Donut by category. Top `max` slices keep their category colour; the rest fold into "Others".
 * Legend with percentage acts as the non-colour identity cue.
 */
export function foldCategories(rows, max = 5) {
  if (rows.length <= max + 1) return rows
  const top = rows.slice(0, max)
  const rest = rows.slice(max)
  const amount = rest.reduce((s, r) => s + r.amount, 0)
  const pctSum = rest.reduce((s, r) => s + r.percentage, 0)
  return [...top, { name: 'Others', color: SERIES.muted, amount, percentage: Math.round(pctSum * 10) / 10, count: rest.reduce((s, r) => s + r.count, 0), folded: rest.map((r) => r.name) }]
}

export function CategoryDonut({ rows, total, max = 5, height = 220, onSelect }) {
  const t = useChartTheme()
  const data = foldCategories(rows, max).map((d) => (d.folded ? { ...d, color: t.muted } : d))
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row">
      <div className="relative shrink-0" style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="amount" nameKey="name" innerRadius="64%" outerRadius="100%" paddingAngle={1}
              stroke={t.ring} strokeWidth={2} startAngle={90} endAngle={-270} isAnimationActive
              onClick={(d) => onSelect && !d.folded && onSelect(d)} className={onSelect ? 'cursor-pointer' : ''}>
              {data.map((d) => <Cell key={d.name} fill={d.color} />)}
            </Pie>
            <Tooltip content={<TooltipBox labelFormatter={(_, p) => p?.[0]?.payload?.folded ? `Others: ${p[0].payload.folded.join(', ')}` : p?.[0]?.name} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-extrabold text-ink sm:text-xl">{formatINR(total)}</span>
          <span className="text-xs text-ink-muted">Total</span>
        </div>
      </div>
      <ul className="w-full min-w-0 flex-1 space-y-2.5">
        {data.map((d) => (
          <li key={d.name} className="flex items-center gap-3 text-sm">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: d.color }} />
            <span className="min-w-0 flex-1" title={d.folded ? d.folded.join(', ') : d.name}>
              <span className="block truncate text-ink-soft">{d.name}</span>
              <span className="block text-xs text-ink-muted">{formatINR(d.amount)}</span>
            </span>
            <span className="w-12 text-right font-semibold text-ink">{d.percentage.toFixed(0)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Horizontal ranking bars rendered in HTML (crisp labels, no colour-only identity). */
export function RankBars({ rows, valueKey = 'total', labelKey = 'merchant', color = 'income', sub }) {
  const t = useChartTheme()
  const max = Math.max(...rows.map((r) => r[valueKey]), 1)
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r[labelKey]} title={`${r[labelKey]}: ${formatINR(r[valueKey])}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium text-ink">{r[labelKey]}</span>
            <span className="shrink-0 font-semibold text-ink">{formatINR(r[valueKey])}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-canvas">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(r[valueKey] / max) * 100}%`, background: r.category_color || t.resolve(color) }} />
          </div>
          {sub && <p className="mt-1 text-xs text-ink-muted">{sub(r)}</p>}
        </li>
      ))}
    </ul>
  )
}
