/* Initial state constants extracted from App.tsx so the reducer can
   import them without depending on the App component module. */
import type { RecordData } from './types';

export const INITIAL_RECORD: RecordData = {
  name: '',
  nameVariants: null,
  nameNative: null,
  nameNativeRtl: false,
  age: '',
  relationship: '',
  language: '',
  lastSeenLocation: '',
  lastSeenLocationSource: '',
  lastSeenLocationRtl: false,
  lastSeenDate: '',
  circumstance: '',
  physicalDesc: '',
  features: '',
  guardian: {
    guardianPresent: '',
    cpConsent: '',
    cmKnown: '',
    referralStatus: '',
  },
  searcherName: '',
  searcherNameLatin: '',
  missingPersons: [],
  familyRoster: [],
};
