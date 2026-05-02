/* Pure predicate: true for structlog event names that fire during
   Beat 6's matching window (1:51–1:54). Used by StructlogSidebar
   and ToolCallsSidebar for consistent kin-flash-highlight treatment.

   matching_trigger_fired  — fires after _trigger_matching() runs,
                             regardless of match count.
   matching_retrigger_fired — fires on extend turns when identity
                              fields change. */
export function isMergeFlashEvent(eventName: string): boolean {
  return (
    eventName === 'matching_trigger_fired' ||
    eventName === 'matching_retrigger_fired'
  );
}
