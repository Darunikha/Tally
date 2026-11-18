import { Link } from 'react-router-dom'
import { CloudUpload } from 'lucide-react'
import { Card, EmptyState } from '../ui'
import DemoDataButton from './DemoDataButton'

/** What every analysis page shows before the first statement is added: one clear next step, never an "all clear". */
export default function NoStatementsYet({ message = 'Upload a bank or credit card statement and this page fills in on its own.' }) {
  return (
    <Card className="card-pad">
      <EmptyState icon={CloudUpload} title="Add your first statement" message={message}
        action={(
          <div className="flex flex-wrap justify-center gap-2">
            <Link to="/upload" className="btn-primary"><CloudUpload className="h-4 w-4" />Upload a statement</Link>
            <DemoDataButton />
          </div>
        )} />
      <p className="mx-auto mt-2 max-w-md pb-6 text-center text-xs text-ink-muted">
        CSV, Excel and PDF work, including password-protected e-statements. Demo data is made up, so you can look around safely and remove it later.
      </p>
    </Card>
  )
}
