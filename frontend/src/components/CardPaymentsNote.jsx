import { Info } from 'lucide-react'

/** Explains why the dashboard total differs from the number of rows on the Transactions page. */
export default function CardPaymentsNote({ count }) {
  if (!count) return null
  return (
    <p className="mt-4 flex items-start gap-2 text-xs text-ink-muted" role="note">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>
        {count} credit card bill payment{count === 1 ? ' is' : 's are'} left out of income and spending, because the card's own purchases are already counted.
        You can still see {count === 1 ? 'it' : 'them'} on the Transactions page.
      </span>
    </p>
  )
}
