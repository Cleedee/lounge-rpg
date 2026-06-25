import ptBR from "./pt-BR.json";

const translations: Record<string, Record<string, string>> = {
  "pt-BR": ptBR,
};

let currentLocale = "pt-BR";

export function setLocale(locale: string) {
  if (translations[locale]) {
    currentLocale = locale;
  }
}

export function getLocale(): string {
  return currentLocale;
}

export function t(key: string, fallback: string = "", vars?: Record<string, string | number>): string {
  const dict = translations[currentLocale];
  let val = dict?.[key] || fallback || key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      val = val.replace(`{${k}}`, String(v));
    }
  }
  return val;
}
