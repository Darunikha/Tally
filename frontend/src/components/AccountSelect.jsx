import { useState } from 'react'
import { useFilters } from '../context/FilterContext'
import AccountForm from './AccountForm'

const NEW = '__new__'

/**
 * Choose the account a statement belongs to. Only accounts of the statement's kind are offered (a card statement can't
 * go into a bank account), and "New account…" creates one without leaving the page.
 */
export default function AccountSelect({ id = 'account', value, onChange, accountType, bankName, disabled, noneLabel = 'No account' }) {
  const { accounts, dataChanged } = useFilters()
  const [creating, setCreating] = useState(false)
  const options = accounts.filter((a) => !accountType || a.account_type === accountType)

  return (
    <>
      <select id={id} className="select" value={value || ''} disabled={disabled}
        onChange={(e) => (e.target.value === NEW ? setCreating(true) : onChange(e.target.value))}>
        <option value="">{noneLabel}</option>
        {options.map((a) => <option key={a.id} value={a.id}>{a.name}{a.last4 ? ` ••${a.last4}` : ''}</option>)}
        <option value={NEW}>+ New account…</option>
      </select>
      {creating && (
        <AccountForm preset={{ name: bankName || '', account_type: accountType, bank_name: bankName }} onClose={() => setCreating(false)}
          onSaved={(a) => { onChange(a.id); dataChanged() }} />
      )}
    </>
  )
}
