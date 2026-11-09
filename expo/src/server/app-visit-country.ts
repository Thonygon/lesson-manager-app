/** Expo Hosting supplies the visitor country in this trusted edge header. */
export function appVisitCountry(request: Request): string {
  const edge = request.headers.get('eas-ip-country');
  const cf = (request as Request & { cf?: { country?: string | null } }).cf?.country;
  const country = String(edge || cf || '').trim().toUpperCase();
  return /^[A-Z]{2}$/.test(country) && !['XX', 'T1'].includes(country) ? country : 'ZZ';
}
