export function localDateKey(value) {
  if (!value) return '';
  const raw = String(value);
  const datePart = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  if (datePart) return datePart[1];
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? raw.slice(0, 10) : [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
}

export function parseLocalDateTime(value, dateOnlyHour = 9) {
  if (!value) return null;
  const raw = String(value);
  const local = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
  if (local) {
    return new Date(
      Number(local[1]), Number(local[2]) - 1, Number(local[3]),
      local[4] === undefined ? dateOnlyHour : Number(local[4]),
      local[5] === undefined ? 0 : Number(local[5]),
      local[6] === undefined ? 0 : Number(local[6]),
    );
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatTimeValue(value) {
  if (!value) return '';
  const match = String(value).match(/^(\d{1,2}):(\d{2})/);
  if (!match) return String(value);
  const date = new Date(2000, 0, 1, Number(match[1]), Number(match[2]));
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}
