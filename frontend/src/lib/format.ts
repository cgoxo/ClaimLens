export const money = (n: number | null | undefined) => (n == null ? "–" : `₹${n.toLocaleString("en-IN")}`);

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

/** Days between two "10-Mar-2026" style dates, or null if either doesn't parse. */
export function daysBetween(a: string, b: string): number | null {
  const parse = (s: string) => {
    const m = /^(\d{1,2})[-\s]([A-Za-z]{3})[A-Za-z]*[-\s](\d{4})$/.exec(s.trim());
    const month = m ? MONTHS.indexOf(m[2].toLowerCase()) : -1;
    return m && month >= 0 ? Date.UTC(Number(m[3]), month, Number(m[1])) : null;
  };
  const [x, y] = [parse(a), parse(b)];
  return x === null || y === null ? null : Math.round((y - x) / 86_400_000);
}
