/* Pure timestamp formatters for split-view tent differentiation.

   Tent A renders 24-hour clock (HH:mm), Tent B renders 12-hour clock
   (h:mm a). Locale fixed to en-US so demo recordings and tests are
   deterministic regardless of viewer locale. */

export type Tent = 'a' | 'b';

const FORMATTER_24H = new Intl.DateTimeFormat('en-US', {
  hour12: false,
  hour: '2-digit',
  minute: '2-digit',
});

const FORMATTER_12H = new Intl.DateTimeFormat('en-US', {
  hour12: true,
  hour: 'numeric',
  minute: '2-digit',
});

export function formatTimestamp(date: Date, tent: Tent): string {
  return tent === 'a'
    ? FORMATTER_24H.format(date)
    : FORMATTER_12H.format(date);
}
