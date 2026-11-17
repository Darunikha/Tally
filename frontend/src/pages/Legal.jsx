import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { Logo } from '../components/layout/Sidebar'
import { useAuth } from '../context/AuthContext'
import { LEGAL, isPlaceholder } from '../legal/config'

const L = LEGAL

function LegalLayout({ title, intro, sections }) {
  const { user } = useAuth()
  const { hash } = useLocation()
  const unfilled = Object.values(L).some(isPlaceholder)
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [hash, title])

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-10 border-b border-line bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to={user ? '/' : '/login'}><Logo className="[&_span]:text-lg [&_svg]:h-7 [&_svg]:w-7" /></Link>
          <nav className="flex gap-1 text-sm font-semibold">
            <Link to="/privacy" className="rounded-lg px-3 py-1.5 text-ink-soft hover:bg-white">Privacy</Link>
            <Link to="/terms" className="rounded-lg px-3 py-1.5 text-ink-soft hover:bg-white">Terms</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 pb-20 pt-8 sm:px-6">
        <Link to={user ? '/settings' : '/login'} className="mb-6 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:underline">
          <ArrowLeft className="h-4 w-4" />{user ? 'Back to Tally' : 'Back to sign in'}
        </Link>
        {unfilled && (
          <div role="note" className="mb-6 flex gap-3 rounded-2xl border border-warn-100 bg-warn-50 p-4 text-sm text-ink-soft">
            <AlertTriangle className="h-5 w-5 shrink-0 text-warn-500" />
            <p><b className="text-ink">Template - not yet finalised.</b> The operator's details in square brackets must be filled in
              (<code className="rounded bg-white px-1">frontend/src/legal/config.js</code>) and the text reviewed by a qualified lawyer before
              this service is offered to the public.</p>
          </div>
        )}
        <article className="card card-pad sm:p-10">
          <h1 className="text-3xl font-extrabold tracking-tight text-ink">{title}</h1>
          <p className="mt-2 text-sm text-ink-muted">Effective {L.effectiveDate} · Version {L.version}</p>
          <div className="mt-6 space-y-3 text-[0.95rem] leading-relaxed text-ink-soft">{intro}</div>

          <nav aria-label="Contents" className="mt-8 rounded-xl bg-canvas p-4">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-muted">Contents</p>
            <ol className="grid gap-1 text-sm sm:grid-cols-2">
              {sections.map((s, i) => <li key={s.id}><a href={`#${s.id}`} className="text-brand-700 hover:underline">{i + 1}. {s.title}</a></li>)}
            </ol>
          </nav>

          {sections.map((s, i) => (
            <section key={s.id} id={s.id} className="mt-10 scroll-mt-20">
              <h2 className="text-lg font-bold text-ink">{i + 1}. {s.title}</h2>
              <div className="mt-3 space-y-3 text-[0.95rem] leading-relaxed text-ink-soft [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_ul]:space-y-1.5 [&_b]:text-ink">{s.body}</div>
            </section>
          ))}
        </article>
      </main>
    </div>
  )
}

const Contact = () => (
  <ul>
    <li>Data Fiduciary: <b>{L.operator}</b>, {L.address}</li>
    <li>Privacy questions: <b>{L.contactEmail}</b></li>
    <li>Grievance Officer: <b>{L.grievanceOfficer}</b> - <b>{L.grievanceEmail}</b></li>
  </ul>
)

