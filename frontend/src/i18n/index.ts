import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import fr from "./fr.json";

export const LANGUAGES = [
  { code: "fr", label: "Français", dir: "ltr" },
  { code: "en", label: "English", dir: "ltr" },
  // { code: "ar", label: "العربية", dir: "rtl" },  ← add ar.json, the layout is already RTL-ready
] as const;

function initialLanguage(): string {
  try {
    return localStorage.getItem("canteen.lang") ?? "fr";
  } catch {
    return "fr";
  }
}

export function applyLanguage(code: string) {
  const lang = LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];
  document.documentElement.lang = lang.code;
  document.documentElement.dir = lang.dir;
  try {
    localStorage.setItem("canteen.lang", lang.code);
  } catch {
    /* ignore */
  }
  void i18n.changeLanguage(lang.code);
}

void i18n.use(initReactI18next).init({
  resources: { fr: { translation: fr }, en: { translation: en } },
  lng: initialLanguage(),
  fallbackLng: "fr",
  interpolation: { escapeValue: false },
});
applyLanguage(i18n.language);

export default i18n;
