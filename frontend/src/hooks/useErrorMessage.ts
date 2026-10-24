import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";

/** Turn any thrown error into a translated, human message (backend sends stable `code`s). */
export function useErrorMessage() {
  const { t, i18n } = useTranslation();
  return (error: unknown): string => {
    if (error instanceof ApiError) {
      const key = `errors.${error.code}`;
      if (i18n.exists(key)) return t(key);
      if (error.fields) return Object.values(error.fields).flat().join(" ");
      return error.message;
    }
    return t("errors.generic");
  };
}
