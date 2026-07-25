export const reviewLexiconV1 = {
  version: "worker-ground-truth-es-419-v1",
  es: {
    instruction:
      "Cuenta una pieza terminada en el primer cuadro en que el trabajador la suelta y la pieza queda en el área de salida indicada.",
    countButton: "+1 PIEZA",
  },
  en: {
    instruction:
      "Count one finished piece on the first frame where the worker releases it and it remains in the designated output area.",
    countButton: "+1 COUNT",
  },
} as const;
