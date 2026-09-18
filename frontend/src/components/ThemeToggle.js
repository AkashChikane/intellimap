import { useI18n } from "../i18n";
import { useTheme } from "../theme";

export default function ThemeToggle() {
  const { mode, toggle } = useTheme();
  const { t } = useI18n();
  const next = mode === "light" ? "dark" : "light";
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={next === "dark" ? t("themeToDark") : t("themeToLight")}
      title={next === "dark" ? t("themeToDark") : t("themeToLight")}
    >
      {mode === "light" ? (
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12.5 2.2a.75.75 0 0 0-1.2.7 7.5 7.5 0 1 1-8.4 8.4.75.75 0 0 0-.95.95A9 9 0 1 0 13.2 2.15a.75.75 0 0 0-.7.05Z"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 4.25a.75.75 0 0 1 .75-.75h.01a.75.75 0 0 1 0 1.5H12.75A.75.75 0 0 1 12 4.25Zm0 15.5a.75.75 0 0 1 .75.75v.01a.75.75 0 0 1-1.5 0V20.5a.75.75 0 0 1 .75-.75ZM4.25 12a.75.75 0 0 1-.75-.75v-.01a.75.75 0 0 1 1.5 0V11.25A.75.75 0 0 1 4.25 12Zm16.25-.75a.75.75 0 0 0-1.5 0v.01a.75.75 0 0 0 1.5 0ZM6.4 6.4a.75.75 0 0 1 0-1.06l.01-.01a.75.75 0 0 1 1.06 1.06l-.01.01A.75.75 0 0 1 6.4 6.4Zm11.25 11.25a.75.75 0 0 0-1.06 0l-.01.01a.75.75 0 1 0 1.06 1.06l.01-.01a.75.75 0 0 0 0-1.06ZM17.6 6.4a.75.75 0 0 1 1.06-1.06l.01.01A.75.75 0 1 1 17.6 6.41Zm-11.25 11.25a.75.75 0 0 0 0 1.06l-.01.01a.75.75 0 0 0 1.06-1.06l.01-.01a.75.75 0 0 0-1.06 0ZM12 7.5A4.5 4.5 0 1 0 12 16.5 4.5 4.5 0 0 0 12 7.5Z"
          />
        </svg>
      )}
      <span>{mode === "light" ? t("themeDark") : t("themeLight")}</span>
    </button>
  );
}
