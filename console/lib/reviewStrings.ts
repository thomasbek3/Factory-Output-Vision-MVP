import { reviewLexiconV1 } from "@/lib/reviewLexicon";

export const reviewStrings = reviewLexiconV1.strings;

export type ReviewLanguage = keyof typeof reviewStrings;
export type ReviewStringSet = (typeof reviewStrings)[ReviewLanguage];
