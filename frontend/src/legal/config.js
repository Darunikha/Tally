/**
 * Details shown in the Privacy Policy and Terms of Service.
 * ⚠️ Fill these in before launching publicly, and have the final text reviewed by a lawyer.
 * Keep `version` in sync with LEGAL_VERSION in backend/.env (stored with each user's consent).
 */
export const LEGAL = {
  version: '2026-11-17',
  effectiveDate: '17 November 2026',
  serviceName: 'Tally',
  operator: '[Your full name or company name]',
  address: '[Postal address, City, State, PIN], India',
  contactEmail: '[privacy@yourdomain.com]',
  grievanceOfficer: '[Name of Grievance Officer]',
  grievanceEmail: '[grievance@yourdomain.com]',
  jurisdictionCity: '[City]',
  hosting: '[Hosting providers and regions, e.g. MongoDB Atlas (Mumbai), Render (Singapore)]',
  emailProvider: '[Email provider, e.g. Resend]',
}

export const isPlaceholder = (v) => typeof v === 'string' && v.startsWith('[')
