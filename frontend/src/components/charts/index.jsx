/**
 * Chart kit. Conventions (dataviz method): one y-axis only, 2px lines, rounded 4px bar ends,
 * recessive grid, hover tooltip on every chart, legends for >= 2 series, colour follows the
 * entity (category colour), never its rank. Values in text use ink colours, not series colours.
 */
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { compactINR, formatINR } from '../../lib/format'

export const SERIES = { income: '#2F7D55', expense: '#3D5A80', upi: '#1BAF7A', muted: '#B8B2A7' }
const AXIS = { fontSize: 11, fill: '#6B7280' }
const GRID = '#ECECE6'

function TooltipBox({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-line bg-white px-3 py-2 text-xs shadow-pop">
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
export function TrendArea({ data, dataKey = 'expense', name = 'Spent', color = SERIES.income, height = 260 }) {
  const id = `grad-${dataKey}-${color.slice(1)}`
  const dense = data.length > 20
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.22} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={compactINR} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ stroke: '#9CA3AF', strokeDasharray: '3 3' }} />
        <Area type="monotone" dataKey={dataKey} name={name} stroke={color} strokeWidth={2} fill={`url(#${id})`}
          dot={dense ? false : { r: 4, fill: color, stroke: '#fff', strokeWidth: 2 }}
          activeDot={{ r: 5, fill: color, stroke: '#fff', strokeWidth: 2 }} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/** Income vs expense grouped bars on one axis. */
export function IncomeExpenseBars({ data, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="28%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={compactINR} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(20,33,61,0.04)' }} />
        <Legend verticalAlign="top" content={<LegendRow />} />
        <Bar dataKey="income" name="Income" fill={SERIES.income} radius={[4, 4, 0, 0]} maxBarSize={28} />
        <Bar dataKey="expense" name="Expenses" fill={SERIES.expense} radius={[4, 4, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Two-line comparison on a single axis (income vs expense over time). */
export function DualLine({ data, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={compactINR} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ stroke: '#9CA3AF', strokeDasharray: '3 3' }} />
        <Legend verticalAlign="top" content={<LegendRow />} />
        <Line type="monotone" dataKey="income" name="Income" stroke={SERIES.income} strokeWidth={2} dot={false} activeDot={{ r: 5 }} />
        <Line type="monotone" dataKey="expense" name="Expenses" stroke={SERIES.expense} strokeWidth={2} dot={false} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Simple vertical bars for one measure. */
export function SimpleBars({ data, dataKey = 'amount', xKey = 'label', name = 'Spent', color = SERIES.expense, height = 240, valueFormatter = compactINR }) {
  const tilt = data.length > 6 && Math.max(...data.map((d) => String(d[xKey]).length)) > 5
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barCategoryGap="24%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval={0} angle={tilt ? -20 : 0} textAnchor={tilt ? 'end' : 'middle'} height={tilt ? 48 : 30} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={valueFormatter} width={56} />
        <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(20,33,61,0.04)' }} />
        <Bar dataKey={dataKey} name={name} fill={color} radius={[4, 4, 0, 0]} maxBarSize={40} />
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
  const data = foldCategories(rows, max)
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row">
      <div className="relative shrink-0" style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="amount" nameKey="name" innerRadius="64%" outerRadius="100%" paddingAngle={1}
              stroke="#fff" strokeWidth={2} startAngle={90} endAngle={-270} isAnimationActive
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
            <span className="min-w-0 flex-1 truncate text-ink-soft" title={d.folded ? d.folded.join(', ') : d.name}>{d.name}</span>
            <span className="hidden text-xs text-ink-faint sm:inline">{formatINR(d.amount)}</span>
            <span className="w-12 text-right font-semibold text-ink">{d.percentage.toFixed(0)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Horizontal ranking bars rendered in HTML (crisp labels, no colour-only identity). */
export function RankBars({ rows, valueKey = 'total', labelKey = 'merchant', color = SERIES.income, sub }) {
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
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(r[valueKey] / max) * 100}%`, background: r.category_color || color }} />
          </div>
          {sub && <p className="mt-1 text-xs text-ink-muted">{sub(r)}</p>}
        </li>
      ))}
    </ul>
  )
}
