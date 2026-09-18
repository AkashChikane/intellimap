import { useI18n } from "../i18n";

export default function LangToggle() {
  const { lang, toggle, t } = useI18n();
  return (
    <button
      type="button"
      className="lang-toggle"
      onClick={toggle}
      aria-label={t("langAria")}
      title={t("langAria")}
    >
      <span className={lang === "en" ? "is-on" : ""}>EN</span>
      <span className="lang-sep" aria-hidden="true">
        /
      </span>
      <span className={lang === "de" ? "is-on" : ""}>DE</span>
    </button>
  );
}