export function PrivacyPolicy() {
  return (
    <LegalLayout
      title="Privacy Policy"
      intro={<>
        <p>This policy explains what personal data {L.serviceName} processes, why, and the rights you have. It is written to meet the
          notice requirements of India's <b className="text-ink">Digital Personal Data Protection Act, 2023</b> ("DPDP Act") and the rules made under it.</p>
        <p>In short: you upload your own bank statements, {L.serviceName} analyses them for you, and that's all your data is used for.
          We never connect to your bank, never ask for bank logins or OTPs, never sell data, and never send your statements to external AI services.</p>
      </>}
      sections={[
        { id: 'who', title: 'Who we are', body: <>
          <p>{L.serviceName} is operated by <b>{L.operator}</b> ("we", "us"), the Data Fiduciary for the personal data described here.</p>
          <Contact />
        </> },
        { id: 'data', title: 'Personal data we process', body: <>
          <p><b>Account data:</b> your name, email address, a one-way hash of your password (we never store the password itself), whether your
            email is verified, and a record of when you accepted this policy and which version.</p>
          <p><b>Statement data you upload:</b> transaction dates, amounts, balances, narrations/descriptions, merchant names, UPI IDs and
            reference numbers, the bank's name, and the original columns of each statement row. This is derived from files you choose to upload.</p>
          <p><b>Data you create:</b> categories, categorisation rules, notes on transactions, anomaly reviews and your preferences.</p>
          <p><b>Technical data:</b> your IP address is used briefly to protect against abuse (rate limiting); it is stored only in hashed form,
            and these records expire automatically within hours. We record the time of your last sign-in.</p>
          <p><b>What we do not collect or keep:</b></p>
          <ul>
            <li>Internet-banking usernames, passwords, OTPs, card numbers or CVVs - never requested.</li>
            <li>The uploaded files themselves - they are processed in memory and discarded; only the extracted transactions are saved.</li>
            <li>PDF statement passwords - used once to open the file and never stored or logged.</li>
          </ul>
        </> },
        { id: 'others', title: 'Information about other people', body: <>
          <p>Bank statements can contain the names or UPI IDs of people you paid or received money from. We process this only to show <i>you</i>
            your own transaction history, never to contact or profile those people. Please upload only statements for accounts you own or are
            authorised to use.</p>
        </> },
        { id: 'purpose', title: 'Why we process it (purpose and consent)', body: <>
          <p>We process your personal data on the basis of the consent you give when you create an account (DPDP Act, section 6), and only for these purposes:</p>
          <ul>
            <li>Reading your statements and organising transactions (bank detection, categorisation, UPI merchant recognition).</li>
            <li>Showing analytics, insights and flagging unusual transactions for your review.</li>
            <li>Keeping your account secure: authentication, preventing abuse, and security notifications.</li>
            <li>Sending service emails: email verification, password reset and password-change alerts. No marketing emails.</li>
          </ul>
          <p>Analysis is automated and rule-based. "Anomalies" are indicators for you to review - we make no decisions about you that have legal or
            similar effects. We do not use your data for advertising, sell it, or use it to train AI models.</p>
        </> },
        { id: 'sharing', title: 'Who we share it with', body: <>
          <p>We do not sell or rent personal data. We use a small number of service providers (Data Processors) who process data only on our
            instructions to run the service:</p>
          <ul>
            <li>Hosting and database: {L.hosting}</li>
            <li>Email delivery: {L.emailProvider} (receives only your email address and the email content)</li>
            <li>Fonts: the website loads the "Plus Jakarta Sans" font from Google Fonts, which means Google receives your IP address when the page loads.</li>
          </ul>
          <p>We may disclose data where required by Indian law or a lawful order of a court or authority.</p>
        </> },
        { id: 'storage', title: 'Where data is stored', body: <>
          <p>Data is stored with the providers listed above. Some may store data outside India; such transfers are permitted under section 16 of the
            DPDP Act except to countries the Government of India restricts by notification, and we will comply with any such restriction.</p>
        </> },
        { id: 'retention', title: 'How long we keep it', body: <>
          <ul>
            <li>Statements and transactions: until you delete them (individually, all at once, or by deleting your account).</li>
            <li>Account data: until you delete your account.</li>
            <li>Password-reset and verification links: expire within {`30 minutes`} and {`48 hours`} respectively; rate-limit records expire within hours.</li>
            <li>When you delete data it is removed from the live database immediately; copies in routine backups are overwritten within [30] days.</li>
          </ul>
        </> },
        { id: 'security', title: 'How we protect it', body: <>
          <ul>
            <li>Passwords are hashed with bcrypt; reset and verification links are single-use and stored only as hashes.</li>
            <li>Every record is tied to your account and isolated from other users.</li>
            <li>Uploaded files are validated as untrusted input and never kept: they are read once, and any temporary copy the server makes while receiving a large upload is deleted as soon as the request finishes.</li>
            <li>Logs never contain transaction descriptions, amounts or UPI IDs.</li>
            <li>Sign-in attempts and uploads are rate-limited; changing your password signs out all other sessions.</li>
          </ul>
          <p>No system is perfectly secure. If a personal data breach occurs, we will notify the Data Protection Board of India and affected users as
            required by the DPDP Act and its rules.</p>
        </> },
        { id: 'rights', title: 'Your rights', body: <>
          <p>Under the DPDP Act you have the right to:</p>
          <ul>
            <li><b>Access</b> a summary of your personal data and how it is processed - use <b>Settings → Download my data</b> for a complete copy.</li>
            <li><b>Correct or update</b> your data - edit your profile, transactions, categories and notes in the app.</li>
            <li><b>Erase</b> your data - delete statements, delete all data, or delete your account in Settings.</li>
            <li><b>Withdraw consent</b> at any time, as easily as you gave it, by deleting your account. Withdrawal does not affect processing done before it.</li>
            <li><b>Grievance redressal</b> - contact our Grievance Officer ({L.grievanceEmail}). We will respond within the period prescribed under the DPDP rules.</li>
            <li><b>Nominate</b> another person to exercise your rights in the event of your death or incapacity - write to {L.contactEmail}.</li>
          </ul>
          <p>If you are not satisfied with our response, you may complain to the <b>Data Protection Board of India</b> after using our grievance process.</p>
        </> },
        { id: 'duties', title: 'Your duties', body: <>
          <p>As required by section 15 of the DPDP Act, please provide accurate information, do not impersonate anyone, do not upload data you are not
            entitled to, and do not file false or frivolous complaints.</p>
        </> },
        { id: 'children', title: 'Children', body: <>
          <p>{L.serviceName} is only for people aged 18 or over. We do not knowingly process personal data of children. If we learn that an account belongs
            to someone under 18, we will delete it.</p>
        </> },
        { id: 'cookies', title: 'Cookies and browser storage', body: <>
          <p>We do not use advertising or analytics cookies. Your sign-in session is kept in your browser's session storage and is cleared when you close
            the tab. A few interface preferences may be kept in your browser.</p>
        </> },
        { id: 'changes', title: 'Changes to this policy', body: <>
          <p>If we make material changes we will notify you by email or in the app before they take effect, and ask for fresh consent where the law requires it.
            The version and effective date are shown at the top of this page.</p>
        </> },
        { id: 'contact', title: 'Contact and Grievance Officer', body: <Contact /> },
      ]}
    />
  )
}

