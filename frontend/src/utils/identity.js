export function resolveTwinName(twinName, userName, wasCustomized = false) {
  const candidate = String(twinName || '').trim();
  const humanName = String(userName || '').trim();
  if (!candidate) return 'Echo';
  if (!wasCustomized && humanName && candidate.toLocaleLowerCase() === humanName.toLocaleLowerCase()) {
    return 'Echo';
  }
  return candidate;
}