export function Terms() {
  return (
    <LegalLayout
      title="Terms of Service"
      intro={<p>These terms are an agreement between you and <b className="text-ink">{L.operator}</b> for the use of {L.serviceName}. By creating an
        account you confirm that you are at least 18 years old and accept these terms and the <Link to="/privacy" className="font-semibold text-brand-600 hover:underline">Privacy Policy</Link>.</p>}
      sections={[
        { id: 'service', title: 'What Tally is', body: <>
          <p>{L.serviceName} is a personal tool that analyses bank statements <i>you</i> upload. It is <b>read-only</b>: it never connects to your bank account,
            never asks for banking credentials or OTPs, and cannot move money or make payments.</p>
          <p>{L.serviceName} is not a bank, payment service, credit bureau or registered investment adviser, and is not affiliated with or endorsed by any bank.
            Bank names are used only to recognise statement formats.</p>
        </> },
        { id: 'account', title: 'Your account', body: <ul>
          <li>Provide accurate information and keep your email address current.</li>
          <li>Keep your password confidential; you are responsible for activity on your account.</li>
          <li>Tell us promptly at {L.contactEmail} if you suspect unauthorised use.</li>
        </ul> },
        { id: 'content', title: 'Your data', body: <>
          <p>You keep all rights to the statements and data you upload. You allow us to process them only as needed to provide the service to you,
            as described in the Privacy Policy.</p>
          <p>Upload only statements for accounts you own or are authorised to access. You are responsible for having the right to upload them.</p>
        </> },
        { id: 'use', title: 'Acceptable use', body: <ul>
          <li>Do not upload malicious files or content designed to harm the service or other users.</li>
          <li>Do not try to access other users' data, probe or bypass security measures or rate limits, or overload the service.</li>
          <li>Do not use automated scripts to create accounts or scrape the service.</li>
          <li>Use the service only for lawful purposes.</li>
        </ul> },
        { id: 'accuracy', title: 'Accuracy - not financial advice', body: <>
          <p>Statement formats vary and automated reading, categorisation and anomaly detection can be wrong or incomplete. Always check important figures
            against your official bank statements.</p>
          <p>Insights and analytics are for information only and are <b>not financial, investment, tax or legal advice</b>. Anomaly flags are not a finding of
            fraud; if you suspect fraud, contact your bank immediately through its official channels.</p>
        </> },
        { id: 'availability', title: 'Availability and changes', body: <p>The service is provided "as is" and "as available". We may change, suspend or
          discontinue features, and will give reasonable notice of significant changes where practical. Please keep your own copies of important records.</p> },
        { id: 'termination', title: 'Ending your use', body: <p>You can delete your account at any time in Settings, which deletes your data as described in the
          Privacy Policy. We may suspend or close accounts that break these terms or put the service or other users at risk.</p> },
        { id: 'liability', title: 'Limitation of liability', body: <p>To the maximum extent permitted by law, we are not liable for indirect, incidental or
          consequential losses, or for decisions you make based on the service. Our total liability for any claim relating to the service is limited to
          [₹1,000] or the amount you paid us in the previous 12 months, whichever is greater. Nothing in these terms limits liability that cannot be limited under Indian law.</p> },
        { id: 'law', title: 'Governing law', body: <p>These terms are governed by the laws of India. Courts at {L.jurisdictionCity} have exclusive jurisdiction,
          subject to any rights you have under consumer protection law.</p> },
        { id: 'changes', title: 'Changes to these terms', body: <p>We will notify you of material changes by email or in the app before they take effect. Continuing
          to use the service after that means you accept the updated terms.</p> },
        { id: 'contact', title: 'Contact', body: <Contact /> },
      ]}
    />
  )
}
